"""
tests.test_token_store — Unit tests for TokenStore credential abstraction.
"""

import unittest
import shutil
import tempfile
from pathlib import Path
from career_os.email.token_store import LocalSecureFileTokenStore


class TestTokenStore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.store = LocalSecureFileTokenStore(base_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_and_retrieve_token(self):
        token_payload = {
            "access_token": "mock_access_token_12345",
            "refresh_token": "mock_refresh_token_67890",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test_client_id.apps.googleusercontent.com",
            "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
            "expires_in": 3600,
        }

        self.assertFalse(self.store.has_token("gmail", "user@example.com"))
        self.store.save_token("gmail", "user@example.com", token_payload)

        self.assertTrue(self.store.has_token("gmail", "user@example.com"))
        retrieved = self.store.get_token("gmail", "user@example.com")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["access_token"], "mock_access_token_12345")
        self.assertEqual(retrieved["refresh_token"], "mock_refresh_token_67890")

    def test_delete_and_list_accounts(self):
        self.store.save_token("gmail", "user1@example.com", {"access_token": "tok1"})
        self.store.save_token("gmail", "user2@example.com", {"access_token": "tok2"})

        accounts = self.store.list_accounts("gmail")
        self.assertIn("user1@example.com", accounts)
        self.assertIn("user2@example.com", accounts)

        deleted = self.store.delete_token("gmail", "user1@example.com")
        self.assertTrue(deleted)
        self.assertFalse(self.store.has_token("gmail", "user1@example.com"))
        self.assertTrue(self.store.has_token("gmail", "user2@example.com"))


if __name__ == "__main__":
    unittest.main()
