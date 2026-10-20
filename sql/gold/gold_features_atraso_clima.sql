CREATE OR REPLACE TABLE `${PROJECT_ID}.tf_anac.tb_anac_gold_features_atraso_clima`
PARTITION BY dt_referencia
CLUSTER BY sg_empresa_icao, sg_icao_origem
OPTIONS (
  description = "GOLD v2/ML - a Gold de voo original, acrescida das features de meteorologia (METAR/IEM) mais proximas e anteriores ao horario previsto de partida. Tabela de validacao, nao de producao.",
  labels = [("camada", "gold"), ("dominio", "vra-metar"), ("uso", "ml")]
) AS
WITH voos AS (
  SELECT
    g.*,
    DATETIME_ADD(g.dt_partida_prevista, INTERVAL 3 HOUR) AS dt_partida_prevista_utc
  FROM `${PROJECT_ID}.tf_anac.tb_anac_gold_features_atraso` AS g
),
-- O join original casava so por desigualdade de tempo (sg_icao = sg_icao E
-- dt_observacao_utc dentro da janela de 3h) e travou por mais de 3h em
-- produção (BigQuery nao conseguiu tratar isso como hash join). Reescrito
-- para casar por IGUALDADE de (aerodromo, hora truncada): a janela de 3h
-- cabe em no maximo 4 horas truncadas (a hora do voo e as 3 anteriores — a
-- IEM reporta ~1 observacao por hora), e so essas 4 sao geradas por voo via
-- UNNEST. Isso forca um hash join por igualdade composta, muito mais barato
-- que o equivalente por desigualdade de timestamp. As condicoes de
-- desigualdade originais continuam no ON, garantindo a mesma correção;
-- a explosao em 4 horas candidatas e so para limitar o fan-out do join.
voos_com_horas_candidatas AS (
  SELECT v.*, hora_candidata
  FROM voos AS v,
  UNNEST([
    DATETIME_TRUNC(v.dt_partida_prevista_utc, HOUR),
    DATETIME_SUB(DATETIME_TRUNC(v.dt_partida_prevista_utc, HOUR), INTERVAL 1 HOUR),
    DATETIME_SUB(DATETIME_TRUNC(v.dt_partida_prevista_utc, HOUR), INTERVAL 2 HOUR),
    DATETIME_SUB(DATETIME_TRUNC(v.dt_partida_prevista_utc, HOUR), INTERVAL 3 HOUR)
  ]) AS hora_candidata
),
metar_com_hora AS (
  SELECT m.*, DATETIME_TRUNC(m.dt_observacao_utc, HOUR) AS hora_observacao
  FROM `${PROJECT_ID}.tf_anac.tb_anac_silver_metar` AS m
),
casado AS (
  SELECT
    v.* EXCEPT (dt_partida_prevista_utc, hora_candidata),
    m.nr_temperatura_c AS clima_temperatura_c,
    m.nr_umidade_relativa_pct AS clima_umidade_relativa_pct,
    m.nr_velocidade_vento_kmh AS clima_velocidade_vento_kmh,
    m.nr_rajada_vento_kmh AS clima_rajada_vento_kmh,
    m.nr_visibilidade_m AS clima_visibilidade_m,
    -- altimetro/QNH, nao pressao ao nivel do mar: mslp nunca e reportada
    -- fora dos EUA (ver sql/silver/create_table_silver_metar.sql)
    m.nr_altimetro_hpa AS clima_pressao_hpa,
    m.ds_cobertura_nuvens_1 AS clima_cobertura_nuvens,
    m.nr_altura_nuvens_1_m AS clima_altura_nuvens_m,
    m.ds_fenomenos AS clima_fenomenos,
    DATETIME_DIFF(v.dt_partida_prevista_utc, m.dt_observacao_utc, MINUTE) AS clima_minutos_desde_observacao
  FROM voos_com_horas_candidatas AS v
  LEFT JOIN metar_com_hora AS m
    ON m.sg_icao = v.sg_icao_origem
    AND m.hora_observacao = v.hora_candidata
    -- mesmas condicoes de sempre: METAR conhecido antes da partida (sem
    -- vazamento), dentro da janela real de 3h — a igualdade acima so limita
    -- o fan-out do join, a correção da janela continua sendo estas duas
    AND m.dt_observacao_utc <= v.dt_partida_prevista_utc
    AND m.dt_observacao_utc > DATETIME_SUB(v.dt_partida_prevista_utc, INTERVAL 3 HOUR)
  -- a explosao em 4 horas candidatas cria ate 4 linhas por voo; a maioria sem
  -- match (m nulo). QUALIFY reduz de volta a 1 linha por voo, preferindo a
  -- que casou (timestamp nao nulo) sobre as nulas
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY v.sg_empresa_icao, v.nr_voo, v.dt_referencia, v.sg_icao_origem, v.dt_partida_prevista
    ORDER BY m.dt_observacao_utc DESC NULLS LAST
  ) = 1
)
SELECT * FROM casado;

-- ============================================================================
-- Duas views sobre a MESMA tabela, no mesmo espirito de
-- vw_anac_gold_treino_m1/vw_anac_gold_avaliacao_m1 (sql/gold/gold_features_atraso.sql):
-- as 10 features do contrato + as novas features de clima, mais o alvo.
-- Usadas para o retreino de validacao do Estagio 4 (mdl_anac_m1_boosted_tree_clima),
-- nao para o modelo de producao.
-- ============================================================================

CREATE OR REPLACE VIEW `${PROJECT_ID}.tf_anac.vw_anac_gold_treino_m1_clima`
OPTIONS (
  description = "Corte de TREINO com clima: as 10 features do contrato + features de clima + alvo binario, excluindo os ultimos 60 dias."
) AS
SELECT
  sg_empresa_icao, sg_icao_origem, sg_icao_destino, cd_tipo_linha,
  sg_equipamento_icao, dia_semana, mes,
  nr_assentos_ofertados, hora_partida_prevista, duracao_prevista_min,
  clima_temperatura_c, clima_umidade_relativa_pct, clima_velocidade_vento_kmh,
  clima_rajada_vento_kmh, clima_visibilidade_m, clima_pressao_hpa,
  clima_cobertura_nuvens, clima_altura_nuvens_m, clima_fenomenos,
  atrasou
FROM `${PROJECT_ID}.tf_anac.tb_anac_gold_features_atraso_clima`
WHERE is_eval = FALSE;

CREATE OR REPLACE VIEW `${PROJECT_ID}.tf_anac.vw_anac_gold_avaliacao_m1_clima`
OPTIONS (
  description = "Corte de AVALIACAO com clima: mesmas features, ultimos 60 dias do periodo ingerido. Split temporal, nunca aleatorio."
) AS
SELECT
  sg_empresa_icao, sg_icao_origem, sg_icao_destino, cd_tipo_linha,
  sg_equipamento_icao, dia_semana, mes,
  nr_assentos_ofertados, hora_partida_prevista, duracao_prevista_min,
  clima_temperatura_c, clima_umidade_relativa_pct, clima_velocidade_vento_kmh,
  clima_rajada_vento_kmh, clima_visibilidade_m, clima_pressao_hpa,
  clima_cobertura_nuvens, clima_altura_nuvens_m, clima_fenomenos,
  atrasou
FROM `${PROJECT_ID}.tf_anac.tb_anac_gold_features_atraso_clima`
WHERE is_eval = TRUE;
