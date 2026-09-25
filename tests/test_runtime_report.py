import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pandas

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "send_qbo_invoices" / "shared"))
import task_minutes_to_clickup_and_qbo as invoices

# Billing August 2026 (the run on Sept 1-2): billing month = August, comparison month = July
BILLING = invoices.BillingPeriodConfig(reference_date=datetime(2026, 8, 1, tzinfo=timezone.utc))


def assistant_run(name: str, started_at: str, duration_seconds: int) -> dict:
    return {
        "id": f"run-{name}-{started_at}",
        "assistant": {"id": f"id-{name}", "name": name},
        "started_at": started_at,
        "duration": duration_seconds,
    }


def fake_assistant_api(runs: list[dict]) -> Mock:
    response = Mock()
    response.json.return_value = {"data": runs, "has_more": False}
    return Mock(return_value=response)


class AssistantRunsTests(unittest.TestCase):
    def call(self, runs: list[dict]):
        with patch.object(invoices.requests, "get", fake_assistant_api(runs)):
            return invoices.get_assistant_runs(
                BILLING.billing_period_start,
                BILLING.billing_period_end,
                BILLING.comparison_period_start,
                "workspace",
                {},
                "Org",
            )

    def test_bills_only_the_billing_month(self):
        total, export_stream, report_df = self.call([
            assistant_run("Payroll Helper", "2026-06-30T12:00:00Z", 600),   # before report window
            assistant_run("Payroll Helper", "2026-07-15T12:00:00Z", 120),   # comparison month: report only
            assistant_run("Payroll Helper", "2026-08-03T12:00:00Z", 61),    # billed: rounds up to 2
            assistant_run("Payroll Helper", "2026-08-31T23:00:00Z", 300),   # billed: 5
            assistant_run("Payroll Helper", "2026-09-01T00:30:00Z", 900),   # after billing month
        ])

        self.assertEqual(total, 7)

        exported = pandas.read_excel(export_stream, sheet_name="Assistant Runs")
        self.assertEqual(len(exported), 2)

        self.assertEqual(sorted(report_df["runtime"].tolist()), [2, 2, 5])
        self.assertEqual(set(report_df["started_at"].dt.month), {7, 8})

    def test_comparison_month_only_bills_zero_but_keeps_report_rows(self):
        total, export_stream, report_df = self.call([
            assistant_run("Payroll Helper", "2026-07-15T12:00:00Z", 120),
        ])

        self.assertEqual(total, 0)
        self.assertEqual(export_stream.getbuffer().nbytes, 0)
        self.assertEqual(len(report_df), 1)


class RuntimeReportTests(unittest.TestCase):
    def test_assistant_runs_keep_their_process_name_and_reach_the_pivot(self):
        with patch.object(invoices.requests, "get", fake_assistant_api([
            assistant_run("Payroll Helper", "2026-07-15T12:00:00Z", 120),
            assistant_run("Payroll Helper", "2026-08-03T12:00:00Z", 180),
        ])):
            _, _, assistant_df = invoices.get_assistant_runs(
                BILLING.billing_period_start, BILLING.billing_period_end, BILLING.comparison_period_start,
                "workspace", {}, "Org",
            )

        unattended_df = pandas.DataFrame({
            "process": [{"id": "p1", "name": "Invoice Bot"}, {"id": "p1", "name": "Invoice Bot"}],
            "started_at": pandas.to_datetime(["2026-07-10T08:00:00Z", "2026-08-10T08:00:00Z"]),
            "runtime": [10, 20],
        })

        report = invoices.build_runtime_report("10001", unattended_df, assistant_df, 0, 0.5)
        sheets = pandas.read_excel(report, sheet_name=None)

        run_data = sheets["Run Data"]
        self.assertEqual(sorted(run_data["Process"].unique()), ["Invoice Bot", "Payroll Helper"])

        pivot = sheets["Usage Pivot"].set_index("Process")
        self.assertEqual(pivot.loc["Payroll Helper", "2026-07"], 2)
        self.assertEqual(pivot.loc["Payroll Helper", "2026-08"], 3)
        self.assertEqual(pivot.loc["Invoice Bot", "2026-08"], 20)
        self.assertEqual(pivot.loc["Total", "2026-08"], 23)

        compare = sheets["Two Month Run Compare"].set_index("Day")
        self.assertEqual(compare.loc[3, "2026-08"], 3)
        self.assertEqual(compare.loc[15, "2026-07"], 2)

        overage = sheets["Overage Calculation"].columns.tolist() + sheets["Overage Calculation"].iloc[:, 1].tolist()
        self.assertIn(23, overage)

    def test_unnamed_runs_are_labelled_not_dropped(self):
        assistant_df = pandas.DataFrame({
            "Process Name": [None],
            "started_at": pandas.to_datetime(["2026-08-05T12:00:00Z"]),
            "runtime": [4],
        })

        report = invoices.build_runtime_report("10001", pandas.DataFrame(), assistant_df, 0, 0.5)
        pivot = pandas.read_excel(report, sheet_name="Usage Pivot").set_index("Process")

        self.assertEqual(pivot.loc["(Unknown process)", "2026-08"], 4)
        self.assertEqual(pivot.loc["Total", "2026-08"], 4)


if __name__ == "__main__":
    unittest.main()
