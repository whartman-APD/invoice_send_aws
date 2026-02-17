import logging
import os
from datetime import datetime, timezone
from urllib.parse import urlparse

import boto3
import pyodbc
import requests

import apd_common

ROBOCORP_BASE_URL = "https://cloud.robocorp.com/api/v1"


def sync_robocorp_processes_to_sql() -> bool:
    """Fetch Robocorp process/assistant data and upsert into Azure SQL Server."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s',
        force=True
    )
    logging.info("Starting Robocorp process sync to Azure SQL...")

    try:
        sql_config = _get_sql_config()
    except ValueError as e:
        logging.error(f"Configuration error: {e}")
        return False

    aws_region = os.environ.get("AWS_REGION", "us-west-2")

    try:
        aws_secretsmanager = boto3.client("secretsmanager", region_name=aws_region)
        aws_dynamodb = boto3.resource('dynamodb', region_name=aws_region)
        robocorp_vault = apd_common.get_secrets("ROBOCORP_API_SECRET_NAME", aws_secretsmanager)
        client_orgs_table = apd_common.get_dynamodb_table("DYNAMODB_TABLE_ROBOCORP_CLIENTS", aws_dynamodb)
    except Exception as e:
        logging.error(f"Failed to initialize AWS resources: {e}")
        return False

    try:
        sql_connection = _connect_to_azure_sql(sql_config)
        logging.info("Connected to Azure SQL Server")
    except Exception as e:
        logging.error(f"Failed to connect to Azure SQL Server: {e}")
        return False

    success_count = 0
    error_count = 0

    try:
        clients = client_orgs_table.scan()['Items']
        logging.info(f"Found {len(clients)} clients in DynamoDB")

        for item in clients:
            client_number = item['client_number']
            workspace_id = item['workspace_id']

            robocorp_api_key = robocorp_vault.get(client_number)
            if not robocorp_api_key:
                logging.warning(f"No Robocorp API key for client {client_number}, skipping")
                error_count += 1
                continue

            try:
                _sync_client_processes(
                    sql_connection, client_number, workspace_id, robocorp_api_key
                )
                success_count += 1
            except Exception as e:
                logging.error(f"Error syncing client {client_number}: {e}")
                error_count += 1

        logging.info(f"Sync complete. Success: {success_count}, Errors: {error_count}")
    except Exception as e:
        logging.error(f"Error during sync process: {e}")
        return False
    finally:
        sql_connection.close()
        logging.info("Azure SQL connection closed")

    return error_count == 0


def _get_sql_config() -> dict[str, str]:
    """Retrieve Azure SQL configuration from environment variables."""
    required_vars = [
        "AZURE_SQL_SERVER",
        "AZURE_SQL_DATABASE",
        "AZURE_SQL_USERNAME",
        "AZURE_SQL_PASSWORD",
    ]

    config = {}
    missing = []
    for var in required_vars:
        value = os.environ.get(var)
        if not value:
            missing.append(var)
        else:
            config[var] = value

    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    return config


def _connect_to_azure_sql(config: dict[str, str]) -> pyodbc.Connection:
    """Establish connection to Azure SQL Server."""
    connection_string = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={config['AZURE_SQL_SERVER']};"
        f"DATABASE={config['AZURE_SQL_DATABASE']};"
        f"UID={config['AZURE_SQL_USERNAME']};"
        f"PWD={config['AZURE_SQL_PASSWORD']};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
        f"Connection Timeout=30;"
    )
    return pyodbc.connect(connection_string)


def _sync_client_processes(
    sql_connection: pyodbc.Connection,
    client_number: str,
    workspace_id: str,
    robocorp_api_key: str,
) -> None:
    """Sync all processes and assistants for a single client."""
    header = {
        "Content-Type": "application/json",
        "Authorization": f"RC-WSKEY {robocorp_api_key}",
    }

    workspace_info = _get_workspace_info(workspace_id, header)
    workspace_name = workspace_info.get("name", "")
    workspace_text_id = _parse_workspace_text_id(workspace_info.get("url", ""))
    client_name = workspace_info.get("organization", {}).get("name", "")

    logging.info(f"  Client {client_number}: workspace={workspace_name}, org={client_name}")

    unattended_processes = _get_paginated_data(
        f"{ROBOCORP_BASE_URL}/workspaces/{workspace_id}/processes", header
    )
    assistant_processes = _get_paginated_data(
        f"{ROBOCORP_BASE_URL}/workspaces/{workspace_id}/assistants", header
    )

    logging.info(
        f"  Found {len(unattended_processes)} processes, {len(assistant_processes)} assistants"
    )

    all_rows = []
    for process in unattended_processes + assistant_processes:
        all_rows.append({
            "process_id": process["id"],
            "process_name": process["name"],
            "workspace_id": workspace_id,
            "workspace_text_id": workspace_text_id,
            "workspace_name": workspace_name,
            "client_number": client_number,
            "client_name": client_name,
        })

    if all_rows:
        _upsert_processes(sql_connection, all_rows)
        logging.info(f"  Upserted {len(all_rows)} rows for client {client_number}")


def _get_workspace_info(workspace_id: str, header: dict[str, str]) -> dict:
    """Fetch workspace metadata from Robocorp API."""
    url = f"{ROBOCORP_BASE_URL}/workspaces/{workspace_id}"
    response = requests.get(url, headers=header)
    response.raise_for_status()
    return response.json()


def _parse_workspace_text_id(workspace_url: str) -> str:
    """Extract workspace text ID from the workspace URL.

    Example: "https://cloud.robocorp.com/automatademo91rcl/production"
             → "automatademo91rcl"
    """
    path = urlparse(workspace_url).path.strip("/")
    parts = path.split("/")
    return parts[0] if parts else ""


def _get_paginated_data(url: str, header: dict[str, str]) -> list[dict]:
    """Fetch all pages from a paginated Robocorp API endpoint."""
    results = []
    query_params = {"limit": 500}

    while url:
        response = requests.get(url, headers=header, params=query_params)
        response.raise_for_status()
        response_json = response.json()
        results.extend(response_json.get("data", []))
        url = response_json.get("next") if response_json.get("has_more") else None
        query_params = {}

    return results


def _upsert_processes(connection: pyodbc.Connection, processes: list[dict]) -> None:
    """Upsert process records into dbo.dim_processes using MERGE."""
    merge_sql = """
    MERGE dbo.dim_processes AS target
    USING (SELECT ? AS process_id, ? AS process_name, ? AS workspace_id,
                  ? AS workspace_text_id, ? AS workspace_name, ? AS client_number,
                  ? AS client_name, ? AS last_synced_at) AS source
    ON target.process_id = source.process_id
    WHEN MATCHED THEN
        UPDATE SET
            process_name = source.process_name,
            workspace_id = source.workspace_id,
            workspace_text_id = source.workspace_text_id,
            workspace_name = source.workspace_name,
            client_number = source.client_number,
            client_name = source.client_name,
            last_synced_at = source.last_synced_at
    WHEN NOT MATCHED THEN
        INSERT (process_id, process_name, workspace_id, workspace_text_id,
                workspace_name, client_number, client_name, last_synced_at)
        VALUES (source.process_id, source.process_name, source.workspace_id,
                source.workspace_text_id, source.workspace_name, source.client_number,
                source.client_name, source.last_synced_at);
    """

    cursor = connection.cursor()
    try:
        current_time = datetime.now(timezone.utc)
        for process in processes:
            cursor.execute(
                merge_sql,
                process["process_id"],
                process["process_name"],
                process["workspace_id"],
                process["workspace_text_id"],
                process["workspace_name"],
                process["client_number"],
                process["client_name"],
                current_time,
            )
        connection.commit()
    except Exception as e:
        logging.error(f"Error during upsert: {e}")
        connection.rollback()
        raise
    finally:
        cursor.close()


if __name__ == "__main__":
    sync_robocorp_processes_to_sql()
