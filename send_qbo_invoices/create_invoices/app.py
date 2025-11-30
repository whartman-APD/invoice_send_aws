import json
from typing import Any
import sys
import os

# Add shared directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))

from shared.task_minutes_to_clickup_and_qbo import process_all_clients


def lambda_handler(event: dict[str, Any], context: object):
    """Lambda handler for creating monthly QuickBooks Online invoices.

    This function creates invoices from recurring transactions or templates
    on a monthly schedule.

    Parameters
    ----------
    event: dict, required
        EventBridge schedule event
        Event doc: https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-run-lambda-schedule.html

    context: object, required
        Lambda Context runtime methods and attributes
        Context doc: https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html

    Returns
    -------
    dict
        Response with statusCode 200 and success indicator
    """
    print("Create invoices function triggered - implementation pending")

    success = process_all_clients()
    if success:
        return {
            "statusCode": 200,
            "body": json.dumps({"ok": True, "message": "Invoices createed successfully"})
        }
    else:
        return {
            "statusCode": 500,
            "body": json.dumps({"ok": False, "message": "Failed to process invoices"})
        }