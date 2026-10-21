-- ============================================================================
-- Streaming - tabela de destino dos eventos de METAR publicados no Pub/Sub
-- Origem  : topico anac-metar -> pipeline Dataflow (streaming/dataflow, --domain metar)
-- Destino : tf_anac.tb_anac_stream_metar
-- ----------------------------------------------------------------------------
-- Um registro por observacao meteorologica recebida. As colunas de feature
-- seguem o recorte nullable (clima_*) de schemas/features.json. Os voos
-- seguem em batch (Medallion do T1).
-- Particionada pela data do evento: a contagem da demo varre so o dia corrente.
-- ============================================================================

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.tf_anac.tb_anac_stream_metar`
(
  event_id               STRING    NOT NULL OPTIONS (description = "Identificador unico do evento (UUID gerado pelo simulador)"),
  event_ts               TIMESTAMP NOT NULL OPTIONS (description = "Instante do evento, ja deslocado para o presente pelo simulador"),
  publish_ts             TIMESTAMP          OPTIONS (description = "Instante de publicacao no Pub/Sub"),
  ingest_ts              TIMESTAMP NOT NULL OPTIONS (description = "Instante em que o Dataflow processou o evento"),

  -- chaves da observacao (nao sao features)
  sg_icao                STRING    NOT NULL OPTIONS (description = "Estacao METAR de origem, codigo ICAO"),
  dt_observacao_utc      DATETIME           OPTIONS (description = "Observacao, deslocada para o presente"),
  dt_observacao_original DATETIME           OPTIONS (description = "Observacao no historico, antes do deslocamento"),

  -- features de clima do contrato (todas nullable: nem toda estacao reporta
  -- tudo em toda observacao)
  clima_temperatura_c         FLOAT64,
  clima_umidade_relativa_pct  FLOAT64,
  clima_velocidade_vento_kmh  FLOAT64,
  clima_rajada_vento_kmh      FLOAT64,
  clima_visibilidade_m        FLOAT64,
  clima_pressao_hpa           FLOAT64,
  clima_cobertura_nuvens      STRING,
  clima_altura_nuvens_m       FLOAT64,
  clima_fenomenos             STRING,

  simulation_run_id      STRING             OPTIONS (description = "Execucao do simulador que gerou o evento")
)
PARTITION BY DATE(event_ts)
CLUSTER BY sg_icao
OPTIONS (
  description = "STREAMING - observacoes de METAR recebidas via Pub/Sub e gravadas pelo Dataflow.",
  labels = [("camada", "streaming"), ("dominio", "metar")]
);
