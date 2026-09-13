SELECT
  _batch_id,
  _ingested_at,
  COUNT(*) AS linhas,
  COUNT(DISTINCT _FILE_NAME) AS arquivos,
  COUNTIF(ds_codeshare IS NULL) AS linhas_sem_codeshare
FROM `pdm-bia-2026.tf_anac.tb_vra_bronze`
GROUP BY 1, 2
ORDER BY 1, 2;
