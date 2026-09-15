import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import usage_support_load as load


class MonthlyLoadTests(unittest.TestCase):
    def test_monthly_metrics_are_aggregate_and_rates_use_accounts(self):
        posthog = {
            "accounts": 100,
            "mail": 80,
            "appointment": 40,
            "send": 20,
        }
        zendesk = {
            "eligible_tickets": 12,
            "unique_requesters": 10,
            "services": {"Send": {"tickets": 2, "unique_requesters": 2}},
            "entity_areas": {"webmail": {"tickets": 1, "unique_requesters": 1}},
            "webmail": {"tickets": 2, "unique_requesters": 2},
        }
        with patch.object(load, "monthly_posthog_people", return_value=posthog), \
             patch.object(load, "login_people_by_client", return_value={
                 "webmail": 25,
                 "accounts_web": 60,
                 "appointment_web": 15,
             }), \
             patch.object(load, "monthly_zendesk_requesters", return_value=zendesk):
            result = load.build_monthly_load("august", 2026)

        self.assertEqual(result["posthog_visible_users"], 100)
        self.assertEqual(result["contact_rate_visible_pct"], 10.0)
        self.assertEqual(result["tickets_per_requester"], 1.2)
        self.assertEqual(result["posthog_surfaces"]["webmail"], 25)
        self.assertEqual(result["surface_contact_rate_visible_pct"]["webmail"], 8.0)
        self.assertEqual(result["zendesk_webmail"]["unique_requesters"], 2)
        self.assertNotIn("any_client", result["posthog_signins"])
        self.assertIn("never summed", result["methodology"])
        self.assertTrue(any("uniq(person_id)" in item for item in result["methodology_scan"]))
        self.assertTrue(any("accounts.activity" in item for item in result["methodology_scan"]))
        self.assertTrue(any("thundermail_what_ui__webmail" in item for item in result["methodology_scan"]))
        self.assertTrue(any(item.startswith("Internal users:") for item in result["methodology_scan"]))
        self.assertFalse(any("staff are excluded" in item.lower() for item in result["methodology_scan"]))
        self.assertTrue(any("@thunderbird.net" in item for item in result["methodology_scan"]))

    def test_unique_people_query_applies_posthog_internal_filters(self):
        start = dt.datetime(2026, 8, 1, tzinfo=dt.timezone.utc)
        end = dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc)
        captured = {}

        def fake_hogql(query, filter_test_accounts=False):
            captured["query"] = query
            captured["filter_test_accounts"] = filter_test_accounts
            return {"results": [[42]]}

        with patch.object(load, "posthog_hogql", side_effect=fake_hogql):
            count = load.unique_people_for_predicate("event = 'accounts.activity'", start, end)

        self.assertEqual(count, 42)
        self.assertTrue(captured["filter_test_accounts"])
        self.assertIn("{filters}", captured["query"])
        self.assertIn("@thunderbird.net", captured["query"])
        self.assertIn("localhost", captured["query"])

    def test_requester_counts_are_deduplicated_by_service(self):
        tickets = [
            {"id": 1, "requester_id": 11, "tags": [
                "pro_service_send", "thundermail_entity_area_webmail",
            ]},
            {"id": 2, "requester_id": 11, "tags": ["pro_service_send"]},
            {"id": 3, "requester_id": 12, "tags": [
                "pro_service_appointment", "thundermail_entity_area_webmail",
            ]},
            {"id": 4, "requester_id": 13, "tags": [
                "pro_service_thundermail", "thundermail_what_ui__webmail",
            ]},
            {"id": 5, "requester_id": 12, "tags": [
                "thundermail_what_ui__webmail", "thundermail_entity_area_webmail",
            ]},
        ]
        with patch.object(load, "fetch_window_tickets", return_value=tickets):
            result = load.monthly_zendesk_requesters(
                dt.date(2026, 8, 1), dt.date(2026, 9, 1)
            )

        self.assertEqual(result["eligible_tickets"], 5)
        self.assertEqual(result["unique_requesters"], 3)
        self.assertEqual(result["services"]["Send"], {
            "tickets": 2, "unique_requesters": 1,
        })
        self.assertEqual(result["entity_areas"]["webmail"], {
            "tickets": 3, "unique_requesters": 2,
        })
        self.assertEqual(result["webmail"], {
            "tickets": 4, "unique_requesters": 3,
        })

    def test_yaml_block_replaces_without_disturbing_manual_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "month.yaml"
            path.write_text("month: August\nnarrative:\n  lede: keep me\n")
            load.write_monthly_yaml(path, {"month": "2026-08", "unique_requesters": 10})
            first = path.read_text()
            load.write_monthly_yaml(path, {"month": "2026-08", "unique_requesters": 11})
            second = path.read_text()

        self.assertIn("lede: keep me", second)
        self.assertEqual(second.count("THUNDERMAIL LOAD (generated"), 1)
        self.assertNotIn("unique_requesters: 10", second)
        self.assertIn("unique_requesters: 11", second)
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
