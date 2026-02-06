PROJECT_ID ?= $(shell gcloud config get-value project)
REGION ?= us-central1
IMAGE_NAME ?= ray-worker
REPO_NAME ?= ml-images
TAG ?= latest
ARTIFACT_REGISTRY = $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(REPO_NAME)

.PHONY: help init plan apply destroy build push run connect connect-mlflow

help: ## Show this help
	@docker run --rm -v "$(CURDIR)":/app -w /app python:3.10-slim python -c "import re; [print(f'\033[36m{m.group(1):<20}\033[0m {m.group(2)}') for m in [re.search(r'^([a-zA-Z_-]+):.*?## (.*)$$', l) for l in open('makefile')] if m]"

init: ## Initialize Terraform
	cd infrastructure && terraform init

plan: ## Plan Terraform changes
	cd infrastructure && terraform plan -var="project_id=$(PROJECT_ID)" -var="region=$(REGION)"

apply: ## Apply Terraform changes (Deploys GCP + K8s stack)
	cd infrastructure && terraform apply -var="project_id=$(PROJECT_ID)" -var="region=$(REGION)" -auto-approve

destroy: ## Destroy Terraform resources
	cd infrastructure && terraform destroy -var="project_id=$(PROJECT_ID)" -var="region=$(REGION)" -auto-approve

build: ## Build Docker image
	docker build -t $(ARTIFACT_REGISTRY)/$(IMAGE_NAME):$(TAG) -f docker/demo.Dockerfile .

push: ## Push Docker image to Artifact Registry
	gcloud auth configure-docker $(REGION)-docker.pkg.dev
	docker push $(ARTIFACT_REGISTRY)/$(IMAGE_NAME):$(TAG)

connect: ## Port forward to Ray Cluster
	@echo "Port forwarding to Ray Head Service..."
	@echo "Ray Client: localhost:10001"
	@echo "Ray Dashboard: localhost:8265"
	@docker run --rm -it --network=host -v "$(APPDATA)/gcloud:/root/.config/gcloud" google/cloud-sdk:latest \
		bash -c "gcloud container clusters get-credentials ai-cluster-dev --region $(REGION) --project $(PROJECT_ID) && kubectl port-forward svc/ray-cluster-head-svc 10001:10001 8265:8265 -n ml-workloads"

connect-mlflow: ## Port forward to MLflow Server UI
	@echo "Port forwarding to MLflow Service (localhost:5000)..."
	@docker run --rm -it --network=host -v "$(APPDATA)/gcloud:/root/.config/gcloud" google/cloud-sdk:latest \
		bash -c "gcloud container clusters get-credentials ai-cluster-dev --region $(REGION) --project $(PROJECT_ID) && kubectl port-forward svc/mlflow-service 5000:5000 -n ml-workloads"

run: ## Run the Python driver script using Docker
	@echo "Running in Docker..."
	@echo "Ensure KAGGLE_USERNAME and KAGGLE_KEY are set in your environment."
	docker run -it --rm \
		-v "$(CURDIR)/src:/app/src" \
		-v "$(APPDATA)/gcloud:/root/.config/gcloud" \
		-e PROJECT_ID=$(PROJECT_ID) \
		-e KAGGLE_USERNAME=$(KAGGLE_USERNAME) \
		-e KAGGLE_KEY=$(KAGGLE_KEY) \
		-e GOOGLE_CLOUD_PROJECT=$(PROJECT_ID) \
		-e RAY_ADDRESS=ray://host.docker.internal:10001 \
		-e MLFLOW_TRACKING_URI=http://host.docker.internal:5000 \
		$(ARTIFACT_REGISTRY)/$(IMAGE_NAME):$(TAG) \
		python src/demo/main.py $(HYDRA_ARGS)
