variable "project_id" {
  description = "Projeto GCP do trabalho (definido em terraform.tfvars, fora do Git)"
  type        = string
}

variable "region" {
  description = "Regiao unica dos servicos regionais. us-central1: o dataset esta em US e o registro BQML -> Vertex cai nessa regiao"
  type        = string
  default     = "us-central1"
}

variable "dataset_id" {
  description = "Dataset do BigQuery que recebe a tabela de eventos"
  type        = string
  default     = "tf_anac"
}

variable "manage_iam" {
  description = <<-EOT
    Cria service accounts dedicadas (anac-api, anac-dataflow) e concede os papeis
    minimos. Exige permissao de administrar IAM no projeto (papel Owner ou
    Project IAM Admin). Com false, Cloud Run e Dataflow usam a conta padrao do
    Compute Engine.
  EOT
  type        = bool
  default     = false
}

variable "labels" {
  description = "Rotulos aplicados aos recursos do trabalho"
  type        = map(string)
  default = {
    projeto = "anac-pdm"
    entrega = "t2"
  }
}
