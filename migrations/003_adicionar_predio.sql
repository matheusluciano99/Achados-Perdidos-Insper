-- Itens existentes precisam ter seus prédios reais identificados antes da alteração.
ALTER TABLE item
    ADD COLUMN predio INT NOT NULL AFTER descricao;
