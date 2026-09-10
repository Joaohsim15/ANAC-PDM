-- Valida a contagem de linhas da Bronze por lote de ingestão.
--
-- Regra 6 do CLAUDE.md / RF-001c: sucesso no upload não é prova de dado
-- completo — toda ingestão precisa ter a contagem conferida. O resultado
-- desta query deve bater com o total de `linhas_dados` somado no manifest
-- gravado por scripts/ingest_bronze_vra_to_gcs.py em
-- gs://dados-anac-vra/bronze/vra/manifest/ (comparação feita na última
-- célula de raw_to_bronze_vra.ipynb).
--
-- `linhas_sem_codeshare` mostra quantas linhas vieram dos arquivos de 20
-- colunas (sem a 21ª coluna Codeshare) — serve de conferência visual de que
-- allow_jagged_rows preencheu ds_codeshare como NULL do jeito esperado.
SELECT
  _batch_id,
  _ingested_at,
  COUNT(*) AS linhas,
  COUNT(DISTINCT _FILE_NAME) AS arquivos,
  COUNTIF(ds_codeshare IS NULL) AS linhas_sem_codeshare
FROM `pdm-bia-2026.tf_anac.tb_vra_bronze`
GROUP BY 1, 2
ORDER BY 1, 2;
