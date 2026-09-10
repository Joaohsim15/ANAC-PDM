-- ============================================================================
-- Camada GOLD - Tabela de features para Machine Learning
-- Projeto : pdm-bia-2026 - Dataset: tf_anac
-- Origem  : tf_anac.tb_anac_silver
-- Destino : tf_anac.tb_anac_gold_features_atraso
-- ============================================================================

CREATE OR REPLACE TABLE `pdm-bia-2026.tf_anac.tb_anac_gold_features_atraso`
PARTITION BY dt_referencia
CLUSTER BY sg_empresa_icao, sg_icao_origem
OPTIONS (
description = "GOLD/ML - um registro por etapa de voo realizada: as 10 features, os alvos atrasou e faixa_atraso, e o flag is_eval.",
labels = [("camada", "gold"), ("dominio", "vra"), ("uso", "ml")]
) AS
WITH
limites AS (
SELECT MAX(dt_referencia) AS dt_max_base
FROM `pdm-bia-2026.tf_anac.tb_anac_silver`
),
base AS (
SELECT
-- chaves e rastreabilidade (NAO sao features)
s.dt_referencia, s.sg_empresa_icao, s.nr_voo, s.dt_partida_prevista,
-- features categoricas
s.sg_icao_origem, s.sg_icao_destino, s.cd_tipo_linha, s.sg_equipamento_icao,
-- features numericas
s.nr_assentos_ofertados,
EXTRACT(HOUR FROM s.dt_partida_prevista) AS hora_partida_prevista,
DATETIME_DIFF(s.dt_chegada_prevista, s.dt_partida_prevista, MINUTE) AS duracao_prevista_min,
-- features derivadas do calendario
CAST(EXTRACT(DAYOFWEEK FROM s.dt_partida_prevista) AS STRING) AS dia_semana, -- 1=domingo
CAST(EXTRACT(MONTH FROM s.dt_partida_prevista) AS STRING) AS mes,
-- insumo do rotulo (pos-partida: proibido como feature)
s.atraso_partida_minutos
FROM `pdm-bia-2026.tf_anac.tb_anac_silver` AS s
WHERE s.dt_partida_prevista IS NOT NULL
AND s.dt_chegada_prevista IS NOT NULL
AND s.atraso_partida_minutos IS NOT NULL
)
SELECT
b.dt_referencia, b.sg_empresa_icao, b.nr_voo, b.dt_partida_prevista,
b.sg_icao_origem, b.sg_icao_destino, b.cd_tipo_linha, b.sg_equipamento_icao,
b.nr_assentos_ofertados, b.hora_partida_prevista, b.dia_semana, b.mes,
b.duracao_prevista_min,
b.atraso_partida_minutos,
-- ALVO 1: atraso de partida acima de 15 min
IF(b.atraso_partida_minutos > 15, 1, 0) AS atrasou,
-- ALVO 2: faixa de duracao.
-- NULO quando atrasou = 0 - e essa ausencia de classe no horario que define
-- o treino condicional de M2 (restrito a atrasou = 1).
CASE
WHEN b.atraso_partida_minutos <= 15 THEN NULL
WHEN b.atraso_partida_minutos <= 30 THEN '15_30'
WHEN b.atraso_partida_minutos <= 60 THEN '30_60'
WHEN b.atraso_partida_minutos <= 120 THEN '60_120'
ELSE '120_mais'
END AS faixa_atraso,
-- particao temporal de avaliacao: ultimos 60 dias da base
b.dt_referencia > DATE_SUB(l.dt_max_base, INTERVAL 60 DAY) AS is_eval
FROM base AS b
CROSS JOIN limites AS l
WHERE b.duracao_prevista_min BETWEEN 10 AND 1200;

-- ============================================================================
-- Duas views sobre a MESMA tabela. Nao sao camadas novas: sao o corte de
-- treino e o de avaliacao, com as 10 features do contrato enumeradas.
--
-- Por que existem: o CREATE MODEL vira um SELECT * sobre a view, entao as
-- colunas pos-partida (atraso_partida_minutos, faixa_atraso) ficam
-- estruturalmente fora do vetor de features.
-- ============================================================================

CREATE OR REPLACE VIEW `pdm-bia-2026.tf_anac.vw_anac_gold_treino_m1`
OPTIONS (
description = "Corte de TREINO: as 10 features do contrato + alvo binario, excluindo os ultimos 60 dias."
) AS
SELECT
sg_empresa_icao, sg_icao_origem, sg_icao_destino, cd_tipo_linha,
sg_equipamento_icao, dia_semana, mes,
nr_assentos_ofertados, hora_partida_prevista, duracao_prevista_min,
atrasou
FROM `pdm-bia-2026.tf_anac.tb_anac_gold_features_atraso`
WHERE is_eval = FALSE;

CREATE OR REPLACE VIEW `pdm-bia-2026.tf_anac.vw_anac_gold_avaliacao_m1`
OPTIONS (
description = "Corte de AVALIACAO: mesmas 10 features, ultimos 60 dias do periodo ingerido. Split temporal, nunca aleatorio."
) AS
SELECT
sg_empresa_icao, sg_icao_origem, sg_icao_destino, cd_tipo_linha,
sg_equipamento_icao, dia_semana, mes,
nr_assentos_ofertados, hora_partida_prevista, duracao_prevista_min,
atrasou
FROM `pdm-bia-2026.tf_anac.tb_anac_gold_features_atraso`
WHERE is_eval = TRUE;