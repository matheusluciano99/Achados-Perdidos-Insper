# Achados & Perdidos Insper

API REST de achados e perdidos do campus Insper, desenvolvida como projeto individual da disciplina de **Megadados**, no quinto semestre de Ciência da Computação.

## Endpoint

`GET /` retorna:

```json
{"message": "Achados & Perdidos API"}
```

## Tecnologias

- Python 3.14
- FastAPI e Uvicorn
- uv para gerenciamento de dependências

## Execução

```bash
uv sync
uv run uvicorn app.main:app --reload
```

O mesmo comando de inicialização do servidor está disponível por meio de `just run`.

## Uso de IA

O OpenAI Codex foi utilizado para interpretar os requisitos do projeto, gerar alguns códigos e editar a documentação.
