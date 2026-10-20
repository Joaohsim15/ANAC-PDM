CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.tf_anac.tb_anac_predicoes_log`
(
  prediction_id          STRING    NOT NULL OPTIONS (description = "Identificador unico da chamada (UUID gerado pela API)"),
  predicted_em            TIMESTAMP NOT NULL OPTIONS (description = "Instante em que a API respondeu"),
  modelo                  STRING    NOT NULL OPTIONS (description = "Predictor que serviu a previsao (ex.: vertex:<endpoint>, bigquery:<modelo>)"),
  contrato_versao         INT64     NOT NULL,
  prob_atraso             FLOAT64   NOT NULL,

  -- chaves OPCIONAIS de reconciliacao (nao sao features - ver acima)
  nr_voo                  STRING,
  dt_referencia           DATE,
  dt_partida_prevista     DATETIME,

  -- features do contrato, para auditoria (o que foi enviado nesta chamada)
  sg_empresa_icao         STRING,
  sg_icao_origem          STRING,
  sg_icao_destino         STRING,
  cd_tipo_linha           STRING,
  sg_equipamento_icao     STRING,
  dia_semana              STRING,
  mes                     STRING,
  nr_assentos_ofertados   INT64,
  hora_partida_prevista   INT64,
  duracao_prevista_min    INT64,
  clima_temperatura_c         FLOAT64,
  clima_umidade_relativa_pct  FLOAT64,
  clima_velocidade_vento_kmh  FLOAT64,
  clima_rajada_vento_kmh      FLOAT64,
  clima_visibilidade_m        FLOAT64,
  clima_pressao_hpa           FLOAT64,
  clima_cobertura_nuvens      STRING,
  clima_altura_nuvens_m       FLOAT64,
  clima_fenomenos             STRING
)
PARTITION BY DATE(predicted_em)
CLUSTER BY modelo
OPTIONS (
  description = "Log de toda chamada ao /predict da API, usado para reconciliar com o resultado real do voo (sql/ml/reconciliar_predicoes.sql) e medir acuracia em producao.",
  labels = [("camada", "ml"), ("uso", "observabilidade")]
);
