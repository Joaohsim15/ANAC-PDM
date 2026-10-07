-- ============================================================================
-- Streaming - tabela de destino dos eventos de voo publicados no Pub/Sub
-- Origem  : topico anac-voos -> pipeline Dataflow (streaming/dataflow)
-- Destino : tf_anac.tb_anac_stream_eventos
-- ----------------------------------------------------------------------------
-- Um registro por evento recebido. As colunas de feature seguem
-- schemas/features.json; o evento traz apenas o que e conhecido antes da
-- decolagem (nenhum horario real, situacao ou justificativa).
-- Particionada pela data do evento: a contagem da demo varre so o dia corrente.
-- ============================================================================

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.tf_anac.tb_anac_stream_eventos`
(
  event_id               STRING    NOT NULL OPTIONS (description = "Identificador unico do evento (UUID gerado pelo simulador)"),
  event_ts               TIMESTAMP NOT NULL OPTIONS (description = "Instante do evento, ja deslocado para o presente pelo simulador"),
  publish_ts             TIMESTAMP          OPTIONS (description = "Instante de publicacao no Pub/Sub"),
  ingest_ts              TIMESTAMP NOT NULL OPTIONS (description = "Instante em que o Dataflow processou o evento"),

  -- chaves do voo (nao sao features)
  sg_empresa_icao        STRING    NOT NULL,
  nr_voo                 STRING,
  dt_partida_prevista    DATETIME           OPTIONS (description = "Partida prevista, deslocada para o presente"),
  dt_partida_prevista_original DATETIME     OPTIONS (description = "Partida prevista no historico, antes do deslocamento"),

  -- features do contrato
  sg_icao_origem         STRING    NOT NULL,
  sg_icao_destino        STRING    NOT NULL,
  cd_tipo_linha          STRING    NOT NULL,
  sg_equipamento_icao    STRING    NOT NULL,
  dia_semana             STRING    NOT NULL,
  mes                    STRING    NOT NULL,
  nr_assentos_ofertados  INT64     NOT NULL,
  hora_partida_prevista  INT64     NOT NULL,
  duracao_prevista_min   INT64     NOT NULL,

  simulation_run_id      STRING             OPTIONS (description = "Execucao do simulador que gerou o evento")
)
PARTITION BY DATE(event_ts)
CLUSTER BY sg_empresa_icao, sg_icao_origem
OPTIONS (
  description = "STREAMING - eventos de voo recebidos via Pub/Sub e gravados pelo Dataflow.",
  labels = [("camada", "streaming"), ("dominio", "vra")]
);
