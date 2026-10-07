# Service accounts dedicadas com menor privilegio. Opcional (var.manage_iam):
# conceder papeis exige administrar IAM, o que o papel Editor nao permite.

locals {
  api_roles = [
    "roles/aiplatform.user", # chamar o endpoint do Vertex
    "roles/logging.logWriter",
  ]
  dataflow_roles = [
    "roles/dataflow.worker",
    "roles/pubsub.subscriber", # ler anac-voos-dataflow
    "roles/pubsub.publisher",  # escrever no dead-letter
    "roles/pubsub.viewer",
    "roles/bigquery.dataEditor", # gravar em tb_anac_stream_eventos
    "roles/bigquery.jobUser",
    "roles/storage.objectAdmin", # temp e staging no bucket do Dataflow
  ]
}

resource "google_service_account" "api" {
  count        = var.manage_iam ? 1 : 0
  account_id   = "anac-api"
  display_name = "ANAC-PDM - API de predicao (Cloud Run)"
}

resource "google_service_account" "dataflow" {
  count        = var.manage_iam ? 1 : 0
  account_id   = "anac-dataflow"
  display_name = "ANAC-PDM - pipeline de streaming (Dataflow)"
}

resource "google_project_iam_member" "api" {
  for_each = var.manage_iam ? toset(local.api_roles) : toset([])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.api[0].email}"
}

resource "google_project_iam_member" "dataflow" {
  for_each = var.manage_iam ? toset(local.dataflow_roles) : toset([])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.dataflow[0].email}"
}
