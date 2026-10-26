import unittest

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.auth import exigir_autenticacao
from app.database import engine, get_session
from app.main import app
from app.models.user import Usuario
from tests.helpers import foto_upload


class RetiradaTests(unittest.TestCase):
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
        self.retirada_data = {
            "id_item": self.create_item(),
            "retirado_em": "2026-10-25T14:00:00",
        }

    def create_item(self):
        response = self.client.post(
            "/itens",
            data={
                "nome": "Garrafa de água",
                "descricao": "Garrafa azul com tampa preta",
                "predio": 1,
                "local_encontrado": "Biblioteca",
                "encontrado_em": "2026-10-25T10:30:00",
            },
            files=foto_upload(),
        )
        self.assertEqual(response.status_code, 201)
        return response.json()["id"]

    def create_retirada(self, data):
        response = self.client.post("/retiradas", json=data)
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_crud(self):
        retirada = self.create_retirada(self.retirada_data)
        self.assertGreater(retirada["id"], 0)
        self.assertEqual(retirada, self.retirada_data | {
            "id": retirada["id"], "id_usuario": self.usuario.id,
        })
        path = f"/retiradas/{retirada['id']}"
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), retirada)

        updated = self.retirada_data | {
            "retirado_em": "2026-10-25T15:00:00",
        }
        response = self.client.put(path, json=updated)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), updated | {
            "id": retirada["id"], "id_usuario": self.usuario.id,
        })
        self.assertEqual(self.client.get(path).json(), response.json())

        response = self.client.delete(path)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.put(path, json=updated).status_code, 404)
        self.assertEqual(self.client.delete(path).status_code, 404)
        self.assertEqual(
            self.client.delete(f"/itens/{retirada['id_item']}").status_code, 204
        )

    def test_conflicts_preserve_records_and_allow_subsequent_requests(self):
        first = self.create_retirada(self.retirada_data)
        second_data = self.retirada_data | {"id_item": self.create_item()}
        second = self.create_retirada(second_data)
        first_path = f"/retiradas/{first['id']}"
        second_path = f"/retiradas/{second['id']}"
        item_path = f"/itens/{first['id_item']}"

        response = self.client.post("/retiradas", json=self.retirada_data)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.get(first_path).json(), first)

        response = self.client.put(second_path, json=self.retirada_data)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.get(second_path).json(), second)

        self.assertEqual(self.client.delete(item_path).status_code, 409)
        self.assertEqual(self.client.get(item_path).status_code, 200)
        self.assertEqual(self.client.get(first_path).json(), first)

        self.assertEqual(self.client.delete(first_path).status_code, 204)
        replacement = self.create_retirada(self.retirada_data)
        self.assertEqual(replacement["id_item"], first["id_item"])

    def test_update_can_change_the_item(self):
        retirada = self.create_retirada(self.retirada_data)
        updated = self.retirada_data | {"id_item": self.create_item()}
        response = self.client.put(f"/retiradas/{retirada['id']}", json=updated)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), updated | {
            "id": retirada["id"], "id_usuario": self.usuario.id,
        })
        self.assertEqual(
            self.client.delete(f"/itens/{retirada['id_item']}").status_code, 204
        )
        self.assertEqual(self.client.delete(f"/itens/{updated['id_item']}").status_code, 409)

    def test_missing_item_is_rejected_without_changing_retirada(self):
        missing_id = self.create_item()
        self.assertEqual(self.client.delete(f"/itens/{missing_id}").status_code, 204)
        invalid_data = self.retirada_data | {"id_item": missing_id}
        self.assertEqual(self.client.post("/retiradas", json=invalid_data).status_code, 404)

        retirada = self.create_retirada(self.retirada_data)
        path = f"/retiradas/{retirada['id']}"
        self.assertEqual(self.client.put(path, json=invalid_data).status_code, 404)
        self.assertEqual(self.client.get(path).json(), retirada)

    def test_pagination(self):
        self.create_retirada(self.retirada_data)
        self.create_retirada(self.retirada_data | {"id_item": self.create_item()})
        first = self.client.get("/retiradas", params={"limite": 1})
        second = self.client.get("/retiradas", params={"limite": 1, "deslocamento": 1})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(len(first.json()), 1)
        self.assertEqual(len(second.json()), 1)
        self.assertLess(first.json()[0]["id"], second.json()[0]["id"])

        for params in ({"limite": 0}, {"limite": 101}, {"deslocamento": -1}):
            with self.subTest(params=params):
                self.assertEqual(
                    self.client.get("/retiradas", params=params).status_code, 422
                )

    def test_invalid_data_is_rejected_for_create_and_update(self):
        retirada = self.create_retirada(self.retirada_data)
        path = f"/retiradas/{retirada['id']}"
        invalid_changes = (
            {"id_item": 0},
            {"id_item": -1},
            {"nome_retirante": "Maria Silva"},
            {"email_retirante": "maria@al.insper.edu.br"},
            {"retirado_em": "invalido"},
            {"retirado_em": "2026-10-25T14:00:00-03:00"},
            {"retirado_em": None},
            {"id": 1},
            {"id_usuario": self.usuario.id + 1},
        )
        for changes in invalid_changes:
            with self.subTest(changes=changes):
                data = self.retirada_data | changes
                self.assertEqual(self.client.post("/retiradas", json=data).status_code, 422)
                self.assertEqual(self.client.put(path, json=data).status_code, 422)

        self.assertEqual(self.client.post("/retiradas", json={}).status_code, 422)
        self.assertEqual(self.client.put(path, json={"nome_retirante": "Maria"}).status_code, 422)
        self.assertEqual(self.client.get(path).json(), retirada)

    def test_invalid_ids_and_api_documentation(self):
        for method in ("GET", "PUT", "DELETE"):
            for id_retirada in ("0", "-1", "invalido"):
                with self.subTest(method=method, id_retirada=id_retirada):
                    response = self.client.request(
                        method, f"/retiradas/{id_retirada}", json=self.retirada_data
                    )
                    self.assertEqual(response.status_code, 422)

        schema = self.client.get("/openapi.json").json()
        self.assertEqual(set(schema["paths"]["/retiradas"]), {"get", "post"})
        self.assertEqual(
            set(schema["paths"]["/retiradas/{id_retirada}"]), {"get", "put", "delete"}
        )
        properties = schema["components"]["schemas"]["RetiradaBase"]["properties"]
        self.assertEqual(set(properties), set(self.retirada_data))
        self.assertEqual(properties["id_item"]["examples"], [1])
