import json
import unittest
from dataclasses import dataclass

from services.warcraftlogs.debug_service import (
    build_debug_json_bytes,
    build_debug_payload,
)


@dataclass(frozen=True)
class ExampleEntry:
    name: str
    rank: int


class WarcraftLogsDebugServiceTests(unittest.TestCase):
    def test_redacts_credential_like_keys_recursively(self):
        payload = build_debug_payload(
            operation="guild_rankings",
            request={
                "client_secret": "hidden",
                "nested": {"access_token": "hidden-too"},
            },
            response={"authorization": "Bearer secret", "value": 42},
        )

        self.assertEqual(payload["request"]["client_secret"], "[REDACTED]")
        self.assertEqual(
            payload["request"]["nested"]["access_token"],
            "[REDACTED]",
        )
        self.assertEqual(payload["response"]["authorization"], "[REDACTED]")
        self.assertEqual(payload["response"]["value"], 42)

    def test_serializes_dataclasses_and_utf8(self):
        raw = build_debug_json_bytes(
            operation="guild_rankings",
            request={"guild_name": "Hekkipekkis guild"},
            response={"entries": (ExampleEntry("Garrosh", 12),)},
        )
        payload = json.loads(raw.decode("utf-8"))

        self.assertEqual(payload["operation"], "guild_rankings")
        self.assertEqual(payload["response"]["entries"][0]["name"], "Garrosh")
        self.assertEqual(payload["response"]["entries"][0]["rank"], 12)

    def test_bytes_are_represented_without_raw_content(self):
        payload = build_debug_payload(
            operation="example",
            request={},
            response={"blob": b"secret bytes"},
        )

        self.assertEqual(payload["response"]["blob"], "<bytes:12>")


if __name__ == "__main__":
    unittest.main()
