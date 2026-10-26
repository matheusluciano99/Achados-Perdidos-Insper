-- Requer item e retirada vazias. Registros antigos precisam de seus usuários
-- identificados antes de adicionar vínculos obrigatórios e remover dados do retirante.
CREATE TABLE IF NOT EXISTS usuario (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    email VARCHAR(254) NOT NULL UNIQUE
);

ALTER TABLE item
    ADD COLUMN id_usuario INT NOT NULL,
    ADD CONSTRAINT fk_item_usuario FOREIGN KEY (id_usuario)
        REFERENCES usuario (id) ON DELETE RESTRICT;

ALTER TABLE retirada
    ADD COLUMN id_usuario INT NOT NULL,
    ADD CONSTRAINT fk_retirada_usuario FOREIGN KEY (id_usuario)
        REFERENCES usuario (id) ON DELETE RESTRICT,
    DROP COLUMN nome_retirante,
    DROP COLUMN email_retirante;
