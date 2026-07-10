import os
import unittest
from unittest.mock import patch

from services.warcraftlogs.api_client import (
    AccessToken,
    WarcraftLogsClient,
    WarcraftLogsConfigurationError,
)
from services.warcraftlogs.credentials import get_warcraftlogs_credentials


class AccessTokenTests(unittest.TestCase):
    def test_token_is_valid_before_expiry(self):
        token = AccessToken(value="token", expires_at=100.0)
        self.assertTrue(token.is_valid(now=99.0))

    def test_token_is_invalid_at_expiry(self):
        token = AccessToken(value="token", expires_at=100.0)
        self.assertFalse(token.is_valid(now=100.0))


class WarcraftLogsClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_credentials_fail_before_network_request(self):
        client = WarcraftLogsClient(None, None)

        with self.assertRaises(WarcraftLogsConfigurationError):
            await client.query("query { rateLimitData { limitPerHour } }")

        await client.close()

    async def test_blank_query_is_rejected(self):
        client = WarcraftLogsClient("client", "secret")

        with self.assertRaises(ValueError):
            await client.query("   ")

        await client.close()


class WarcraftLogsCredentialTests(unittest.TestCase):
    def test_environment_credentials_are_loaded(self):
        with patch.dict(
            os.environ,
            {
                "WARCRAFTLOGS_CLIENT_ID": "client-id",
                "WARCRAFTLOGS_CLIENT_SECRET": "client-secret",
            },
            clear=False,
        ):
            self.assertEqual(
                get_warcraftlogs_credentials(),
                ("client-id", "client-secret"),
            )


if __name__ == "__main__":
    unittest.main()
