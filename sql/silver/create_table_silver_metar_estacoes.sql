CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.tf_anac.tb_anac_silver_metar_estacoes`
(
  sg_icao              STRING OPTIONS(description = 'Codigo ICAO da estacao'),
  nm_estacao           STRING OPTIONS(description = 'Nome da estacao/aerodromo'),
  ds_fuso_iana         STRING OPTIONS(description = 'Fuso horario IANA da estacao (ex.: America/Sao_Paulo), metadado da IEM. NAO usado na conversao de dt_partida_prevista para UTC: o VRA registra horario de Brasilia fixo para todos os aerodromos, nao hora local por aerodromo (P-09, CLAUDE.md), entao o join com a Silver de METAR usa um deslocamento fixo de 3h. Mantido so como metadado de referencia da estacao'),
  dt_cobertura_inicio  DATE OPTIONS(description = 'Inicio da cobertura historica da estacao na IEM'),
  dt_cobertura_fim     DATE OPTIONS(description = 'Fim da cobertura historica da estacao na IEM, NULL se ainda ativa'),
  bo_ativa             BOOL OPTIONS(description = 'Estacao reportando atualmente, conforme metadados da IEM')
)
OPTIONS (
  description = 'Metadados das estacoes da rede BR__ASOS (IEM) usadas no backfill de METAR — carregada por scripts/carregar_metar_estacoes.py a partir de metar/estacoes_br_asos.json, nao por query SQL (sao ~150 linhas de metadado, nao dado de observacao).'
);
