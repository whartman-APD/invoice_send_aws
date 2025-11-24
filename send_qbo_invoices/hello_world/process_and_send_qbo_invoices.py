from datetime import datetime
from xmlrpc import client
import apd_quickbooksonline as quickbooks_online
import apd_msgraph_v2 as msgraph
import pandas
import apd_common
import boto3
import os
import json

def send_qbo_invoices():    
    apd_client_id = "10000"
    # Email variables
    email_path = "assets/sent_invoices_email_template.html"
    bookeeper_email = "whartman@automatapracdev.com"

    # Data variables
    current_date = datetime.now().strftime("%Y-%m-%d")
    column_names = ["Id", "Invoice Num", "Name", "Invoice Date", "Invoice Due", "Amount", "Status"]
    invoices_dataframe = pandas.DataFrame(columns=column_names)
    print("Starting invoice send process...")
    # Get secrets and intialize instances
    msgraph_vault = get_secrets("MSGRAPH_SECRET_NAME")
    quickbooks_online_vault = get_secrets("QBO_SECRET_NAME")
    msgraph_instance = msgraph.MsGraph(
        tenant=msgraph_vault["tenant_id"],
        client_id=msgraph_vault["client_id"],
        client_secret=msgraph_vault["client_secret_value"],
    )
    quickbooks_online_instance = quickbooks_online.QuickBooksOnline(quickbooks_online_vault)
    
    # Write tokens back to secrets manager
    update_secret("QBO_SECRET_NAME", quickbooks_online_instance.vault_values)

    # Get invoices for today
    query = f"select * from Invoice where TxnDate = '{current_date}'"
    invoices = quickbooks_online_instance.query_invoices(query)
    if invoices['QueryResponse'].get('Invoice') is None:
        print("No invoices found for today.")
        return
    
    # Loop through invoices and send them
    for invoice in invoices['QueryResponse']['Invoice']:
        invoice_row = {
            "Id": invoice['Id'],
            "Invoice Num": invoice['DocNumber'],
            "Name": invoice['CustomerRef']['name'],
            "Invoice Date": invoice['TxnDate'],
            "Invoice Due": invoice['DueDate'],
            "Amount": invoice['TotalAmt'], 
            "Status": "Not Sent"
        }
        if invoice_row['Amount'] == 0:
            invoice_row["Status"] = "Zero Amount"
        elif invoice_row['Name'] == "10001 - AICPA":
            continue
        else:
            try:
                quickbooks_online_instance.send_invoice(invoice['Id'])
                invoice_row["Status"] = "Sent"
            except Exception as e:
                print(e)
                invoice_row["Status"] = "Error"

        invoices_dataframe.loc[len(invoices_dataframe)] = invoice_row
    total_all_invoices = invoices_dataframe["Amount"].sum()
    formatted_total = "{:,}".format(total_all_invoices)
    # Set data email variables
    invoices_html_table = invoices_dataframe.to_html(index=False)
    data_to_email = {
        "invoices_table": invoices_html_table,
        "total_all_invoices": formatted_total,
        "invoice_count": len(invoices_dataframe)
    }

    # Setup email template from APD resource, email address to use, and email payload
    send_email(email_path, bookeeper_email, msgraph_instance, data_to_email)

def send_email(email_path: str, bookeeper_email: str, msgraph_instance: msgraph.MsGraph, data_to_email: dict[str, str]):
    print("Preparing and sending email...")
    template = apd_common.APD_Html_Template(email_path, data_to_email)
    email_to_recipients = []
    email_to_recipients.append({"emailAddress": {"address": bookeeper_email}})
    bcc_recipients = []
    email_payload = {
        "message": {
            "subject": "Invoices Sent Today",
            "body": {
                "contentType": "HTML",
                "content": template.template_content
            },
            "toRecipients": email_to_recipients,
            "bccRecipients": bcc_recipients
        },
        "saveToSentItems": "true"
    }

    # Send email and handle response using msgraph
    issues, response = msgraph_instance.send_email(email_payload, alternate_email_username_for_sending="robotarmy@automatapracdev.com")

def get_secrets(secret_name_env: str) -> dict[str, str]:
    secret_name = os.environ[secret_name_env]
    region_name = "us-west-2"
    sm = boto3.client("secretsmanager", region_name=region_name)
    secret_value = sm.get_secret_value(SecretId=secret_name)
    return json.loads(secret_value["SecretString"])

# Add this method to the QuickBooksOnline class
def update_secret(secret_name_env: str, secret_values: dict[str, str]) -> None:
    """Update the secret in AWS Secrets Manager with current vault values."""
    secret_name = os.environ[secret_name_env]
    region_name = "us-west-2"
    sm = boto3.client("secretsmanager", region_name=region_name)
    sm.update_secret(
        SecretId=secret_name,
        SecretString=json.dumps(secret_values)
    )

    
if __name__ == "__main__":
    send_qbo_invoices()