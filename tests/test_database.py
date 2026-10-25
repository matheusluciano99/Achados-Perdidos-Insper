import unittest

from sqlalchemy import text

from app.database import engine, settings


class DatabaseTests(unittest.TestCase):
    def test_connection_uses_configured_database_and_user(self):
        with engine.connect() as connection:
            database, user, message = connection.execute(
                text("SELECT DATABASE(), CURRENT_USER(), :message"),
                {"message": "Achados & Perdidos"},
            ).one()

        self.assertEqual(database, settings.mysql_database)
        self.assertEqual(user.split("@")[0], settings.mysql_user)
        self.assertEqual(message, "Achados & Perdidos")
