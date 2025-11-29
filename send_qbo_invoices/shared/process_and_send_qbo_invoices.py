from datetime import datetime
import logging
import apd_quickbooksonline as quickbooks_online
import apd_msgraph_v2 as msgraph
import pandas
import apd_common
import boto3
import os
import json

def send_qbo_invoices() -> bool:
    
    # Email variables
    # Path to assets folder (Lambda runs from function directory, assets is at parent level)
    email_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'sent_invoices_email_template.html')
    bookkeeper_email = os.environ.get("BOOKKEEPER_EMAIL", "whartman@automatapracdev.com")
    sender_email = os.environ.get("SENDER_EMAIL", "robotarmy@automatapracdev.com")
    excluded_customers = os.environ.get("EXCLUDED_CUSTOMERS", "").split(",")
    aws_region = os.environ.get("AWS_REGION", "us-west-2")
    
    # Data variables
    current_date = datetime.now().strftime("%Y-%m-%d")
    column_names = ["Id", "Invoice Num", "Name", "Invoice Date", "Invoice Due", "Amount", "Status"]
    invoices_dataframe = pandas.DataFrame(columns=column_names)
    logging.info("Starting invoice send process...")
    
    # Get secrets and intialize instances
    aws_secretsmanager = boto3.client("secretsmanager", region_name=aws_region)
    msgraph_vault = get_secrets("MSGRAPH_SECRET_NAME", aws_secretsmanager)
    quickbooks_online_vault = get_secrets("QBO_SECRET_NAME", aws_secretsmanager)
    msgraph_instance = msgraph.MsGraph(
        tenant=msgraph_vault["tenant_id"],
        client_id=msgraph_vault["client_id"],
        client_secret=msgraph_vault["client_secret_value"],
    )
    quickbooks_online_instance = quickbooks_online.QuickBooksOnline(quickbooks_online_vault)

    # Write tokens back to secrets manager
    update_secret("QBO_SECRET_NAME", quickbooks_online_instance.vault_values, aws_secretsmanager)

    # Get invoices for today
    query = f"select * from Invoice where TxnDate = '{current_date}'"
    invoices = quickbooks_online_instance.query_invoices(query)
    if invoices['QueryResponse'].get('Invoice') is None:
        logging.info("No invoices found for today.")
        return True
    
    # Loop through invoices and send them
    invoice_rows = []
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
        elif invoice_row['Name'] in excluded_customers:
            invoice_row["Status"] = "Excluded - Do Not Send"
        else:
            try:
                quickbooks_online_instance.send_invoice(invoice['Id'])
                invoice_row["Status"] = "Sent"
            except quickbooks_online.QBOError as e:
                logging.error(f"Failed to send invoice {invoice['Id']}: {e}")
                invoice_row["Status"] = f"Error: {str(e)}"

        invoice_rows.append(invoice_row)
    invoices_dataframe = pandas.DataFrame(invoice_rows)
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
    success = send_email(email_path, bookkeeper_email, sender_email, msgraph_instance, data_to_email)

    return success

def send_email(email_path: str, bookkeeper_email: str, sender_email: str, msgraph_instance: msgraph.MsGraph, data_to_email: dict[str, str]) -> bool:
    logging.info("Preparing and sending email...")
    template = apd_common.APD_Html_Template(email_path, data_to_email)
    email_to_recipients = []
    email_to_recipients.append({"emailAddress": {"address": bookkeeper_email}})
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
    issues, _ = msgraph_instance.send_email(email_payload, alternate_email_username_for_sending=sender_email)
    if issues:
        logging.warning(f"Issues encountered while sending email: {issues}")
        return False
    else:
        logging.info("Email sent successfully.")
        return True

def get_secrets(secret_name_env: str, aws_secretsmanager: boto3.client) -> dict[str, str]:
    secret_name = os.environ[secret_name_env]
    secret_value = aws_secretsmanager.get_secret_value(SecretId=secret_name)
    return json.loads(secret_value["SecretString"])

# Add this method to the QuickBooksOnline class
def update_secret(secret_name_env: str, secret_values: dict[str, str], aws_secretsmanager: boto3.client) -> None:
    """Update the secret in AWS Secrets Manager with current vault values."""
    secret_name = os.environ[secret_name_env]
    aws_secretsmanager.update_secret(
        SecretId=secret_name,
        SecretString=json.dumps(secret_values)
    )

    
if __name__ == "__main__":
    send_qbo_invoices()