import unittest

from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.database import engine
from app.main import app
from app.models.user import Usuario


class UsuarioTests(unittest.TestCase):
    def test_validates_institutional_emails(self):
        for email in ("ALUNO@AL.INSPER.EDU.BR", "professor@insper.edu.br"):
            with self.subTest(email=email):
                usuario = Usuario.model_validate({"nome": "Maria Silva", "email": email})
                self.assertEqual(usuario.email, email.lower())
                self.assertIsNone(usuario.id)
        for email in (
            "email-invalido", "aluno@gmail.com", "aluno@insper.edu.br.evil.com",
            "aluno@outroinsper.edu.br", None,
        ):
            with self.subTest(email=email), self.assertRaises(ValidationError):
                Usuario.model_validate({"nome": "Maria Silva", "email": email})

    def test_name_is_required_and_trimmed(self):
        dados = {"nome": "  Maria Silva  ", "email": "maria@al.insper.edu.br"}
        self.assertEqual(Usuario.model_validate(dados).nome, "Maria Silva")
        for nome in ("", "   ", "x" * 101, None):
            with self.subTest(nome=nome), self.assertRaises(ValidationError):
                Usuario.model_validate(dados | {"nome": nome})
        with self.assertRaises(ValidationError):
            Usuario.model_validate({"email": dados["email"]})

    def test_persists_user_and_rejects_duplicate_email(self):
        self.enterContext(TestClient(app))
        connection = self.enterContext(engine.connect())
        transaction = connection.begin()
        self.addCleanup(transaction.rollback)
        session = self.enterContext(
            Session(bind=connection, join_transaction_mode="create_savepoint")
        )
        usuario = Usuario.model_validate({
            "nome": "Maria Silva", "email": "teste.modelo.usuario@al.insper.edu.br",
        })
        session.add(usuario)
        session.commit()
        session.refresh(usuario)
        self.assertGreater(usuario.id, 0)
        self.assertEqual(session.get(Usuario, usuario.id).nome, "Maria Silva")
        self.assertEqual(session.get(Usuario, usuario.id).email, usuario.email)

        session.add(Usuario.model_validate({"nome": "Outro nome", "email": usuario.email.upper()}))
        with self.assertRaises(IntegrityError):
            session.commit()
        session.rollback()
        self.assertEqual(session.get(Usuario, usuario.id).email, usuario.email)
