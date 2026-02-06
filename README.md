# GKE Ray Embedding Pipeline

A complete solution for standing up a Ray cluster on Google Kubernetes Engine (GKE) to generate embeddings from the "Million Headlines" dataset using Hugging Face transformers.

## Features
- **Infrastructure as Code**: Terraform configuration for GKE, GCS, and Artifact Registry.
- **Distributed Computing**: Ray cluster deployment on Kubernetes for scalable processing.
- **Machine Learning**: Embedding generation using `sentence-transformers` served via Ray Serve.
- **Interactive Development**: VS Code integration for remote debugging against the cluster.
- **Dockerized**: Containerized environment with GPU support.

## Project Structure
```text
.
├── .vscode/               # VS Code launch and settings
├── docker/                # Dockerfile and python requirements
├── infrastructure/        # Terraform and Kubernetes manifests
├── src/
│   └── demo/
│       └── main.py        # Main driver and Ray Serve application
├── makefile               # Project automation commands
├── pyproject.toml         # Python project metadata
└── README.md
```

## Prerequisites
- Google Cloud Project with billing enabled.
- [Terraform](https://www.terraform.io/downloads.html) installed.
- [gcloud SDK](https://cloud.google.com/sdk/docs/install) installed and authenticated.
- [kubectl](https://kubernetes.io/docs/tasks/tools/) installed.
- Kaggle API credentials (`KAGGLE_USERNAME`, `KAGGLE_KEY`).

## Quick Start

### 1. Infrastructure Setup
Initialize and provision the GCP resources:
```bash
make init
make apply PROJECT_ID=your-project-id
```

### 2. Build and Deploy
Build the custom Ray worker image and deploy the cluster:
```bash
make build PROJECT_ID=your-project-id
make push PROJECT_ID=your-project-id
make deploy-ray PROJECT_ID=your-project-id
```

### 3. Run the Pipeline
Execute the embedding generation script:
```bash
export KAGGLE_USERNAME=xxx
export KAGGLE_KEY=xxx
make run PROJECT_ID=your-project-id
```

## Interactive Development
You can develop directly against the GKE Ray cluster from VS Code:
1. Run `make connect` in a dedicated terminal to port-forward the Ray head.
2. Use the **"Python: Ray Remote Demo"** debug configuration (F5) in VS Code.

## License
MIT
