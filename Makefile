PROJECT_ID ?= $(shell gcloud config get-value project)
REGION ?= us-central1
IMAGE_NAME ?= ray-worker
REPO_NAME ?= ml-images
TAG ?= latest
ARTIFACT_REGISTRY = $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(REPO_NAME)

.PHONY: help init plan apply destroy build push run deploy-ray connect

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

init: ## Initialize Terraform
	cd infrastructure && terraform init

plan: ## Plan Terraform changes
	cd infrastructure && terraform plan -var="project_id=$(PROJECT_ID)" -var="region=$(REGION)"

apply: ## Apply Terraform changes
	cd infrastructure && terraform apply -var="project_id=$(PROJECT_ID)" -var="region=$(REGION)" -auto-approve

destroy: ## Destroy Terraform resources
	cd infrastructure && terraform destroy -var="project_id=$(PROJECT_ID)" -var="region=$(REGION)" -auto-approve

build: ## Build Docker image
	docker build -t $(ARTIFACT_REGISTRY)/$(IMAGE_NAME):$(TAG) -f docker/demo.Dockerfile docker/

push: ## Push Docker image to Artifact Registry
	gcloud auth configure-docker $(REGION)-docker.pkg.dev
	docker push $(ARTIFACT_REGISTRY)/$(IMAGE_NAME):$(TAG)

deploy-ray: ## Deploy Ray Cluster manifest (substituting image name)
	@echo "Deploying Ray Cluster..."
	@sed "s|YOUR-PROJECT-ID|$(PROJECT_ID)|g" infrastructure/ray-cluster.yaml | kubectl apply -f -

connect: ## Port forward to Ray Cluster (keeps running in foreground)
	@echo "Port forwarding to Ray Head Service..."
	@echo "Ray Client: localhost:10001"
	@echo "Ray Dashboard: localhost:8265"
	kubectl port-forward svc/ray-cluster-head-svc 10001:10001 8265:8265

run: ## Run the Python driver script using Docker
	@echo "Running in Docker..."
	@echo "Ensure KAGGLE_USERNAME and KAGGLE_KEY are set in your environment."
	docker run -it --rm \
		-v $(PWD)/src:/app/src \
		-v $(HOME)/.config/gcloud:/root/.config/gcloud \
		-e PROJECT_ID=$(PROJECT_ID) \
		-e KAGGLE_USERNAME=$(KAGGLE_USERNAME) \
		-e KAGGLE_KEY=$(KAGGLE_KEY) \
		-e GOOGLE_CLOUD_PROJECT=$(PROJECT_ID) \
		-e RAY_ADDRESS=ray://host.docker.internal:10001 \
		$(ARTIFACT_REGISTRY)/$(IMAGE_NAME):$(TAG) \
		python src/demo/main.py
