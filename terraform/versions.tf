terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.0"
    }
  }

  # state remoto; o bucket e informado no init (nao versionado):
  #   terraform init -backend-config="bucket=<BUCKET_DO_STATE>"
  backend "gcs" {
    prefix = "anac-pdm/t2"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
