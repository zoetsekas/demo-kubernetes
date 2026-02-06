# System Architecture

The GKE Ray Embedding Pipeline is designed for high-throughput, horizontally scalable text embedding generation using a hybrid orchestration model.

## Component Overview

```mermaid
graph TD
    subgraph "External"
        Kaggle["Kaggle API"]
        HF["Hugging Face Hub"]
    end

    subgraph "GCP Infrastructure"
        GCS["Google Cloud Storage (Buckets)"]
        SQL["Cloud SQL (PostgreSQL)"]
        AR["Artifact Registry"]
    end

    subgraph "GKE Cluster"
        subgraph "Ray Head Group"
            Head["Ray Head Node"]
            Serve["Ray Serve Controller"]
        end
        
        subgraph "Ray Worker Group (GPU)"
            Worker1["Ray Worker (L4 GPU)"]
            Worker2["Ray Worker (L4 GPU)"]
        end

        MLflow["MLflow Tracking Server"]
        SQLProxy["Cloud SQL Proxy"]
    end

    Kaggle -->|Download| GCS
    HF -->|Load| GCS
    Head -->|Job Orchestration| Worker1
    Head -->|Job Orchestration| Worker2
    Worker1 -->|Read/Write| GCS
    Worker2 -->|Read/Write| GCS
    Worker1 -->|Log Metrics| MLflow
    Worker2 -->|Log Metrics| MLflow
    MLflow -->|Metadata| SQLProxy
    SQLProxy -->|Connect| SQL
    MLflow -->|Artifacts| GCS
```

## Scaling Model

The architecture implements a **Two-Layer Scaling Model**:

### 1. Infrastructure Layer (GKE Cluster Autoscaler)
GKE monitors the resource requests in the cluster. When Ray attempts to spin up more worker pods than the current nodes can accommodate, GKE automatically provisions new Compute Engine instances (e.g., `g2-standard-4` spots with L4 GPUs).

### 2. Application Layer (Ray Autoscaler & Ray Serve)
- **Ray Autoscaler**: Monitors the task queue and pending actor requests. It dynamically requests more pod replicas from Kubernetes when load increases.
- **Ray Serve**: Manages the life cycle of the `EmbeddingModel` deployment. It uses request-based autoscaling to adjust replicas (min/max) based on real-time traffic.

## Benefits of Ray on GKE

| Feature         | GKE (Kubernetes)  | Ray                      | Benefit of Hybrid                                        |
| :-------------- | :---------------- | :----------------------- | :------------------------------------------------------- |
| **Scheduling**  | Container-level   | Task/Actor-level         | Fine-grained GPU slicing with container isolation.       |
| **Scaling**     | Node pool scaling | Logical resource scaling | Ray handles the "what" to scale; GKE handles the "how".  |
| **Portability** | Standard K8s API  | Python-native API        | Runs on any cloud with a standard Kubernetes setup.      |
| **Recovery**    | Pod restarts      | Actor/Task retries       | Multi-level fault tolerance for long-running batch jobs. |
