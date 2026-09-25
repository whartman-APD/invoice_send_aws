import io
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "send_qbo_invoices" / "shared"))
import task_minutes_to_clickup_and_qbo as invoices


class InvoiceCreationTests(unittest.TestCase):
    @patch.object(invoices.quickbooks_online, "QuickBooksOnline")
    def test_missing_billing_email_prevents_invoice_creation(self, quickbooks_class):
        quickbooks = quickbooks_class.return_value
        quickbooks.query_a_customer.return_value = {
            "QueryResponse": {"Customer": [{"Id": "42"}]}
        }

        with self.assertRaisesRegex(ValueError, "has no billing email"):
            invoices.generate_invoice({}, "10033", 100, 0, 0.5, 0, "Managed Service", "Client", "")

        quickbooks.create_invoice.assert_not_called()

    @patch.object(invoices.apd_common, "update_secret")
    @patch.object(invoices, "send_creation_summary")
    @patch.object(invoices, "send_files_to_sharepoint")
    @patch.object(invoices, "generate_invoice")
    @patch.object(invoices, "build_runtime_report", return_value=None)
    @patch.object(invoices, "send_data_to_clickup")
    @patch.object(invoices, "get_unattended_runs", return_value=pandas.DataFrame())
    @patch.object(invoices, "get_assistant_runs")
    @patch.object(invoices, "get_unattended_data_from_spreadsheet")
    @patch.object(invoices, "get_unattended_data_from_sharepoint", return_value=pandas.DataFrame())
    @patch.object(invoices.msgraph, "MsGraph")
    @patch.object(invoices.apd_common, "get_dynamodb_table")
    @patch.object(invoices.apd_common, "get_secrets")
    @patch.object(invoices.boto3, "resource")
    @patch.object(invoices.boto3, "client")
    def test_rate_gate_client_error_and_summary(self, boto_client, boto_resource, get_secrets, get_table,
                                   msgraph_class, get_sharepoint, get_spreadsheet,
                                   get_assistant, get_unattended, get_clickup, build_report,
                                   generate, send_files, send_summary, update_secret):
        get_secrets.side_effect = [{}, {}, {"10001": "key", "10002": "key", "10003": "key"},
                                   {"tenant_id": "", "client_id": "", "client_secret_value": "", "hostname": ""}]
        get_table.return_value.scan.return_value = {"Items": [
            {"client_number": "10003", "organization_id": "c", "workspace_id": "c"},
            {"client_number": "10001", "organization_id": "a", "workspace_id": "a"},
            {"client_number": "10002", "organization_id": "b", "workspace_id": "b"},
        ]}
        get_spreadsheet.return_value = (0, io.BytesIO(), "Org")
        get_assistant.return_value = (0, io.BytesIO(), pandas.DataFrame())
        get_clickup.side_effect = [
            (None, 0, 0, 0.5, "Managed Service", "Client", ""),
            (None, 125, 0, 0.5, "Managed Service", "Client", ""),
            (None, 200, 0, 0.5, "Managed Service", "Client", ""),
        ]
        generate.side_effect = [
            ValueError("QuickBooks customer for client 10002 has no billing email"),
            {"Invoice": {"Id": "99", "DocNumber": "INV-99", "TotalAmt": 200, "TxnDate": "2026-09-01"}},
        ]
        send_summary.return_value = True

        with patch.object(invoices, "CREATE_INVOICE", True):
            self.assertFalse(invoices.process_all_clients())

        self.assertEqual(generate.call_count, 2)
        self.assertEqual([call.args[1] for call in generate.call_args_list], ["10002", "10003"])
        created, errors = send_summary.call_args.args[1:]
        self.assertEqual(created[0]["Invoice ID"], "99")
        self.assertEqual(errors[0]["Client #"], "10002")
        self.assertEqual(len(errors), 1)
        update_secret.assert_called_once()
        self.assertEqual(update_secret.call_args.args[0], "QBO_SECRET_NAME")

    def test_summary_contains_escaped_error_and_invoice(self):
        msgraph = Mock()
        msgraph.send_email.return_value = (False, None)
        created = [{"Client #": "10001", "Invoice #": "INV-1", "Invoice ID": "99", "Amount": 125, "Invoice Date": "2026-09-01"}]
        errors = [{"Client #": "10002", "Error": "bad <email>"}]

        self.assertTrue(invoices.send_creation_summary(msgraph, created, errors))

        payload = msgraph.send_email.call_args.args[0]
        body = payload["message"]["body"]["content"]
        self.assertIn("INV-1", body)
        self.assertIn("bad &lt;email&gt;", body)
        self.assertIn("Invoices created: 1", body)
        self.assertIn("Errors: 1", body)


if __name__ == "__main__":
    unittest.main()
