SELECT
  _batch_id,
  _ingested_at,
  COUNT(*) AS linhas,
  COUNT(DISTINCT _FILE_NAME) AS arquivos,
  COUNTIF(ds_codeshare IS NULL) AS linhas_sem_codeshare
FROM `${PROJECT_ID}.tf_anac.tb_anac_bronze`
GROUP BY 1, 2
ORDER BY 1, 2;
