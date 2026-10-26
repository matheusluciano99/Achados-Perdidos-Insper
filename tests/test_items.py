import unittest

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.auth import exigir_autenticacao
from app.database import engine, get_session
from app.main import app
from app.models.user import Usuario


class ItemTests(unittest.TestCase):
    def setUp(self):
        connection = self.enterContext(engine.connect())
        transaction = connection.begin()
        self.addCleanup(transaction.rollback)
        session = self.enterContext(
            Session(bind=connection, join_transaction_mode="create_savepoint")
        )
        app.dependency_overrides[get_session] = lambda: session
        self.usuario = Usuario.model_validate({"nome": "Maria Silva", "email": "maria@al.insper.edu.br"})
        session.add(self.usuario)
        session.flush()
        app.dependency_overrides[exigir_autenticacao] = lambda: self.usuario
        self.addCleanup(app.dependency_overrides.clear)
        self.client = self.enterContext(TestClient(app))
        self.item_data = {
            "nome": "Garrafa de água",
            "descricao": "Garrafa azul com tampa preta",
            "local_encontrado": "Biblioteca",
            "encontrado_em": "2026-10-25T10:30:00",
        }

    def test_crud(self):
        response = self.client.post("/itens", json=self.item_data)
        self.assertEqual(response.status_code, 201)
        item = response.json()
        self.assertGreater(item["id"], 0)
        self.assertEqual(item, self.item_data | {"id": item["id"], "id_usuario": self.usuario.id})
        path = f"/itens/{item['id']}"

        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), item)

        updated = self.item_data | {"nome": "Garrafa térmica", "local_encontrado": "Sala 101"}
        response = self.client.put(path, json=updated)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), updated | {"id": item["id"], "id_usuario": self.usuario.id})
        self.assertEqual(self.client.get(path).json(), response.json())

        response = self.client.delete(path)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.put(path, json=updated).status_code, 404)
        self.assertEqual(self.client.delete(path).status_code, 404)

    def test_list_pagination(self):
        for _ in range(2):
            self.assertEqual(self.client.post("/itens", json=self.item_data).status_code, 201)

        first = self.client.get("/itens", params={"limite": 1})
        second = self.client.get("/itens", params={"limite": 1, "deslocamento": 1})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(len(first.json()), 1)
        self.assertEqual(len(second.json()), 1)
        self.assertLess(first.json()[0]["id"], second.json()[0]["id"])

        for params in ({"limite": 0}, {"limite": 101}, {"deslocamento": -1}):
            with self.subTest(params=params):
                self.assertEqual(self.client.get("/itens", params=params).status_code, 422)

    def test_invalid_data_is_rejected_for_create_and_update(self):
        response = self.client.post("/itens", json=self.item_data)
        self.assertEqual(response.status_code, 201)
        path = f"/itens/{response.json()['id']}"
        invalid_changes = (
            {"nome": "   "},
            {"nome": "x" * 101},
            {"descricao": ""},
            {"descricao": "x" * 1001},
            {"local_encontrado": " "},
            {"local_encontrado": "x" * 201},
            {"encontrado_em": "invalid"},
            {"encontrado_em": "2026-10-25T10:30:00-03:00"},
            {"encontrado_em": None},
            {"id": 1},
            {"id_usuario": self.usuario.id + 1},
        )
        for changes in invalid_changes:
            with self.subTest(changes=changes):
                data = self.item_data | changes
                self.assertEqual(self.client.post("/itens", json=data).status_code, 422)
                self.assertEqual(self.client.put(path, json=data).status_code, 422)

        self.assertEqual(self.client.post("/itens", json={}).status_code, 422)
        self.assertEqual(self.client.put(path, json={"nome": "Outro item"}).status_code, 422)
        self.assertEqual(self.client.get(path).json(), self.item_data | {
            "id": response.json()["id"], "id_usuario": self.usuario.id,
        })

    def test_invalid_item_ids(self):
        for method in ("GET", "PUT", "DELETE"):
            for id_item in ("0", "-1", "invalid"):
                with self.subTest(method=method, id_item=id_item):
                    response = self.client.request(method, f"/itens/{id_item}", json=self.item_data)
                    self.assertEqual(response.status_code, 422)

    def test_root_and_api_documentation(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"mensagem": "Achados & Perdidos API"})
        self.assertEqual(self.client.get("/docs").status_code, 200)
        schema = self.client.get("/openapi.json").json()
        self.assertEqual(set(schema["paths"]["/itens"]), {"get", "post"})
        self.assertEqual(set(schema["paths"]["/itens/{id_item}"]), {"get", "put", "delete"})
        properties = schema["components"]["schemas"]["ItemBase"]["properties"]
        self.assertEqual(set(properties), set(self.item_data))
        self.assertEqual(properties["nome"]["examples"], ["Garrafa de água"])
