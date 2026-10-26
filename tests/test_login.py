from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from jwt import decode
from sqlmodel import Session, delete, select

from app import auth
from app.database import engine, get_session
from app.main import app
from app.models.auth import CodigoLogin
from app.models.user import Usuario


class LoginTests(unittest.TestCase):
    def setUp(self):
        self.segredo = "chave-exclusiva-dos-testes-" * 4
        config = auth.AuthSettings(
            _env_file=None, auth_secret_key=self.segredo,
            smtp_username="remetente@gmail.com",
            smtp_password="senha-exclusiva-dos-testes",
        )
        self.enterContext(patch.object(auth, "config_auth", config))
        self.smtp_factory = self.enterContext(patch("app.auth.smtplib.SMTP"))
        self.smtp = self.smtp_factory.return_value.__enter__.return_value
        self.enterContext(patch("app.routes.auth.secrets.randbelow", return_value=123))
        self.client = self.enterContext(TestClient(app))
        connection = self.enterContext(engine.connect())
        transaction = connection.begin()
        self.addCleanup(transaction.rollback)
        self.session = self.enterContext(
            Session(bind=connection, join_transaction_mode="create_savepoint")
        )
        app.dependency_overrides[get_session] = lambda: self.session
        self.addCleanup(app.dependency_overrides.clear)
        self.email = "login.teste@al.insper.edu.br"

    def solicitar(self, email=None):
        return self.client.post("/auth/solicitar-codigo", json={"email": email or self.email})

    def confirmar(self, codigo="000123", nome="Maria Silva", email=None):
        return self.client.post("/auth/verificar-codigo", json={
            "email": email or self.email, "codigo": codigo, "nome": nome,
        })

    def test_first_login_sends_email_creates_user_and_issues_valid_token(self):
        response = self.solicitar(self.email.upper())
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("000123", response.text)
        self.assertIsNone(self.session.exec(select(Usuario).where(Usuario.email == self.email)).first())
        registro = self.session.get(CodigoLogin, self.email)
        self.assertEqual(len(registro.codigo_hash), 64)
        self.assertNotEqual(registro.codigo_hash, "000123")
        self.assertEqual(registro.expira_em - registro.enviado_em, timedelta(minutes=10))
        self.smtp_factory.assert_called_once_with("smtp.gmail.com", 587, timeout=10)
        context = self.smtp.starttls.call_args.kwargs["context"]
        self.assertTrue(context.check_hostname)
        self.smtp.login.assert_called_once_with("remetente@gmail.com", "senha-exclusiva-dos-testes")
        mensagem = self.smtp.send_message.call_args.args[0]
        self.assertEqual(mensagem["To"], self.email)
        self.assertIn("000123", mensagem.get_content())

        response = self.confirmar(nome="  Maria Silva  ")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        token = response.json()["token_acesso"]
        claims = decode(token, self.segredo, algorithms=["HS256"], audience="achados-perdidos-api", issuer="achados-perdidos-insper")
        self.assertEqual(claims["sub"], self.email)
        self.assertEqual(claims["exp"] - claims["iat"], 3600)
        self.assertEqual(self.session.exec(select(Usuario).where(Usuario.email == self.email)).one().nome, "Maria Silva")
        self.assertEqual(self.client.get("/itens", headers={"Authorization": f"Bearer {token}"}).status_code, 200)
        self.assertEqual(self.confirmar().status_code, 401)

    def test_consuming_code_does_not_round_expiration_into_the_future(self):
        self.assertEqual(self.solicitar().status_code, 200)
        agora = datetime.now(UTC).replace(microsecond=900_000)
        with patch("app.routes.auth.datetime") as clock:
            clock.now.return_value = agora
            self.assertEqual(self.confirmar().status_code, 200)
        registro = self.session.get(CodigoLogin, self.email)
        self.session.refresh(registro)
        self.assertLessEqual(registro.expira_em, agora.replace(tzinfo=None, microsecond=0))
        self.assertEqual(self.confirmar().status_code, 401)

    def test_existing_user_logs_in_without_name_and_keeps_original_name(self):
        email = "professor.login@insper.edu.br"
        usuario = Usuario.model_validate({"nome": "João Santos", "email": email})
        self.session.add(usuario)
        self.session.commit()
        self.assertEqual(self.solicitar(email).status_code, 200)
        self.assertEqual(self.confirmar(nome=None, email=email).status_code, 200)
        self.assertEqual(self.session.exec(select(Usuario).where(Usuario.email == email)).one().nome, "João Santos")

    def test_first_login_requires_name_without_consuming_code(self):
        self.assertEqual(self.solicitar().status_code, 200)
        self.assertEqual(self.confirmar(nome=None).status_code, 422)
        self.assertEqual(self.confirmar().status_code, 200)

    def test_invalid_inputs_are_rejected_before_sending(self):
        for email in ("invalido", "aluno@gmail.com", "aluno@insper.edu.br.evil.com"):
            with self.subTest(email=email):
                self.assertEqual(self.solicitar(email).status_code, 422)
                self.assertEqual(self.confirmar(email=email).status_code, 422)
        for codigo in ("12345", "1234567", "abcdef", 123456):
            with self.subTest(codigo=codigo):
                self.assertEqual(self.confirmar(codigo=codigo).status_code, 422)
        for nome in ("", "  ", "x" * 101):
            self.assertEqual(self.confirmar(nome=nome).status_code, 422)
        self.smtp.send_message.assert_not_called()

    def test_requests_are_throttled_and_resend_replaces_code(self):
        self.assertEqual(self.solicitar().status_code, 200)
        response = self.solicitar()
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response.headers["Retry-After"]), 0)
        self.assertEqual(self.smtp.send_message.call_count, 1)
        registro = self.session.get(CodigoLogin, self.email)
        registro.enviado_em -= timedelta(seconds=61)
        self.session.commit()
        with patch("app.routes.auth.secrets.randbelow", return_value=456):
            self.assertEqual(self.solicitar().status_code, 200)
        self.assertEqual(self.confirmar(codigo="000123").status_code, 401)
        self.assertEqual(self.confirmar(codigo="000456").status_code, 200)

    def test_expired_missing_and_exhausted_codes_are_rejected(self):
        self.assertEqual(self.confirmar().status_code, 401)
        self.assertEqual(self.solicitar().status_code, 200)
        for _ in range(5):
            self.assertEqual(self.confirmar(codigo="999999").status_code, 401)
        self.assertEqual(self.session.get(CodigoLogin, self.email).tentativas, 5)
        self.assertEqual(self.confirmar().status_code, 401)
        registro = self.session.get(CodigoLogin, self.email)
        registro.tentativas = 0
        registro.expira_em = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
        self.session.commit()
        self.assertEqual(self.confirmar().status_code, 401)
        self.assertIsNone(self.session.exec(select(Usuario).where(Usuario.email == self.email)).first())

    def test_email_failure_rolls_back_code_and_allows_retry(self):
        self.smtp.send_message.side_effect = OSError("detalhe-interno-do-servidor")
        response = self.solicitar()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("detalhe-interno", response.text)
        self.assertIsNone(self.session.get(CodigoLogin, self.email))
        self.smtp.send_message.side_effect = None
        self.assertEqual(self.solicitar().status_code, 200)

    def test_failed_resend_preserves_previous_code(self):
        self.assertEqual(self.solicitar().status_code, 200)
        registro = self.session.get(CodigoLogin, self.email)
        codigo_hash = registro.codigo_hash
        registro.enviado_em -= timedelta(seconds=61)
        self.session.commit()
        self.smtp.send_message.side_effect = OSError("indisponível")
        with patch("app.routes.auth.secrets.randbelow", return_value=456):
            self.assertEqual(self.solicitar().status_code, 503)
        self.assertEqual(self.session.get(CodigoLogin, self.email).codigo_hash, codigo_hash)
        self.assertEqual(self.confirmar().status_code, 200)

    def test_missing_configuration_denies_login(self):
        for config in (
            auth.AuthSettings(_env_file=None),
            auth.AuthSettings(_env_file=None, auth_secret_key=self.segredo),
        ):
            with patch.object(auth, "config_auth", config):
                self.assertEqual(self.solicitar().status_code, 503)
        self.assertIsNone(self.session.get(CodigoLogin, self.email))
        self.smtp.send_message.assert_not_called()

    def test_concurrent_confirmations_consume_code_only_once(self):
        email = f"concorrencia.{uuid4().hex}@al.insper.edu.br"
        app.dependency_overrides.pop(get_session)
        try:
            self.assertEqual(self.solicitar(email).status_code, 200)
            with ThreadPoolExecutor(max_workers=2) as pool:
                responses = list(pool.map(lambda _: self.confirmar(email=email), range(2)))
            self.assertEqual(sorted(response.status_code for response in responses), [200, 401])
            with Session(engine) as session:
                self.assertEqual(len(session.exec(select(Usuario).where(Usuario.email == email)).all()), 1)
        finally:
            with Session(engine) as session:
                session.exec(delete(CodigoLogin).where(CodigoLogin.email == email))
                session.exec(delete(Usuario).where(Usuario.email == email))
                session.commit()
            app.dependency_overrides[get_session] = lambda: self.session
