output "topic" {
  value = google_pubsub_topic.voos.name
}

output "dead_letter_topic" {
  value = google_pubsub_topic.voos_dlq.name
}

output "subscription" {
  value = google_pubsub_subscription.voos_dataflow.name
}

output "image_repository" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.anac.repository_id}"
}

output "dataflow_bucket" {
  value = google_storage_bucket.dataflow.name
}

output "api_service_account" {
  value = var.manage_iam ? google_service_account.api[0].email : null
}

output "dataflow_service_account" {
  value = var.manage_iam ? google_service_account.dataflow[0].email : null
}
