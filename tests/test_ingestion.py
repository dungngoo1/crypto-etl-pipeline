import sys
from datetime import datetime, timezone
from pathlib import Path
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ingest_market_data import fetch_snapshot, parse_timestamp


def response(body):
    result = Mock()
    result.json.return_value = body
    return result


class IngestionTests(unittest.TestCase):
    def test_all_quotes_are_retained_including_inactive(self):
        rows = [{"symbol": "ETHBTC"}, {"symbol": "BTCUSDT"}, {"symbol": "OLDUSDT"}]
        session = Mock()
        session.get.side_effect = [
            response(rows),
            response({"symbols": [
                {"symbol": "ETHBTC", "status": "TRADING", "isSpotTradingAllowed": True},
                {"symbol": "BTCUSDT", "status": "TRADING", "isSpotTradingAllowed": True},
                {"symbol": "OLDUSDT", "status": "BREAK", "isSpotTradingAllowed": False},
            ]}),
        ]
        actual, metadata, captured = fetch_snapshot(session)
        self.assertEqual(actual, rows)
        self.assertEqual(len(metadata), 3)
        self.assertIsNotNone(captured.tzinfo)
        self.assertNotIn("params", session.get.call_args_list[0].kwargs)

    def test_empty_and_error_payloads_fail(self):
        for payload in ([], {"code": -1, "msg": "error"}):
            with self.subTest(payload=payload):
                session = Mock()
                session.get.return_value = response(payload)
                with self.assertRaises(ValueError):
                    fetch_snapshot(session)

    def test_missing_active_symbol_fails(self):
        session = Mock()
        session.get.side_effect = [
            response([{"symbol": "ETHBTC"}]),
            response({"symbols": [{"symbol": "BTCUSDT", "status": "TRADING", "isSpotTradingAllowed": True}]}),
        ]
        with self.assertRaisesRegex(ValueError, "Missing active"):
            fetch_snapshot(session)

    def test_duplicate_symbol_fails(self):
        session = Mock()
        session.get.return_value = response([{"symbol": "BTCUSDT"}, {"symbol": "BTCUSDT"}])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            fetch_snapshot(session)

    def test_timezone_is_required_and_normalized(self):
        with self.assertRaises(ValueError):
            parse_timestamp("2026-01-01T00:00:00")
        self.assertEqual(parse_timestamp("2026-01-01T07:00:00+07:00"),
                         datetime(2026, 1, 1, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()
