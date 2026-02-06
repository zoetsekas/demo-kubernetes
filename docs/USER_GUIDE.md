# User Guide

This guide provides detailed instructions for deploying and operating the GKE Ray Embedding Pipeline.

## 1. Prerequisites
- **Google Cloud Account**: Project ID with billing enabled.
- **Kaggle API Key**: Required for the Million Headlines dataset.
- **Tools**: `gcloud`, `kubectl`, `terraform`, `docker`, and `make`.

## 2. Configuration Deep-Dive
The project uses **Hydra** for configuration. All settings are located in `src/demo/conf/config.yaml`.

### Common Overrides
You can override any variable using `HYDRA_ARGS` with the `make run` command:
- `dataset.nrows`: Number of rows to process (default 10,000).
- `ray.chunk_size`: Batch size for Ray workers.
- `model.name`: Hugging Face model identifier (e.g., `sentence-transformers/all-mpnet-base-v2`).

## 3. Dataset Integration
### Using Kaggle (Default)
The pipeline is pre-configured for the `therohk/million-headlines` dataset.
```bash
make run
```

### Using Hugging Face
To switch to a Hugging Face dataset, override the source and path:
```bash
make run HYDRA_ARGS="dataset.source_type=huggingface dataset.huggingface.path=imdb dataset.huggingface.column=text"
```

## 4. Monitoring & Observability

### Ray Dashboard
Establish a connection to the Ray cluster:
```bash
make connect
```
Visit `http://localhost:8265` to monitor worker nodes, GPU utilization, and actor status.

### MLflow
Establish a connection to the MLflow server:
```bash
make connect-mlflow
```
Visit `http://localhost:5000` to view experiment metrics, throughput logs, and processed dataset summaries.

## 5. Scaling and Maintenance
The `infrastructure/templates/ray-cluster.yaml.tftpl` defines the cluster size. You can adjust horizontal scaling by changing `minReplicas` and `maxReplicas` in the `workerGroupSpecs`.

### Spot Instances
The GKE node pool is configured to use **Spot Instances** by default to minimize costs. If you need 100% availability, disable `spot = true` in `infrastructure/main.tf`.

## 6. Troubleshooting
- **GPU Not Found**: Ensure you have enough quota for `NVIDIA_L4_GPUS` in your GCP region.
- **GCS Access Denied**: verify the `ml-platform-sa` has `roles/storage.objectAdmin` permissions.
- **Ray Connection Refused**: Ensure `make connect` is still running in the background.
