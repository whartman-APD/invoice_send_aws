import json
from typing import Any
import sys
import os

# Add shared directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))

from shared.process_and_send_qbo_invoices import send_qbo_invoices


def lambda_handler(event: dict[str, Any], context: object):
    """Lambda handler for processing and sending QuickBooks Online invoices.

    Queries QuickBooks Online for today's invoices, sends them to clients,
    and emails a summary report to the bookkeeper via Microsoft Graph.

    Parameters
    ----------
    event: dict, required
        API Gateway Lambda Proxy Input Format or EventBridge schedule event
        Event doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html#api-gateway-simple-proxy-for-lambda-input-format

    context: object, required
        Lambda Context runtime methods and attributes
        Context doc: https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html

    Returns
    -------
    dict
        API Gateway Lambda Proxy Output Format with statusCode 200 and success indicator
        Return doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html
    """
    success = send_qbo_invoices()
    return {
        "statusCode": 200,
        "body": json.dumps({"ok": True, "message": "Invoices processed and sent successfully"})
    }
