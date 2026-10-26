# Achados & Perdidos Insper

API REST de achados e perdidos do campus Insper, desenvolvida como projeto individual da disciplina de **Megadados**, no quinto semestre de Ciência da Computação.

## Endpoints

As rotas de itens e retiradas exigem autenticação. A raiz, as rotas de login e a documentação são públicas.

`GET /` retorna:

```json
{"mensagem": "Achados & Perdidos API"}
```

### Itens

O cadastro de itens encontrados oferece as seguintes operações:

| Método | Rota | Operação | Sucesso |
| --- | --- | --- | --- |
| POST | `/itens` | Cadastrar item | 201 |
| GET | `/itens` | Listar itens | 200 |
| GET | `/itens/{id_item}` | Consultar item | 200 |
| PUT | `/itens/{id_item}` | Atualizar todos os dados do item | 200 |
| DELETE | `/itens/{id_item}` | Excluir item | 204, sem corpo |

A listagem aceita `deslocamento` (padrão 0) e `limite` (padrão e máximo 100), com resultados ordenados por identificador. Itens inexistentes retornam 404, e dados inválidos retornam 422.

Exemplo de corpo para cadastro e atualização completa:

```json
{
  "nome": "Garrafa de água",
  "descricao": "Garrafa azul com tampa preta",
  "local_encontrado": "Biblioteca",
  "encontrado_em": "2026-10-25T10:30:00"
}
```

Todos esses campos são obrigatórios. Os textos têm espaços removidos das extremidades e não podem ficar vazios. Os limites são 100 caracteres para `nome`, 1000 para `descricao` e 200 para `local_encontrado`. A data usa o horário local de São Paulo, sem indicação de fuso horário. O banco gera o `id`, e a API rejeita campos adicionais nas requisições.

O cadastro vincula o item ao usuário autenticado. A resposta inclui `id_usuario`, definido pela API e preservado nas atualizações.

### Retiradas

| Método | Rota | Operação | Sucesso |
| --- | --- | --- | --- |
| POST | `/retiradas` | Registrar retirada | 201 |
| GET | `/retiradas` | Listar retiradas | 200 |
| GET | `/retiradas/{id_retirada}` | Consultar retirada | 200 |
| PUT | `/retiradas/{id_retirada}` | Atualizar todos os dados da retirada | 200 |
| DELETE | `/retiradas/{id_retirada}` | Excluir retirada | 204, sem corpo |

Exemplo de corpo para registro e atualização completa:

```json
{
  "id_item": 1,
  "retirado_em": "2026-10-25T14:00:00"
}
```

Os dois campos são obrigatórios. A data segue o mesmo formato e horário local dos itens. O banco gera o `id`, e campos adicionais são rejeitados. A retirada é vinculada ao usuário autenticado que levou o objeto; a resposta inclui seu `id_usuario`, preservado nas atualizações. Nome e e-mail dessa pessoa são armazenados em `usuario`.

A listagem usa os mesmos parâmetros `deslocamento` e `limite` dos itens, com resultados ordenados por identificador. Retiradas ou itens inexistentes retornam 404; dados inválidos retornam 422.

Cada retirada deve apontar para um item existente, e cada item pode ter no máximo uma retirada. Essas regras são garantidas por chave estrangeira e restrição de unicidade no MySQL. Tentar registrar duas retiradas para o mesmo item retorna 409. A atualização pode vincular a retirada a outro item existente que ainda não tenha retirada.

Um item com retirada registrada não pode ser excluído: a API retorna 409. Excluir a retirada mantém o item e permite registrar uma nova retirada ou excluir o item.

## Autenticação

O login usa um código enviado ao e-mail institucional. São aceitos apenas os domínios `al.insper.edu.br` e `insper.edu.br`. Uma conta Gmail configurada no servidor envia as mensagens.

| Método | Rota | Operação |
| --- | --- | --- |
| POST | `/auth/solicitar-codigo` | Enviar código ao e-mail informado |
| POST | `/auth/verificar-codigo` | Confirmar o código e receber um token de acesso |

Solicite o código com:

```json
{"email": "maria@al.insper.edu.br"}
```

Depois, confirme o código recebido. No primeiro acesso, informe também o nome:

```json
{
  "email": "maria@al.insper.edu.br",
  "codigo": "123456",
  "nome": "Maria Silva"
}
```

O usuário só é cadastrado após a confirmação. Nos próximos acessos, `nome` pode ser omitido; o login preserva o nome já cadastrado. A resposta contém `token_acesso`, `tipo_token` (`bearer`) e `expira_em`, em UTC. O token vale por uma hora.

O código tem seis dígitos, vale por dez minutos e permite até cinco tentativas incorretas. Cada e-mail pode solicitar um código a cada 60 segundos; um reenvio substitui o anterior. Códigos utilizados, expirados ou bloqueados por tentativas não permitem entrar. O banco armazena somente um hash HMAC-SHA256 do código, vinculado ao e-mail e à chave da aplicação.

Para acessar as rotas protegidas, envie `Authorization: Bearer <token_acesso>`. A API valida a assinatura JWT com HS256, a validade, o emissor `achados-perdidos-insper`, o destinatário `achados-perdidos-api` e o e-mail no campo `sub`, que deve corresponder a um usuário cadastrado. O Swagger permite informar o token no botão **Authorize**.

Dados de login inválidos, incluindo e-mails de outros domínios, retornam 422. Código inválido ou expirado retorna 401; solicitar outro código antes do intervalo retorna 429 com `Retry-After`. Falhas de configuração ou envio retornam 503. Nas rotas protegidas, token ausente ou inválido retorna 401, e e-mail de outro domínio retorna 403.

### Configuração do envio

Configure `AUTH_SECRET_KEY` no `.env` com uma chave aleatória de pelo menos 32 caracteres. Para gerar uma chave localmente:

```bash
uv run python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Preencha também:

```dotenv
SMTP_USERNAME=seu.email@gmail.com
SMTP_PASSWORD=sua_senha_de_app
```

O envio usa `smtp.gmail.com`, porta 587 e STARTTLS com validação do certificado. Ative a verificação em duas etapas na conta Google e gere uma [senha de app](https://support.google.com/accounts/answer/185833?hl=pt-BR) para `SMTP_PASSWORD`. O remetente é `SMTP_USERNAME`; o destinatário é sempre o e-mail institucional solicitado no login. As credenciais ficam no `.env`, ignorado pelo Git.

## Modelo de dados

Os modelos, as tabelas e os campos JSON usam nomes em português.

![Modelo relacional gerado no MySQL Workbench](docs/modelo-relacional.png)

A tabela `usuario` armazena o `id`, gerado pelo banco, o `nome`, obrigatório e com limite de 100 caracteres, e o `email`, obrigatório e único. O modelo remove espaços nas extremidades do nome, rejeita nomes vazios, valida o e-mail institucional e o converte para minúsculas.

`item.id_usuario` identifica quem cadastrou o pertence encontrado. `retirada.id_usuario` identifica quem retirou o pertence, enquanto `retirada.id_item` aponta para o item. As chaves estrangeiras impedem referências a usuários inexistentes e a exclusão de usuários que tenham itens ou retiradas vinculados. Todos os usuários autenticados podem gerenciar os registros.

A tabela `codigo_login` mantém um registro por e-mail, com o hash do código, horário de envio, expiração e quantidade de tentativas incorretas. Seus horários são armazenados em UTC. Ela também atende o primeiro acesso, antes de existir um usuário cadastrado.

## Tecnologias

- Python 3.14
- FastAPI e Uvicorn
- SQLModel e PyMySQL
- pydantic-settings para leitura das variáveis de ambiente
- MySQL 8.4 via Docker Compose
- uv para gerenciamento de dependências

## Execução

Com Python 3.14, uv e Docker Compose instalados, prepare o ambiente:

```bash
uv sync
cp .env.example .env
```

Edite o `.env` e substitua as senhas de exemplo em `MYSQL_PASSWORD` e `MYSQL_ROOT_PASSWORD`. O arquivo `.env` é ignorado pelo Git.

Inicie o banco e a API:

```bash
docker compose up -d --wait mysql
uv run uvicorn app.main:app --reload
```

O mesmo comando de inicialização do servidor está disponível por meio de `just run`.

Na inicialização, a API cria as tabelas de itens, retiradas, usuários e códigos de login caso elas ainda não existam. A documentação interativa está disponível em `http://127.0.0.1:8000/docs`.

Para atualizar um banco de desenvolvimento antigo, com `item` e `collection` vazias, os scripts em `migrations/` devem ser executados uma vez, na ordem numérica, antes de iniciar esta versão da API. Eles renomeiam as tabelas e colunas e adicionam os vínculos com usuários. Bancos com registros existentes precisam ter seus usuários identificados antes dessa alteração. A criação automática de tabelas não atualiza estruturas já existentes.

O MySQL fica disponível em `127.0.0.1:3306`. A porta pode ser alterada em `MYSQL_PORT`. Os dados são armazenados no volume `mysql_data` e preservados ao parar o contêiner com `docker compose stop mysql`.

As credenciais do `.env` são aplicadas na primeira inicialização do volume. Alterar o arquivo depois disso não altera os usuários e senhas já criados no MySQL.

## Testes

Com o MySQL iniciado, execute:

```bash
uv run python -m unittest discover -s tests -v
```

Os testes verificam a conexão com o MySQL, os CRUDs de itens e retiradas, paginação, validação de dados, integridade dos vínculos, conflitos, autenticação e acesso à documentação. O fluxo de login cobre envio SMTP simulado, cadastro após confirmação, expiração, tentativas, reenvio, falhas de envio e confirmação concorrente do mesmo código.

## Uso de IA

O OpenAI Codex foi utilizado para interpretar os requisitos do projeto, gerar códigos e editar a documentação.
