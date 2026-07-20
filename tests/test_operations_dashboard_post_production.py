import importlib.util
import json
import unittest
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "operations_audit",
    ROOT / "scripts" / "operations-audit.py",
)
operations_audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(operations_audit)


class OperationsDashboardPostProductionTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.fromisoformat("2026-07-18T10:00:00-04:00")
        self.base_item = {
            "show_key": "breach-of-protocol",
            "show_name": "Breach of Protocol",
            "episode_time": "2026-07-17T15:00:00-04:00",
            "date_time": "2026-07-17T15:00:00-04:00",
            "episode_end_time": "2026-07-17T16:00:00-04:00",
            "calendar_event_found": True,
            "issues": [],
            "post_production_workflow": [
                "Podcast upload",
                "Newsletter recap",
                "Clips",
                "Transcript",
            ],
            "checklist_statuses": [
                {"key": "recording_exists", "label": "Recording exists", "status": "Complete", "due_stage": "post_show"},
                {"key": "transcript_exists", "label": "Transcript exists", "status": "Unknown", "due_stage": "post_show"},
                {"key": "ai_clips_complete", "label": "Clips created", "status": "Complete", "due_stage": "post_show"},
                {"key": "newsletter_complete", "label": "Newsletter/recap status checked", "status": "Unknown", "due_stage": "post_show"},
                {"key": "post_production_complete", "label": "Post-production complete", "status": "Unknown", "due_stage": "post_show"},
            ],
        }

    def test_completed_live_window_suppresses_preproduction_and_lists_remaining_work(self):
        item = operations_audit.finalize_schedule_item(dict(self.base_item), self.now)

        self.assertEqual("Post Production", item["workflow"]["current_phase"])
        self.assertEqual("Not Applicable", item["guest_status"])
        self.assertEqual("Not Applicable", item["topics_status"])
        self.assertEqual([], item["production_blockers"])
        self.assertIn("Podcast upload", item["unfinished_post_production_deliverables"])
        self.assertIn("Newsletter recap", item["unfinished_post_production_deliverables"])
        self.assertIn("Transcript", item["unfinished_post_production_deliverables"])
        self.assertNotIn("Clips", item["unfinished_post_production_deliverables"])

    def test_explicit_postproduction_completion_archives_episode_from_inbox(self):
        item = dict(self.base_item)
        item["checklist_statuses"] = [
            {"key": "post_production_complete", "label": "Post-production complete", "status": "Complete", "due_stage": "post_show"}
        ]
        finalized = operations_audit.finalize_schedule_item(item, self.now)
        sections = operations_audit.workflow_dashboard_sections([finalized], self.now, {})

        self.assertEqual("Complete", finalized["workflow"]["current_phase"])
        self.assertEqual([], sections["jessie_inbox"])

    def test_episode_without_configured_or_tracked_postproduction_work_is_archived(self):
        item = dict(self.base_item)
        item["post_production_workflow"] = []
        item["checklist_statuses"] = []
        finalized = operations_audit.finalize_schedule_item(item, self.now)

        self.assertEqual("Complete", finalized["workflow"]["current_phase"])
        self.assertEqual([], finalized["unfinished_post_production_deliverables"])

    def test_preshow_checklist_items_are_suppressed_after_scheduled_end(self):
        timeline_rules = json.loads((ROOT / "config" / "production_timeline_rules.json").read_text())
        episode = {
            "episode_time": self.base_item["episode_time"],
            "expected_calendar_end": self.base_item["episode_end_time"],
            "issues": [],
        }
        stage = operations_audit.production_stage_context(episode, timeline_rules, self.now)
        checklist = operations_audit.build_episode_checklist(episode, {}, timeline_rules, stage, self.now)

        self.assertTrue(checklist)
        self.assertTrue(
            all(item.get("due_stage") in {"post_show", "post_production"} for item in checklist)
        )
        self.assertNotIn("calendar_created", {item.get("key") for item in checklist})


class OperationsDashboardBrandStylingTests(unittest.TestCase):
    def test_stage_badges_use_distinct_reveting_brand_classes(self):
        self.assertEqual("production-setup", operations_audit.manager_status_class("Production Setup"))
        self.assertEqual("post-production", operations_audit.manager_status_class("Post Production"))
        self.assertNotEqual(
            operations_audit.manager_status_class("Production Setup"),
            operations_audit.manager_status_class("Post Production"),
        )

    def test_semantic_badges_use_requested_brand_classes(self):
        self.assertEqual("attention", operations_audit.manager_status_class("Needs Attention"))
        self.assertEqual("attention", operations_audit.manager_status_class("Blocked"))
        self.assertEqual("ready", operations_audit.manager_status_class("Ready"))
        self.assertEqual("info", operations_audit.manager_status_class("Informational"))
        self.assertEqual("info", operations_audit.manager_status_class("Monitor"))

    def test_dashboard_css_contains_brand_fonts_and_accessible_badge_pairings(self):
        dashboard_html = operations_audit.render_operations_manager_dashboard_html({})

        self.assertIn('font-family: "America"', dashboard_html)
        self.assertIn('font-family: "America Condensed"', dashboard_html)
        self.assertIn('font-family: "America Mono"', dashboard_html)
        self.assertIn("--brand-black: #000000", dashboard_html)
        self.assertIn("--brand-neon-green: #57e400", dashboard_html)
        self.assertIn("--brand-hot-pink: #FC0FC0", dashboard_html)
        self.assertIn("--brand-neutral: #fafafa", dashboard_html)
        self.assertIn(".badge.production-setup", dashboard_html)
        self.assertIn(".badge.post-production", dashboard_html)
        self.assertIn(".badge.attention", dashboard_html)


class PostProductionEmailReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.rules = {
            "shows": {
                "breach-of-protocol": {
                    "show_name": "Breach of Protocol",
                    "post_production_asset_email_required": True,
                    "post_production_asset_email_type": "Final post-production asset email",
                }
            }
        }
        self.item = {
            "show_key": "breach-of-protocol",
            "show_name": "Breach of Protocol",
            "episode_title": "The Cost of Moving Second | Episode 56",
            "calendar_event_title": "Breach of Protocol Episode 56 | The Cost of Moving Second",
            "episode_time": "2026-07-17T15:00:00-04:00",
            "episode_end_time": "2026-07-17T16:00:00-04:00",
            "guest_names": ["Sam Kushner", "Steven Oliphant", "Thomas Phillips"],
        }
        self.aliases = ["breach of protocol", "ridgeback network defense"]

    def message(self, **overrides):
        value = {
            "id": "message-1",
            "labels": ["SENT"],
            "sent_at": "2026-07-17T16:45:00-04:00",
            "to": ["Client Contact <client@example.com>"],
            "cc": [],
            "bcc": [],
            "subject": "Breach of Protocol Episode 56 post-show assets",
            "body": "Hi Sam Kushner, the full recording, transcript, and clips are ready in the organized Drive folder.",
        }
        value.update(overrides)
        return value

    def reconcile(self, messages):
        return operations_audit.reconcile_post_production_email(
            self.item,
            messages,
            self.aliases,
            self.rules,
            "Fresh",
        )

    def test_valid_external_post_show_asset_email(self):
        result = self.reconcile([self.message()])

        self.assertEqual("Verified Sent", result["status"])
        self.assertEqual("client@example.com", result["recipient"])
        self.assertEqual("Breach of Protocol Episode 56 post-show assets", result["matching_email_subject"])

    def test_internal_reminder_does_not_count(self):
        result = self.reconcile(
            [
                self.message(
                    to=["Test Producer <test-producer@reveting.com>", "Test Assistant <test-assistant@reveting.com>"],
                    subject="Reminder: Episode 56 assets still needed",
                    body="Internal deadline reminder for Breach of Protocol.",
                )
            ]
        )

        self.assertEqual("Not Sent / Not Found", result["status"])
        self.assertIn("internal-only", result["reason"])

    def test_day_of_show_email_does_not_count(self):
        result = self.reconcile(
            [
                self.message(
                    sent_at="2026-07-17T14:45:00-04:00",
                    subject="Breach of Protocol Episode 56 — you are live today",
                    body="Join StreamYard fifteen minutes early for today's show.",
                )
            ]
        )

        self.assertEqual("Not Sent / Not Found", result["status"])

    def test_asset_email_sent_before_show_does_not_count(self):
        result = self.reconcile([self.message(sent_at="2026-07-17T14:00:00-04:00")])

        self.assertEqual("Not Sent / Not Found", result["status"])

    def test_ambiguous_episode_match_needs_review(self):
        result = self.reconcile(
            [
                self.message(
                    subject="Your episode assets are ready",
                    body="Hi Sam Kushner, the recording and transcript are in the organized folder.",
                )
            ]
        )

        self.assertEqual("Needs Review", result["status"])
        self.assertIn("ambiguous", result["reason"])

    def test_completed_episode_with_no_matching_email(self):
        result = self.reconcile([])

        self.assertEqual("Not Sent / Not Found", result["status"])
        self.assertIn("No qualifying external post-show asset email", result["reason"])

    def test_conflicting_episode_number_is_not_an_ambiguous_match(self):
        result = self.reconcile(
            [self.message(subject="Breach of Protocol Episode 55 post-show assets")]
        )

        self.assertEqual("Not Sent / Not Found", result["status"])

    def test_email_matches_episode_number_guest_name_and_show_alias(self):
        result = self.reconcile([self.message()])
        match_types = {item["type"] for item in result["identifier_matches"]}

        self.assertEqual("Verified Sent", result["status"])
        self.assertTrue({"show_alias", "episode_number", "guest_name"}.issubset(match_types))

    def test_verified_email_clears_only_email_deliverable(self):
        item = dict(self.item)
        item["post_production_workflow"] = ["Clips", "Transcript"]
        item["checklist_statuses"] = []
        item["post_production_email_verification"] = self.reconcile([self.message()])

        unfinished = operations_audit.unfinished_post_production_deliverables(item)

        self.assertIn("Clips", unfinished)
        self.assertIn("Transcript", unfinished)
        self.assertNotIn("Final post-production asset email", unfinished)

    def test_missing_email_keeps_episode_active_without_other_postproduction_checklist(self):
        item = {
            "post_production_workflow": [],
            "checklist_statuses": [],
            "post_production_email_verification": {
                "status": "Not Sent / Not Found",
                "required_email_type": "Final post-production asset email",
            },
        }

        self.assertFalse(operations_audit.post_production_complete_for_schedule(item))
        self.assertEqual(
            operations_audit.unfinished_post_production_deliverables(item),
            ["Final post-production asset email"],
        )


if __name__ == "__main__":
    unittest.main()
