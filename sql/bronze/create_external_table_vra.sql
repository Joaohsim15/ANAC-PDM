CREATE OR REPLACE EXTERNAL TABLE `pdm-bia-2026.tf_anac.tb_vra_bronze`
(
  sg_empresa_icao       STRING OPTIONS(description = 'Código ICAO da companhia operadora'),
  nm_empresa            STRING OPTIONS(description = 'Razão social da companhia'),
  nr_voo                STRING OPTIONS(description = 'Número do voo atribuído pela companhia'),
  cd_di                 STRING OPTIONS(description = 'Dígito identificador do tipo de operação'),
  cd_tipo_linha         STRING OPTIONS(description = 'Natureza da linha: N nacional, I internacional, C cargueiro, G -'),
  sg_equipamento_icao   STRING OPTIONS(description = 'Modelo da aeronave (ex.: B77W, A20N)'),
  nr_assentos_ofertados STRING OPTIONS(description = 'Assentos ofertados'),
  sg_icao_origem        STRING OPTIONS(description = 'Aeroporto de partida'),
  nm_aerodromo_origem   STRING OPTIONS(description = 'Nome do aeroporto de partida'),
  dt_partida_prevista   STRING OPTIONS(description = 'Horário programado de partida'),
  dt_partida_real       STRING OPTIONS(description = 'Horário efetivo de partida — proibido como feature'),
  sg_icao_destino       STRING OPTIONS(description = 'Aeroporto de chegada'),
  nm_aerodromo_destino  STRING OPTIONS(description = 'Nome do aeroporto de chegada'),
  dt_chegada_prevista   STRING OPTIONS(description = 'Horário programado de chegada'),
  dt_chegada_real       STRING OPTIONS(description = 'Horário efetivo de chegada — proibido'),
  ds_situacao_voo       STRING OPTIONS(description = 'REALIZADO ou CANCELADO — proibido'),
  ds_justificativa      STRING OPTIONS(description = 'Motivo do atraso — vem vazio na base observada — proibido'),
  dt_referencia         STRING OPTIONS(description = 'Data de referência do voo'),
  ds_situacao_partida   STRING OPTIONS(description = 'Faixa oficial ANAC do atraso de partida — proibido como feature, só para derivar o rótulo'),
  ds_situacao_chegada   STRING OPTIONS(description = 'Idem, para a chegada — proibido'),
  ds_codeshare          STRING OPTIONS(description = 'Indicador de voo codeshare — só presente a partir de out/2022; NULL nos arquivos sem a 21ª coluna')
)
WITH PARTITION COLUMNS
OPTIONS (
  format = 'CSV',
  uris = ['gs://dados-anac-vra/bronze/vra/raw/*'],
  hive_partition_uri_prefix = 'gs://dados-anac-vra/bronze/vra/raw/',
  require_hive_partition_filter = false,
  field_delimiter = ';',
  skip_leading_rows = 1,
  encoding = 'ISO-8859-1',
  allow_jagged_rows = true,
  description = 'Camada Bronze do VRA/ANAC. External table sobre o GCS, todos os campos STRING, append-only. Particionada por _ingested_at/_batch_id via layout Hive. allow_jagged_rows=true por causa da coluna Codeshare, ausente antes de out/2022.'
);
