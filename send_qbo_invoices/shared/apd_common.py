from datetime import datetime
import json
import logging
import os
from typing import Any
from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table
from mypy_boto3_secretsmanager import SecretsManagerClient

def get_secrets(secret_name_env: str, aws_secretsmanager: SecretsManagerClient) -> dict[str, str]:
    """Retrieve the secret from AWS Secrets Manager."""
    secret_name = None
    try:
        secret_name = os.environ[secret_name_env]
        logging.debug(f"Fetching secret: {secret_name}")

        secret_value = aws_secretsmanager.get_secret_value(SecretId=secret_name)
        return json.loads(secret_value["SecretString"])

    except KeyError:
        logging.error(f"Environment variable '{secret_name_env}' not set")
        raise
    except aws_secretsmanager.exceptions.ResourceNotFoundException:
        logging.error(f"Secret '{secret_name or secret_name_env}' not found in Secrets Manager")
        raise
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in secret '{secret_name or secret_name_env}': {e}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error fetching secret '{secret_name or secret_name_env}': {e}")
        raise

def update_secret(secret_name_env: str, secret_values: dict[str, str], aws_secretsmanager: SecretsManagerClient) -> None:
    """Update the secret in AWS Secrets Manager with current vault values."""
    secret_name = None
    try:
        secret_name = os.environ[secret_name_env]
        logging.debug(f"Updating secret: {secret_name}")

        aws_secretsmanager.update_secret(
            SecretId=secret_name,
            SecretString=json.dumps(secret_values)
        )
        logging.info(f"Successfully updated secret: {secret_name}")

    except KeyError:
        logging.error(f"Environment variable '{secret_name_env}' not set")
        raise
    except aws_secretsmanager.exceptions.ResourceNotFoundException:
        logging.error(f"Secret '{secret_name or secret_name_env}' not found in Secrets Manager")
        raise
    except Exception as e:
        logging.error(f"Unexpected error updating secret '{secret_name or secret_name_env}': {e}")
        raise

def get_dynamodb_table(table_name_env: str, aws_dynamodb: DynamoDBServiceResource) -> Table:
    """Retrieve the DynamoDB table resource."""
    table_name = None
    try:
        table_name = os.environ[table_name_env]
        logging.debug(f"Accessing DynamoDB table: {table_name}")

        table = aws_dynamodb.Table(table_name)
        return table

    except KeyError:
        logging.error(f"Environment variable '{table_name_env}' not set")
        raise
    except Exception as e:
        logging.error(f"Unexpected error accessing DynamoDB table '{table_name or table_name_env}': {e}")
        raise

def get_dynamodb_item(table: Table, key: dict[str, Any]) -> dict[str, Any]|None:
    """Retrieve an item from the DynamoDB table by key."""
    try:
        response = table.get_item(Key=key)
        return response.get('Item', None)

    except Exception as e:
        logging.error(f"Error retrieving item with key {key} from DynamoDB: {e}")
        raise

def append_date_to_filename(file_name:str, with_time:bool=False):
    """
    # `append_date_to_filename` Function

    This function appends the current date, and optionally the time, to a given filename, preserving the file extension if present.

    ## Parameters

    `file_name` (str): The original name of the file.
    `with_time` (bool, optional): A flag to include the current time along with the date. Defaults to False.

    ## Usage

    ```python
    new_name_with_date = append_date_to_filename("example.txt")  # Appends only the date
    new_name_with_date_and_time = append_date_to_filename("example.txt", with_time=True)  # Appends both date and time

    ```

    ## Returns

    `str`: The new filename with the date appended.


    """
    if with_time:
        date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    else:
        date = datetime.now().strftime("%Y-%m-%d")

    # Splitting the file name by the last '.' to separate the extension
    name_parts = file_name.rsplit(".", 1)
    if len(name_parts) == 2:
        # If there is an extension, insert the date between the name and the extension
        new_file_name = f"{name_parts[0]}_{date}.{name_parts[1]}"
    else:
        # If there is no extension, just append the date to the file name
        new_file_name = f"{file_name}_{date}"

    return new_file_name

class APD_Html_Template: #NOSONAR
    """
    # `APD_Html_Template` Class
    
    A class for handling HTML templates, allowing for dynamic data replacement and validation.

    This class is designed to work with HTML templates that contain placeholders in the format `[[key]]`. It provides functionality to load a template from a file, replace placeholders with actual data, and validate that all placeholders have been filled and all provided data has been used.

    ## Initialization Parameters

    - `template_path` (str): The file path to the HTML template.
    - `data` (dict, optional): A dictionary containing key-value pairs for replacing placeholders in the template. Defaults to None.

    ## Usage

    ```python
    template = APD_Html_Template("path/to/template.html", {"name": "John Doe", "date": "2023-01-01"})
    print(template.html())  # Outputs the template with replaced tokens
    ```

    ## Methods

    - `replace_tokens`: Replaces placeholders in the template with values from the provided data dictionary.
    - `check_unfilled_tokens`: Checks for any placeholders in the template that were not replaced.
    - `check_unused_data`: Checks if there are any keys in the provided data that were not used in the template.
    - `html`: Returns the current state of the template content.

    The class encourages starting with both the template and data for developing dynamic HTML content, while providing methods (`check_unfilled_tokens` and `check_unused_data`) for validation to ensure that all placeholders are filled and all data is utilized.
    """

    def __init__(self, template_path: str, data: dict[str, str]|None = None):
        """
        Initializes the APD_Html_Template object with a template path and optional data.

        Parameters:
        - `template_path` (str): The path to the template file.
        - `data` (dict, optional): Data to replace the placeholders in the template. Defaults to None.
        """
        self.template_path = template_path
        self.template_content = ""
        self.data = data
        
        with open(self.template_path, "r", encoding="utf-8") as file:
            self.template_content = file.read()
        
        if data is not None:
            self.replace_tokens(data)

    def replace_tokens(self, data: dict[str, str]):
        """
        Replaces placeholders in the template with values from the provided data dictionary.

        Parameters:
        - `data` (dict): A dictionary of key-value pairs where each key corresponds to a placeholder in the template.
        """
        self.data = data
        
        for key, value in data.items():
            self.template_content = self.template_content.replace(
                f"[[{key}]]", str(value)
            )

    def check_unfilled_tokens(self):
        """
        Checks for any placeholders in the template that were not replaced by the provided data.

        Returns:
        - `tuple`: A tuple where the first element is a boolean indicating if there are unfilled tokens, and the second element is a list of the unfilled tokens' keys.
        """
        import re

        pattern = re.compile(r"\[\[(.*?)\]\]")
        matches = pattern.findall(self.template_content)

        if matches:
            return True, list(set(matches))
        else:
            return False, []

    def check_unused_data(self):
        """
        Checks if there are any keys in the provided data that were not used in the template.

        Returns:
        - `list`: A list of keys from the data that were not used in the template.
        """
        if self.data is None:
            raise ValueError("No data was provided to the template object")
        
        unused_keys = []
        
        for key in self.data.keys():
            if f"[[{key}]]" not in self.template_content:
                unused_keys.append(key)
        return unused_keys

    def html(self):
        """
        Returns the current state of the template content.

        Returns:
        - `str`: The HTML content of the template with data replaced.
        """
        return self.template_content