import os
import time
import pandas as pd
from google.cloud import storage
import ray
from ray import serve
from sentence_transformers import SentenceTransformer
import kaggle

# Configure settings
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "your-project-id")
BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", f"{PROJECT_ID}-ml-data")
KAGGLE_DATASET = "therohk/million-headlines"
CSV_FILENAME = "abcnews-date-text.csv"

# --- 1. Data Ingestion ---


def download_and_upload_data():
    """Downloads dataset from Kaggle and uploads to GCS."""
    print(f"Downloading {KAGGLE_DATASET} from Kaggle...")
    kaggle.api.authenticate()
    kaggle.api.dataset_download_files(KAGGLE_DATASET, path=".", unzip=True)

    if not os.path.exists(CSV_FILENAME):
        raise FileNotFoundError(f"Could not find {CSV_FILENAME} after download.")

    print(f"Uploading {CSV_FILENAME} to gs://{BUCKET_NAME}...")
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(f"raw/{CSV_FILENAME}")
    blob.upload_from_filename(CSV_FILENAME)
    print("Upload complete.")


# --- 2. Ray Serve Deployment ---


@serve.deployment(
    autoscaling_config={
        "min_replicas": 2,
        "max_replicas": 4,
    },
    ray_actor_options={"num_gpus": 0.5},  # Adjustable based on resource availability
)
class EmbeddingModel:
    def __init__(self):
        print("Loading Sentence Transformer model...")
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

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


def main():
    # 1. Ingest Data
    # Ensure KAGGLE_USERNAME and KAGGLE_KEY are set in environment
    try:
        download_and_upload_data()
    except Exception as e:
        print(f"Data ingestion skipped or failed: {e}")
        # Proceeding assuming data might already be there for dev loop

    # 2. Connect to Ray Cluster
    # If RAY_ADDRESS env var is set (e.g. "ray://localhost:10001"), it will connect to that.
    # Otherwise it connects to local cluster (if running on head node) or starts a local one.
    ray_address = os.environ.get("RAY_ADDRESS")
    if ray_address:
        print(f"Connecting to Ray cluster at {ray_address}...")
        ray.init(address=ray_address)
    else:
        print("Starting local Ray instance (or connecting to local default)...")
        ray.init()

    # 3. Deploy Model
    print("Deploying Ray Serve application...")
    serve.run(EmbeddingModel.bind())

    # 4. Process Data
    print("Reading data from GCS...")
    # NOTE: Efficiently reading GCS in chunks with Pandas
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(f"raw/{CSV_FILENAME}")

    # For demo purpose, download locally to stream (or use gcsfs)
    if not os.path.exists(CSV_FILENAME):
        blob.download_to_filename(CSV_FILENAME)

    # Process in chunks using Ray
    chunk_size = 1000
    futures = []

    print("Submitting processing tasks...")
    # Read only first 10000 rows for demo speed
    for chunk in pd.read_csv(CSV_FILENAME, chunksize=chunk_size, nrows=10000):
        futures.append(process_batch.remote(chunk))

    print("Waiting for results...")
    results = ray.get(futures)
    final_df = pd.concat(results)

    # 5. Save Embeddings
    output_filename = "embeddings.parquet"
    final_df.to_parquet(output_filename)

    print(f"Uploading results to gs://{BUCKET_NAME}/processed/...")
    out_blob = bucket.blob(f"processed/{output_filename}")
    out_blob.upload_from_filename(output_filename)
    print("Done!")


if __name__ == "__main__":
    main()
