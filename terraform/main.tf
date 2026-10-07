# Recursos estaveis e novos do T2. Nada aqui importa ou referencia recursos de
# aula (prefixo aula-*). O que liga e desliga por custo (modelo no endpoint do
# Vertex, job do Dataflow, servico do Cloud Run) fica em scripts/t2/, para o
# liga/desliga de cada demo nao virar drift do Terraform.

locals {
  services = [
    "dataflow.googleapis.com",
    "pubsub.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "aiplatform.googleapis.com",
    "bigquery.googleapis.com",
    "compute.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each = toset(local.services)

  service            = each.value
  disable_on_destroy = false # destroy nunca desliga API usada por outras atividades do projeto
}

# ---------------------------------------------------------------- Pub/Sub ---

resource "google_pubsub_topic" "voos" {
  name                       = "anac-voos"
  message_retention_duration = "86400s" # 1 dia: permite reprocessar a demo
  labels                     = var.labels

  depends_on = [google_project_service.apis]
}

# Recebe do proprio pipeline os eventos que violam o contrato (parse/validacao).
# A politica de dead-letter nativa do Pub/Sub nao e usada: ela exige conceder
# papeis a conta de servico do Pub/Sub, e o pipeline ja trata a falha de forma
# observavel.
resource "google_pubsub_topic" "voos_dlq" {
  name                       = "anac-voos-dlq"
  message_retention_duration = "604800s"
  labels                     = var.labels

  depends_on = [google_project_service.apis]
}

resource "google_pubsub_subscription" "voos_dataflow" {
  name                       = "anac-voos-dataflow"
  topic                      = google_pubsub_topic.voos.id
  ack_deadline_seconds       = 60
  message_retention_duration = "86400s"
  labels                     = var.labels

  expiration_policy {
    ttl = "" # nunca expira, mesmo parada entre as demos
  }
}

# Permite inspecionar o dead-letter na demo sem consumir o topico de outra forma
resource "google_pubsub_subscription" "voos_dlq_inspecao" {
  name                       = "anac-voos-dlq-inspecao"
  topic                      = google_pubsub_topic.voos_dlq.id
  ack_deadline_seconds       = 30
  message_retention_duration = "604800s"
  labels                     = var.labels

  expiration_policy {
    ttl = ""
  }
}

# ------------------------------------------------------ Artifact Registry ---

resource "google_artifact_registry_repository" "anac" {
  location      = var.region
  repository_id = "anac"
  description   = "Imagens do trabalho ANAC-PDM (API de predicao)"
  format        = "DOCKER"
  labels        = var.labels

  cleanup_policies {
    id     = "manter-ultimas-5"
    action = "KEEP"
    most_recent_versions {
      keep_count = 5
    }
  }

  depends_on = [google_project_service.apis]
}

# ------------------------------------------------- Bucket do Dataflow -------

resource "google_storage_bucket" "dataflow" {
  name                        = "${var.project_id}-anac-dataflow"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true # so guarda temporarios e staging do Dataflow
  labels                      = var.labels

  lifecycle_rule {
    condition {
      age = 7
    }
    action {
      type = "Delete"
    }
  }
}
