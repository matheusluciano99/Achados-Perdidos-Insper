import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient
from jwt import encode
from sqlmodel import Session

from app import auth
from app.database import engine, get_session
from app.main import app
from app.models.user import Usuario


class AutenticacaoTests(unittest.TestCase):
    def setUp(self):
        self.segredo = "chave-exclusiva-dos-testes-" * 4
        config = auth.AuthSettings(_env_file=None, auth_secret_key=self.segredo)
        self.enterContext(patch.object(auth, "config_auth", config))
        self.client = self.enterContext(TestClient(app))
        connection = self.enterContext(engine.connect())
        transaction = connection.begin()
        self.addCleanup(transaction.rollback)
        session = self.enterContext(
            Session(bind=connection, join_transaction_mode="create_savepoint")
        )
        self.aluno = Usuario.model_validate({"nome": "Maria Silva", "email": "aluno@al.insper.edu.br"})
        self.professor = Usuario.model_validate({"nome": "João Santos", "email": "professor@insper.edu.br"})
        session.add_all([self.aluno, self.professor])
        session.flush()
        app.dependency_overrides[get_session] = lambda: session
        self.addCleanup(app.dependency_overrides.clear)
        agora = datetime.now(UTC)
        self.claims = {
            "sub": "aluno@al.insper.edu.br",
            "iss": "achados-perdidos-insper",
            "aud": "achados-perdidos-api",
            "iat": agora - timedelta(seconds=10),
            "nbf": agora - timedelta(seconds=10),
            "exp": agora + timedelta(hours=1),
        }

    def headers(self, claims):
        token = encode(claims, self.segredo, algorithm="HS256")
        return {"Authorization": f"Bearer {token}"}

    def test_all_data_routes_require_authentication(self):
        for route in ("/itens", "/retiradas"):
            for method, path in (
                ("GET", route), ("POST", route), ("GET", route + "/1"),
                ("PUT", route + "/1"), ("DELETE", route + "/1"),
            ):
                with self.subTest(method=method, path=path):
                    response = self.client.request(method, path, json={})
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")

    def test_both_institutional_domains_are_accepted(self):
        for email in ("aluno@al.insper.edu.br", "professor@insper.edu.br", "ALUNO@AL.INSPER.EDU.BR"):
            response = self.client.get("/itens", headers=self.headers(self.claims | {"sub": email}))
            self.assertEqual(response.status_code, 200)

    def test_other_domains_are_forbidden(self):
        for email in ("aluno@gmail.com", "aluno@insper.edu.br.evil.com", "aluno@outroinsper.edu.br"):
            response = self.client.get("/itens", headers=self.headers(self.claims | {"sub": email}))
            self.assertEqual(response.status_code, 403)

    def test_unregistered_user_is_rejected(self):
        response = self.client.get("/itens", headers=self.headers(
            self.claims | {"sub": "nao.cadastrado@al.insper.edu.br"}
        ))
        self.assertEqual(response.status_code, 401)

    def test_item_and_withdrawal_use_authenticated_users(self):
        aluno_headers = self.headers(self.claims)
        professor_headers = self.headers(self.claims | {"sub": self.professor.email})
        dados_item = {
            "nome": "Garrafa", "descricao": "Garrafa azul",
            "predio": 1,
            "local_encontrado": "Biblioteca", "encontrado_em": "2026-10-25T10:30:00",
        }
        response = self.client.post("/itens", json=dados_item, headers=aluno_headers)
        self.assertEqual(response.status_code, 201)
        item = response.json()
        self.assertEqual(item["id_usuario"], self.aluno.id)

        dados_retirada = {"id_item": item["id"], "retirado_em": "2026-10-25T14:00:00"}
        response = self.client.post("/retiradas", json=dados_retirada, headers=professor_headers)
        self.assertEqual(response.status_code, 201)
        retirada = response.json()
        self.assertEqual(retirada["id_usuario"], self.professor.id)

        response = self.client.put(f"/itens/{item['id']}", json=dados_item, headers=professor_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id_usuario"], self.aluno.id)
        response = self.client.put(
            f"/retiradas/{retirada['id']}", json=dados_retirada, headers=aluno_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id_usuario"], self.professor.id)

        for path, dados, headers, id_usuario in (
            ("/itens", dados_item, aluno_headers, self.professor.id),
            ("/retiradas", dados_retirada, professor_headers, self.aluno.id),
        ):
            with self.subTest(path=path):
                response = self.client.post(path, json=dados | {"id_usuario": id_usuario}, headers=headers)
                self.assertEqual(response.status_code, 422)

    def test_invalid_claims_are_rejected(self):
        agora = datetime.now(UTC)
        for changes in (
            {"sub": "email-invalido"}, {"sub": ["aluno@al.insper.edu.br"]},
            {"iss": "outro-emissor"}, {"aud": "outra-api"},
            {"exp": agora - timedelta(seconds=1)},
            {"nbf": agora + timedelta(minutes=1)},
            {"iat": agora + timedelta(minutes=1)},
        ):
            with self.subTest(claim=list(changes)):
                response = self.client.get("/itens", headers=self.headers(self.claims | changes))
                self.assertEqual(response.status_code, 401)
        for field in self.claims:
            claims = self.claims.copy()
            claims.pop(field)
            with self.subTest(missing=field):
                self.assertEqual(self.client.get("/itens", headers=self.headers(claims)).status_code, 401)

    def test_bad_signatures_and_algorithms_are_rejected(self):
        tokens = (
            encode(self.claims, "outra-chave-dos-testes-" * 4, algorithm="HS256"),
            encode(self.claims, self.segredo, algorithm="HS512"),
            encode(self.claims, None, algorithm="none"),
            "token.invalido.teste",
        )
        for token in tokens:
            response = self.client.get("/itens", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(response.status_code, 401)

    def test_missing_configuration_denies_access(self):
        config = auth.AuthSettings(_env_file=None, auth_secret_key=None)
        with patch.object(auth, "config_auth", config):
            response = self.client.get("/itens", headers=self.headers(self.claims))
        self.assertEqual(response.status_code, 503)

    def test_public_routes_and_documentation(self):
        for path in ("/", "/docs", "/openapi.json"):
            self.assertEqual(self.client.get(path).status_code, 200)
        schema = self.client.get("/openapi.json").json()
        self.assertEqual(schema["components"]["securitySchemes"]["AcessoInsper"]["scheme"], "bearer")
        for route in ("/itens", "/retiradas"):
            self.assertEqual(schema["paths"][route]["get"]["security"], [{"AcessoInsper": []}])
