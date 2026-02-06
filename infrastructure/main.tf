# Terraform configuration for the GCP AI/ML Platform
# Includes GKE (Ray), Cloud SQL, Composer, and IAM bindings.

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# --- Variables ---

variable "project_id" {
  description = "The GCP Project ID"
  type        = string
}

variable "region" {
  description = "The GCP Region"
  type        = string
  default     = "us-central1"
}
variable "db_password" {
  description = "Password for the Cloud SQL user"
  type        = string
  sensitive   = true
  default     = "mlflow_pass"
}

# --- Enable APIs ---

locals {
  services = [
    "container.googleapis.com",
    "artifactregistry.googleapis.com",
    "sqladmin.googleapis.com",
    "aiplatform.googleapis.com",
    "compute.googleapis.com",
    "iam.googleapis.com",
    "storage.googleapis.com"
  ]
}

resource "google_project_service" "enabled_apis" {
  for_each = toset(local.services)
  project  = var.project_id
  service  = each.key

  disable_on_destroy = false
}

# --- Artifact Registry ---

resource "google_artifact_registry_repository" "ml_images" {
  location      = var.region
  repository_id = "ml-images"
  description   = "Docker repository for AI/ML images"
  format        = "DOCKER"
  depends_on    = [google_project_service.enabled_apis]
}

# --- Cloud Storage ---

resource "google_storage_bucket" "ml_data" {
  name          = "${var.project_id}-ml-data"
  location      = var.region
  force_destroy = true
}

resource "google_storage_bucket" "mlflow_artifacts" {
  name          = "${var.project_id}-mlflow-artifacts"
  location      = var.region
  force_destroy = true
}
# --- Cloud SQL (PostgreSQL) ---

resource "google_sql_database_instance" "ml_db_instance" {
  name             = "ml-db-instance"
  database_version = "POSTGRES_15"
  region           = var.region

  settings {
    tier = "db-f1-micro"
  }
  deletion_protection = false
  depends_on          = [google_project_service.enabled_apis]
}

resource "google_sql_database" "mlflow_db" {
  name     = "mlflow_db"
  instance = google_sql_database_instance.ml_db_instance.name
}

resource "google_sql_user" "ml_user" {
  name     = "ml_user"
  instance = google_sql_database_instance.ml_db_instance.name
  password = var.db_password
}

# --- GKE Cluster (Ray Enabled) ---

resource "google_container_cluster" "ai_cluster" {
  name     = "ai-cluster-dev"
  location = var.region

  # Standard cluster requires initial_node_count or a node_config
  initial_node_count = 1

  # Enabling Workload Identity
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  # Enabling Ray Operator Add-on
  addons_config {
    ray_operator_config {
      enabled = true
    }
  }

  node_config {
    machine_type = "e2-standard-4"
    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }

  deletion_protection = false
  depends_on          = [google_project_service.enabled_apis]
}

# GPU Spot Node Pool
resource "google_container_node_pool" "gpu_pool_spot" {
  name     = "gpu-pool-spot"
  location = var.region
  cluster  = google_container_cluster.ai_cluster.name

  autoscaling {
    min_node_count = 0
    max_node_count = 10
  }

  node_config {
    spot         = true
    machine_type = "g2-standard-4"

    guest_accelerator {
      type  = "nvidia-l4"
      count = 1
    }

    taint {
      key    = "nvidia.com/gpu"
      value  = "true"
      effect = "NO_SCHEDULE"
    }

    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }
}



# --- IAM & Workload Identity ---

resource "google_service_account" "ml_platform_sa" {
  account_id   = "ml-platform-sa"
  display_name = "ML Platform SA"
}

resource "google_project_iam_member" "storage_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.ml_platform_sa.email}"
}

resource "google_project_iam_member" "sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.ml_platform_sa.email}"
}



# Workload Identity Binding
resource "google_service_account_iam_member" "workload_identity_binding" {
  service_account_id = google_service_account.ml_platform_sa.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[ml-workloads/ray-worker-sa]"
}

# --- Outputs ---

output "bucket_name" {
  description = "The name of the GCS bucket for ML data"
  value       = google_storage_bucket.ml_data.name
}

output "cluster_name" {
  description = "The name of the GKE cluster"
  value       = google_container_cluster.ai_cluster.name
}

output "cluster_location" {
  description = "The location of the GKE cluster"
  value       = google_container_cluster.ai_cluster.location
}

output "sql_connection_name" {
  description = "The connection name of the Cloud SQL instance"
  value       = google_sql_database_instance.ml_db_instance.connection_name
}
