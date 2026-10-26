from io import BytesIO
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, select

from app.auth import exigir_autenticacao
from app.database import engine, get_session
from app.main import app
from app.models.photo import FotoItem
from app.models.user import Usuario
from app.routes import items
from tests.helpers import foto_upload, imagem_teste


class PhotoTests(unittest.TestCase):
    def setUp(self):
        self.client = self.enterContext(TestClient(app))
        connection = self.enterContext(engine.connect())
        transaction = connection.begin()
        self.addCleanup(transaction.rollback)
        self.session = self.enterContext(
            Session(bind=connection, join_transaction_mode="create_savepoint")
        )
        usuario = Usuario.model_validate({"nome": "Maria Silva", "email": "foto.teste@al.insper.edu.br"})
        self.session.add(usuario)
        self.session.flush()
        app.dependency_overrides[get_session] = lambda: self.session
        app.dependency_overrides[exigir_autenticacao] = lambda: usuario
        self.addCleanup(app.dependency_overrides.clear)
        self.dados_item = {
            "nome": "Garrafa", "descricao": "Garrafa azul", "predio": 1,
            "local_encontrado": "Biblioteca", "encontrado_em": "2026-10-25T10:30:00",
        }
        response = self.client.post("/itens", data=self.dados_item, files=foto_upload())
        self.assertEqual(response.status_code, 201)
        self.item = response.json()
        self.path = f"/itens/{self.item['id']}/foto"

    def enviar(self, conteudo, path=None):
        return self.client.put(path or self.path, files=foto_upload(conteudo))

    def test_creation_includes_photo_and_replacement_keeps_one_photo(self):
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/jpeg")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertIn("no-store", response.headers["cache-control"])
        with Image.open(BytesIO(response.content)) as foto:
            self.assertEqual(foto.format, "JPEG")
            self.assertEqual(foto.size, (12, 8))

        self.assertEqual(self.enviar(imagem_teste("JPEG", (20, 10))).status_code, 204)
        with Image.open(BytesIO(self.client.get(self.path).content)) as foto:
            self.assertEqual(foto.size, (20, 10))
        fotos = self.session.exec(select(FotoItem).where(FotoItem.id_item == self.item["id"])).all()
        self.assertEqual(len(fotos), 1)
        self.assertEqual(self.client.get(f"/itens/{self.item['id']}").json(), self.item)

        self.assertEqual(self.client.delete(self.path).status_code, 405)
        self.assertEqual(self.client.get(self.path).status_code, 200)
        self.assertEqual(self.client.get(f"/itens/{self.item['id']}").status_code, 200)

    def test_invalid_files_preserve_existing_photo(self):
        original = self.client.get(self.path).content
        for conteudo in (b"", b"nao e uma imagem", imagem_teste("GIF"), imagem_teste()[:30]):
            with self.subTest(tamanho=len(conteudo)):
                self.assertEqual(self.enviar(conteudo).status_code, 400)
                self.assertEqual(self.client.get(self.path).content, original)
        self.assertEqual(self.enviar(b"x" * (items.MAX_FOTO_BYTES + 1)).status_code, 413)
        self.assertEqual(self.client.get(self.path).content, original)
        with patch.object(items, "MAX_FOTO_PIXELS", 100):
            self.assertEqual(self.enviar(imagem_teste(tamanho=(20, 10))).status_code, 413)
        self.assertEqual(self.client.get(self.path).content, original)

    def test_resizes_photo_and_removes_exif(self):
        exif = Image.Exif()
        exif[274] = 6
        exif[315] = "Autor de teste"
        conteudo = imagem_teste("JPEG", (2400, 1200), exif=exif)
        self.assertEqual(self.enviar(conteudo).status_code, 204)
        with Image.open(BytesIO(self.client.get(self.path).content)) as foto:
            self.assertEqual(foto.size, (960, 1920))
            self.assertEqual(len(foto.getexif()), 0)

    def test_requires_existing_item_and_valid_identifier(self):
        item_path = f"/itens/{self.item['id']}"
        self.assertEqual(self.client.delete(item_path).status_code, 204)
        self.assertEqual(self.enviar(imagem_teste()).status_code, 404)
        self.assertEqual(self.client.get(self.path).status_code, 404)
        for id_item in ("0", "-1", "invalido"):
            path = f"/itens/{id_item}/foto"
            self.assertEqual(self.enviar(imagem_teste(), path=path).status_code, 422)
            self.assertEqual(self.client.get(path).status_code, 422)

    def test_item_deletion_removes_photo_only_when_deletion_succeeds(self):
        response = self.client.post("/retiradas", json={
            "id_item": self.item["id"], "retirado_em": "2026-10-25T14:00:00",
        })
        self.assertEqual(response.status_code, 201)
        item_path = f"/itens/{self.item['id']}"
        self.assertEqual(self.client.delete(item_path).status_code, 409)
        self.assertEqual(self.client.get(self.path).status_code, 200)
        self.assertEqual(self.client.delete(f"/retiradas/{response.json()['id']}").status_code, 204)
        self.assertEqual(self.client.delete(item_path).status_code, 204)
        self.session.expire_all()
        self.assertIsNone(self.session.get(FotoItem, self.item["id"]))

    def test_documentation_describes_photo_upload(self):
        schema = self.client.get("/openapi.json").json()
        path = schema["paths"]["/itens/{id_item}/foto"]
        self.assertEqual(set(path), {"put", "get"})
        self.assertIn("multipart/form-data", path["put"]["requestBody"]["content"])
        self.assertIn("image/jpeg", path["get"]["responses"]["200"]["content"])
        for operation in path.values():
            self.assertEqual(operation["security"], [{"AcessoInsper": []}])
        cadastro = schema["paths"]["/itens"]["post"]["requestBody"]["content"]
        self.assertEqual(set(cadastro), {"multipart/form-data"})
        self.assertIn("foto", schema["components"]["schemas"]["ItemCreate"]["required"])

    def test_missing_or_invalid_photo_does_not_create_item(self):
        antes = self.client.get("/itens").json()
        self.assertEqual(self.client.post("/itens", data=self.dados_item).status_code, 422)
        for conteudo, status in ((b"", 400), (b"arquivo invalido", 400), (b"x" * (items.MAX_FOTO_BYTES + 1), 413)):
            with self.subTest(status=status, tamanho=len(conteudo)):
                response = self.client.post("/itens", data=self.dados_item, files=foto_upload(conteudo))
                self.assertEqual(response.status_code, status)
        self.assertEqual(self.client.get("/itens").json(), antes)

    def test_photo_persistence_failure_rolls_back_item(self):
        antes = self.client.get("/itens").json()
        adicionar = self.session.add

        def foto_sem_item(registro):
            if isinstance(registro, FotoItem):
                registro.id_item = 0
            adicionar(registro)

        with patch.object(self.session, "add", side_effect=foto_sem_item):
            response = self.client.post("/itens", data=self.dados_item, files=foto_upload())
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.get("/itens").json(), antes)
