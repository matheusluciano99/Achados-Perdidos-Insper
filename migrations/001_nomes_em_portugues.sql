RENAME TABLE collection TO retirada;

ALTER TABLE item
    RENAME COLUMN name TO nome,
    RENAME COLUMN description TO descricao,
    RENAME COLUMN found_location TO local_encontrado,
    RENAME COLUMN found_at TO encontrado_em;

ALTER TABLE retirada
    RENAME COLUMN item_id TO id_item,
    RENAME COLUMN collector_name TO nome_retirante,
    RENAME COLUMN collector_email TO email_retirante,
    RENAME COLUMN collected_at TO retirado_em;
