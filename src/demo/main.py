import os
import time
import pandas as pd
from google.cloud import storage
import ray
from ray import serve
from sentence_transformers import SentenceTransformer
import kaggle
import mlflow
import logging
import hydra
from omegaconf import DictConfig, OmegaConf
import datasets

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Configure settings from environment for infrastructure
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "your-project-id")
BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", f"{PROJECT_ID}-ml-data")

# --- 1. Data Ingestion ---


def download_and_upload_data(dataset_cfg: DictConfig):
    """Downloads dataset from Kaggle or HF and uploads to GCS."""
    source_type = dataset_cfg.source_type

    if source_type == "kaggle":
        kaggle_path = dataset_cfg.kaggle.kaggle_path
        csv_filename = dataset_cfg.kaggle.csv_filename

        logger.info(f"Downloading {kaggle_path} from Kaggle...")
        kaggle.api.authenticate()
        kaggle.api.dataset_download_files(kaggle_path, path=".", unzip=True)

        local_file = csv_filename
    elif source_type == "huggingface":
        hf_path = dataset_cfg.huggingface.path
        hf_split = dataset_cfg.huggingface.split
        hf_column = dataset_cfg.huggingface.column
        local_file = f"{hf_path.replace('/', '_')}.csv"

        logger.info(f"Loading {hf_path} ({hf_split}) from Hugging Face...")
        dataset = datasets.load_dataset(hf_path, split=hf_split, streaming=True)

        # Take nrows and convert to expected format
        rows = []
        for i, row in enumerate(dataset):
            if i >= dataset_cfg.nrows:
                break
            rows.append({"headline_text": row[hf_column]})

        logger.info(f"Converting HF dataset to {local_file}...")
        df = pd.DataFrame(rows)
        df.to_csv(local_file, index=False)
    else:
        raise ValueError(f"Unknown source_type: {source_type}")

    if not os.path.exists(local_file):
        raise FileNotFoundError(
            f"Could not find local file {local_file} after ingestion."
        )

    # We use a consistent filename in GCS for the processing step
    gcs_filename = "active_dataset.csv"
    logger.info(f"Uploading {local_file} to gs://{BUCKET_NAME}/raw/{gcs_filename}...")
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(f"raw/{gcs_filename}")
    blob.upload_from_filename(local_file)
    logger.info("Upload complete.")

    return local_file, gcs_filename


# --- 2. Ray Serve Deployment ---


@serve.deployment(
    autoscaling_config={
        "min_replicas": 2,
        "max_replicas": 4,
    },
    ray_actor_options={"num_gpus": 0.5},  # Adjustable based on resource availability
)
class EmbeddingModel:
    def __init__(self, model_name: str):
        logger.info(f"Loading Sentence Transformer model: {model_name}...")
        self.model = SentenceTransformer(model_name)

    async def __call__(self, text: str):
        embeddings = self.model.encode(text)
        return embeddings.tolist()


# --- 3. Processing Logic ---


@ray.remote
def process_batch(batch_df):
    """Sends a batch of text to the Serve deployment for embedding."""
    texts = batch_df["headline_text"].tolist()
    # In a real scenario, you might want to batch these requests or use a handle that supports batching
    # For simplicity, we loop or send async requests (this part can be optimized)

    # Getting the handle inside the remote function to ensure connectivity
    handle = serve.get_deployment("EmbeddingModel").get_handle()

    results = []
    # Using ray.get to wait for results - in high scale, use async appropriately
    refs = [handle.remote(text) for text in texts]
    embeddings = ray.get(refs)

    return pd.DataFrame({"text": texts, "embedding": embeddings})


@hydra.main(version_base=None, config_path="conf", config_name="config")
def main(cfg: DictConfig):
    logger.info(f"Configuration:\n{OmegaConf.to_yaml(cfg)}")

    # 0. Setup MLflow
    mlflow_tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", cfg.mlflow.tracking_uri)
    mlflow.set_tracking_uri(mlflow_tracking_uri)
    mlflow.set_experiment(cfg.mlflow.experiment_name)

    # 1. Ingest Data
    # Ensure KAGGLE_USERNAME and KAGGLE_KEY are set in environment if using Kaggle
    try:
        local_file, gcs_filename = download_and_upload_data(cfg.dataset)
    except Exception as e:
        logger.error(f"Data ingestion skipped or failed: {e}")
        # Proceeding assuming data might already be there for dev loop
        local_file = (
            cfg.dataset.kaggle.csv_filename
            if cfg.dataset.source_type == "kaggle"
            else f"{cfg.dataset.huggingface.path.replace('/', '_')}.csv"
        )
        gcs_filename = "active_dataset.csv"

    # 2. Connect to Ray Cluster
    # If RAY_ADDRESS env var is set (e.g. "ray://localhost:10001"), it will connect to that.
    # Otherwise it connects to local cluster (if running on head node) or starts a local one.
    ray_address = os.environ.get("RAY_ADDRESS", cfg.ray.address)
    if ray_address:
        logger.info(f"Connecting to Ray cluster at {ray_address}...")
        ray.init(address=ray_address)
    else:
        logger.info("Starting local Ray instance (or connecting to local default)...")
        ray.init()

    # 3. Deploy Model
    logger.info("Deploying Ray Serve application...")
    serve.run(EmbeddingModel.bind(cfg.model.name))

    # 4. Process Data
    logger.info("Reading data from GCS...")
    # NOTE: Efficiently reading GCS in chunks with Pandas
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(f"raw/{gcs_filename}")

    # For demo purpose, download locally to stream (or use gcsfs)
    # Use the local file from ingestion if it exists, otherwise download from GCS
    if not os.path.exists(local_file):
        logger.info(f"Downloading {gcs_filename} from GCS...")
        blob.download_to_filename(local_file)

    # Process in chunks using Ray
    chunk_size = cfg.ray.chunk_size
    futures = []

    logger.info("Submitting processing tasks...")
    # Read only first nrows rows
    for chunk in pd.read_csv(local_file, chunksize=chunk_size, nrows=cfg.dataset.nrows):
        # The ingestion logic ensures the column is always 'headline_text'
        futures.append(process_batch.remote(chunk))

    logger.info("Waiting for results...")
    start_time = time.time()

    with mlflow.start_run():
        mlflow.log_params(OmegaConf.to_container(cfg, resolve=True))

        results = ray.get(futures)
        final_df = pd.concat(results)

        processing_time = time.time() - start_time
        mlflow.log_metric("total_headlines", len(final_df))
        mlflow.log_metric("processing_time_sec", processing_time)
        mlflow.log_metric(
            "throughput_headlines_per_sec", len(final_df) / processing_time
        )

        # 5. Save Embeddings
        output_filename = "embeddings.parquet"
        final_df.to_parquet(output_filename)

        # Log summary as artifact
        summary = final_df.describe().to_string()
        with open("summary.txt", "w") as f:
            f.write(summary)
        mlflow.log_artifact("summary.txt")

        logger.info(f"Uploading results to gs://{BUCKET_NAME}/processed/...")
        out_blob = bucket.blob(f"processed/{output_filename}")
        out_blob.upload_from_filename(output_filename)
    logger.info("Done!")


if __name__ == "__main__":
    # We call main() without arguments, Hydra handles the rest
    main()
