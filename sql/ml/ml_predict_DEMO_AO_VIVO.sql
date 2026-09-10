-- ============================================================================
-- BigQuery ML - Predicao e explicabilidade: O BLOCO AO VIVO da apresentacao
-- Atende  : RF-018 - Aceite A1.10 - roteiro secao 14.1 (3:30-4:30)
-- ----------------------------------------------------------------------------
-- Este e o unico arquivo executado AO VIVO. Nada aqui treina nada: sao leituras
-- de segundos sobre um modelo que ja existe. O voo e montado na hora, a partir
-- de um horario previsto - todas as 10 features saem da PROGRAMACAO do voo,
-- nenhuma de dado pos-partida. E o que prova que o modelo do T1 continua valido
-- quando servido em tempo real no TF.
--
-- Nota de tipo: p.label e comparado como STRING para nao depender de o BigQuery
-- ML devolver o rotulo como INT64 ou como STRING nesta versao.
--
-- Rodar UM BLOCO POR VEZ: selecione o trecho e Ctrl+Enter.
-- ============================================================================

-- ------------------------ 1. Um voo inventado na hora (A1.10) -------------
-- Trocar livremente empresa, aeroportos, equipamento e horario durante a demo.
-- As tres features de calendario sao DERIVADAS do horario previsto na propria
-- query: o professor ve que nada foi pre-calculado.
WITH voo_inventado AS (
SELECT
'GLO'  AS sg_empresa_icao,      -- GOL
'SBGO' AS sg_icao_origem,       -- Goiania
'SBGR' AS sg_icao_destino,      -- Guarulhos
'N'    AS cd_tipo_linha,        -- nacional
'B738' AS sg_equipamento_icao,  -- 737-800
186    AS nr_assentos_ofertados,
EXTRACT(HOUR FROM partida_prevista)                       AS hora_partida_prevista,
CAST(EXTRACT(DAYOFWEEK FROM partida_prevista) AS STRING)  AS dia_semana,
CAST(EXTRACT(MONTH     FROM partida_prevista) AS STRING)  AS mes,
DATETIME_DIFF(chegada_prevista, partida_prevista, MINUTE) AS duracao_prevista_min
FROM (
SELECT
DATETIME '2024-12-20 18:30:00' AS partida_prevista,
DATETIME '2024-12-20 19:45:00' AS chegada_prevista
)
),
predicao AS (
SELECT
predicted_atrasou,
(SELECT p.prob FROM UNNEST(predicted_atrasou_probs) AS p
WHERE CAST(p.label AS STRING) = '1') AS prob_atraso
FROM ML.PREDICT(
MODEL `pdm-bia-2026.tf_anac.mdl_anac_m1_boosted_tree`,
TABLE voo_inventado
)
)
SELECT
predicted_atrasou     AS predicao,
ROUND(prob_atraso, 4) AS prob_atraso,
CASE
WHEN prob_atraso >= 0.70 THEN 'RISCO ALTO'
WHEN prob_atraso >= 0.40 THEN 'RISCO MEDIO'
ELSE                          'RISCO BAIXO'
END                   AS faixa_de_risco
FROM predicao;

-- ------------------ 2. Por que? SHAP nativo (RF-018, secao 14.2) ----------
-- Os tres atributos que mais empurraram a probabilidade, para cima ou para
-- baixo. Trinta segundos de demo que transformam um numero em uma decisao
-- justificavel - e a razao de a persona pedir explicabilidade (secao 4.2).
-- Medido em 10/09/2026: mes +0,131 - hora_partida_prevista +0,089 -
-- nr_assentos_ofertados +0,067. Dezembro, fim de tarde, aeronave grande.
WITH voo_inventado AS (
SELECT
'GLO' AS sg_empresa_icao, 'SBGO' AS sg_icao_origem, 'SBGR' AS sg_icao_destino,
'N'   AS cd_tipo_linha,   'B738' AS sg_equipamento_icao,
186   AS nr_assentos_ofertados,
18    AS hora_partida_prevista,
'6'   AS dia_semana,      '12'   AS mes,
75    AS duracao_prevista_min
)
SELECT
ROUND(prediction_value, 5)       AS score_bruto,
atribuicao.feature               AS atributo,
ROUND(atribuicao.attribution, 5) AS empurrao
FROM ML.EXPLAIN_PREDICT(
MODEL `pdm-bia-2026.tf_anac.mdl_anac_m1_boosted_tree`,
TABLE voo_inventado,
STRUCT(3 AS top_k_features)
), UNNEST(top_feature_attributions) AS atribuicao
ORDER BY ABS(empurrao) DESC;

-- --------------- 3. Ranking operacional do dia (cenario CU-01/CU-03) ------
-- O uso real da persona: nao "este voo atrasa?", e "quais dos voos de hoje
-- merecem atencao antecipada?". As colunas extras passadas ao ML.PREDICT
-- atravessam a funcao intactas - nao entram no vetor de features, mas voltam
-- na saida, o que permite comparar predicao com o que de fato aconteceu.
SELECT
sg_empresa_icao,
nr_voo,
CONCAT(sg_icao_origem, ' -> ', sg_icao_destino) AS rota,
dt_partida_prevista,
ROUND((SELECT p.prob FROM UNNEST(predicted_atrasou_probs) AS p
WHERE CAST(p.label AS STRING) = '1'), 4)        AS prob_atraso,
atrasou                                         AS atrasou_de_fato,
atraso_partida_minutos                          AS atraso_real_min
FROM ML.PREDICT(
MODEL `pdm-bia-2026.tf_anac.mdl_anac_m1_boosted_tree`,
(
SELECT
-- as 10 features do contrato
sg_empresa_icao, sg_icao_origem, sg_icao_destino, cd_tipo_linha,
sg_equipamento_icao, dia_semana, mes,
nr_assentos_ofertados, hora_partida_prevista, duracao_prevista_min,
-- carona para exibicao (ignoradas pelo modelo)
nr_voo, dt_partida_prevista, atrasou, atraso_partida_minutos
FROM `pdm-bia-2026.tf_anac.tb_anac_gold_features_atraso`
WHERE dt_referencia = DATE '2024-12-20'
)
)
ORDER BY prob_atraso DESC
LIMIT 15;