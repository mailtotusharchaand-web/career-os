"""
tests.test_gmail_oauth — Unit tests for Google OAuth2 client, read-only scope locking, canonical redirect URI, and token management.
"""

import unittest
import tempfile
import shutil
import os
from unittest.mock import patch, MagicMock
from career_os.email.oauth import (
    GoogleOAuthClient,
    OAuthConfigurationError,
    READONLY_GMAIL_SCOPE,
    USERINFO_EMAIL_SCOPE,
)
from career_os.email.token_store import LocalSecureFileTokenStore
from career_os.config import get_canonical_redirect_uri, get_oauth_config, load_dotenv


class TestGmailOAuth(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.token_store = LocalSecureFileTokenStore(base_dir=self.temp_dir)
        self.client = GoogleOAuthClient(
            client_id="test_client_id.apps.googleusercontent.com",
            client_secret="test_client_secret_xyz",
            redirect_uri="http://localhost:8080/api/gmail/callback",
            token_store=self.token_store,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_missing_client_id_fails_clearly(self):
        client = GoogleOAuthClient(client_id="", client_secret="secret_abc", token_store=self.token_store)
        with self.assertRaises(OAuthConfigurationError) as ctx:
            client.validate_configuration()
        self.assertIn("GMAIL_CLIENT_ID", str(ctx.exception))
        self.assertIn(".env", str(ctx.exception))

    def test_missing_client_secret_fails_clearly(self):
        client = GoogleOAuthClient(client_id="client_123", client_secret="", token_store=self.token_store)
        with self.assertRaises(OAuthConfigurationError) as ctx:
            client.validate_configuration()
        self.assertIn("GMAIL_CLIENT_SECRET", str(ctx.exception))
        self.assertIn(".env", str(ctx.exception))

    def test_canonical_redirect_uri_generation(self):
        # When no explicit override is in env, defaults to active port
        with patch.dict(os.environ, {}, clear=True):
            uri_8080 = get_canonical_redirect_uri(port=8080)
            self.assertEqual(uri_8080, "http://localhost:8080/api/gmail/callback")

            uri_8081 = get_canonical_redirect_uri(port=8081)
            self.assertEqual(uri_8081, "http://localhost:8081/api/gmail/callback")

        # When GMAIL_REDIRECT_URI is explicitly set in env, it is respected
        with patch.dict(os.environ, {"GMAIL_REDIRECT_URI": "http://127.0.0.1:9000/api/gmail/callback"}):
            self.assertEqual(get_canonical_redirect_uri(port=8080), "http://127.0.0.1:9000/api/gmail/callback")

    def test_authorization_url_uses_configured_and_dynamic_redirect_uri(self):
        url, state = self.client.get_authorization_url()
        self.assertIn("redirect_uri=http%3A%2F%2Flocalhost%3A8080%2Fapi%2Fgmail%2Fcallback", url)

        # Dynamic port alignment on port 8081
        url_8081, state_8081 = self.client.get_authorization_url(port=8081)
        self.assertIn("redirect_uri=http%3A%2F%2Flocalhost%3A8081%2Fapi%2Fgmail%2Fcallback", url_8081)

    def test_authorization_url_strictly_requests_readonly_scope(self):
        url, state = self.client.get_authorization_url()
        self.assertTrue(len(state) > 10)
        self.assertIn("accounts.google.com", url)
        self.assertIn("client_id=test_client_id.apps.googleusercontent.com", url)
        self.assertIn("access_type=offline", url)
        self.assertIn("prompt=consent", url)
        # Verify read-only scope is present and write scope is NEVER present
        self.assertIn("gmail.readonly", url)
        self.assertNotIn("gmail.modify", url)
        self.assertNotIn("gmail.compose", url)
        self.assertNotIn("gmail.send", url)

    @patch("requests.post")
    @patch("requests.get")
    def test_exchange_code_for_tokens_and_save_to_token_store(self, mock_get, mock_post):
        # Mock token response
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {
            "access_token": "ya29.mock_access_token",
            "refresh_token": "1//mock_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
        mock_post.return_value = mock_post_resp

        # Mock userinfo response
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = {"email": "candidate.test@gmail.com"}
        mock_get.return_value = mock_get_resp

        result = self.client.exchange_code_for_tokens("mock_auth_code_123")
        self.assertEqual(result["account_email"], "candidate.test@gmail.com")

        # Verify saved in TokenStore
        saved = self.token_store.get_token("gmail", "candidate.test@gmail.com")
        self.assertIsNotNone(saved)
        self.assertEqual(saved["access_token"], "ya29.mock_access_token")
        self.assertEqual(saved["refresh_token"], "1//mock_refresh_token")

    @patch("requests.post")
    def test_refresh_token_flow(self, mock_post):
        self.token_store.save_token("gmail", "candidate@gmail.com", {
            "access_token": "old_token",
            "refresh_token": "valid_refresh_token",
        })

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "new_refreshed_access_token",
            "expires_in": 3600,
        }
        mock_post.return_value = mock_resp

        refreshed = self.client.refresh_token("candidate@gmail.com")
        self.assertIsNotNone(refreshed)
        self.assertEqual(refreshed["access_token"], "new_refreshed_access_token")
        self.assertEqual(refreshed["refresh_token"], "valid_refresh_token")


if __name__ == "__main__":
    unittest.main()
