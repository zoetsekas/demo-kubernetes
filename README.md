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
├── docs/                  # Architecture and User Guides
├── docker/                # Dockerfile and python requirements
├── infrastructure/        # Terraform and Kubernetes templates
│   └── templates/         # Parameterized YAML templates
├── src/
│   └── demo/
│       └── main.py        # Main driver and Ray Serve application
├── makefile               # Project automation commands
├── pyproject.toml         # Python project metadata
└── README.md
```

## Local Development Environment
To set up your local development environment, you will need the following tools:

### Required Tools
- **[Terraform](https://www.terraform.io/downloads.html)** (>= 1.0): For managing cloud infrastructure.
- **[Google Cloud SDK (gcloud)](https://cloud.google.com/sdk/docs/install)**: For GCP authentication and project management.
- **[kubectl](https://kubernetes.io/docs/tasks/tools/)**: For interacting with the GKE cluster.
- **[Docker](https://docs.docker.com/get-docker/)**: For building and pushing container images.
- **[Make](https://www.gnu.org/software/make/)**: For running automation targets defined in the `makefile`.

### Recommended VS Code Extensions
- **[HashiCorp Terraform](https://marketplace.visualstudio.com/items?itemName=HashiCorp.terraform)**: Syntax highlighting and autocompletion for `.tf` files.
- **[Python](https://marketplace.visualstudio.com/items?itemName=ms-python.python)**: For local scripts and remote debugging.
- **[Kubernetes](https://marketplace.visualstudio.com/items?itemName=ms-kubernetes-tools.vscode-kubernetes-tools)**: For managing GKE resources directly from the editor.
- **[YAML](https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml)**: For editing Kubernetes manifests and templates.
- **[Docker](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-docker)**: For managing local containers and images.

## Prerequisites
- Google Cloud Project with billing enabled.
- Kaggle API credentials (`KAGGLE_USERNAME`, `KAGGLE_KEY`).
- GCP regions with `NVIDIA_L4_GPU` quota available (default: `us-central1`).

## Quick Start

### 1. Infrastructure Setup
Initialize and provision the GCP resources:
```bash
make init
make apply PROJECT_ID=your-project-id
```

### 2. Build and Deploy
Build the custom Ray worker image:
```bash
make build PROJECT_ID=your-project-id
make push PROJECT_ID=your-project-id
```

Deploy everything via Terraform:
```bash
make apply PROJECT_ID=your-project-id
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
