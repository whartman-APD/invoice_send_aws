import json
import os
import requests
import mimetypes
import logging
import time
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)

BASE_URL = "https://quickbooks.api.intuit.com"
MINOR_VERSION = 74

# Custom exceptions
class QBOError(Exception):
    """Base exception for QuickBooks Online errors."""
    pass

class QBOAuthError(QBOError):
    """Authentication/authorization error (401/403)."""
    pass

class QBORateLimitError(QBOError):
    """Rate limit exceeded (429)."""
    pass

class QBOValidationError(QBOError):
    """Validation error from QBO API (400)."""
    pass

class QBOServerError(QBOError):
    """Server-side error (5xx)."""
    pass

# Retry decorator
def retry_on_failure(
    max_retries: int = 3,
    backoff_factor: float = 1.0,
    retryable_statuses: tuple[int, ...] = (429, 500, 502, 503, 504)
) -> Callable[..., Any]:
    """Decorator to retry failed requests with exponential backoff."""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(self: "QuickBooksOnline", *args: Any, **kwargs: Any) -> Any:
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(self, *args, **kwargs)
                except requests.exceptions.HTTPError as e:
                    status_code = e.response.status_code if e.response is not None else None

                    # Handle 401 with token refresh (only once)
                    if status_code == 401 and attempt == 0:
                        logger.info("Access token expired, refreshing...")
                        try:
                            self.refresh_token()
                            continue
                        except Exception as refresh_error:
                            logger.error(f"Token refresh failed: {refresh_error}")
                            raise QBOAuthError(f"Authentication failed: {e}") from e

                    # Check if we should retry
                    if status_code in retryable_statuses and attempt < max_retries:
                        wait_time = backoff_factor * (2 ** attempt)
                        logger.warning(f"Request failed with {status_code}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        last_exception = e
                        continue

                    # Convert to appropriate custom exception
                    if status_code == 401 or status_code == 403:
                        raise QBOAuthError(f"Authentication failed: {e}") from e
                    elif status_code == 429:
                        raise QBORateLimitError(f"Rate limit exceeded: {e}") from e
                    elif status_code == 400:
                        raise QBOValidationError(f"Validation error: {e.response.text if e.response else e}") from e
                    elif status_code and status_code >= 500:
                        raise QBOServerError(f"Server error: {e}") from e
                    else:
                        raise

                except requests.exceptions.ConnectionError as e:
                    if attempt < max_retries:
                        wait_time = backoff_factor * (2 ** attempt)
                        logger.warning(f"Connection error, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        last_exception = e
                        continue
                    raise QBOError(f"Connection failed after {max_retries} retries: {e}") from e

                except requests.exceptions.Timeout as e:
                    if attempt < max_retries:
                        wait_time = backoff_factor * (2 ** attempt)
                        logger.warning(f"Request timeout, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        last_exception = e
                        continue
                    raise QBOError(f"Request timed out after {max_retries} retries: {e}") from e

            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
        return wrapper
    return decorator

class QuickBooksOnline:
    def __init__(self, vault_values: dict[str, str], oauth: bool = False) -> None:
        self.vault_values = vault_values
        if oauth:
            self.oauth_flow()
        else:
            self.refresh_token()

    def oauth_flow(self) -> None:
        """
        # `oauth_flow` Function

        This function performs the OAuth flow to get the access token and refresh token.

        ## Usage

        ```python
        vault_values = read_from_vault()
        oauth_flow(vault_values)
        ```

        ## Arguments

        - `vault_values`: The dictionary with the vault values.

        ## Returns

        This function returns the dictionary with the updated vault values.
        """
        pass
        
        # mfa = MFA() #NOSONAR
        # auth_url = mfa.generate_oauth_url(
        #     auth_url="https://appcenter.intuit.com/connect/oauth2",
        #     client_id=self.vault_values["client_id"],
        #     redirect_uri="https://www.automatapracdev.com/redirect",
        #     scope="com.intuit.quickbooks.accounting openid profile email phone address",
        #     client_secret=self.vault_values["client_secret"],
        # )
        # browser.configure()
        # browser.goto(auth_url)
        # browser.page().wait_for_url("**/*code=*", timeout=300000)
        # url = browser.page().url
        # token = mfa.get_oauth_token(
        #     token_url="https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer",
        #     client_secret=self.vault_values["client_secret"],
        #     response_url=url,
        # )
        # self.vault_values["access_token"] = token["access_token"]
        # self.vault_values["refresh_token"] = token["refresh_token"]
        # vault.set_secret(self.vault_values)

    def refresh_token(self) -> None:
        """
        # `refresh_token` Function

        This function refreshes the OAuth token.

        ## Usage

        ```python
        vault_values = read_from_vault()
        vault_values = refresh_token(vault_values)
        ```

        ## Arguments

        - `vault_values`: The dictionary with the vault values.

        ## Returns

        This function returns the dictionary with the updated vault values.

        """
    
        token_url = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
        auth = (self.vault_values["client_id"], self.vault_values["client_secret"])
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.vault_values["refresh_token"],
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        try:
            response = requests.post(token_url, auth=auth, data=data, headers=headers, timeout=30)
            response.raise_for_status()
            token = response.json()
            self.vault_values["access_token"] = token["access_token"]
            self.vault_values["refresh_token"] = token["refresh_token"]
            logger.info("Successfully refreshed OAuth token")
        except requests.exceptions.HTTPError as e:
            error_detail = e.response.text if e.response else str(e)
            logger.error(f"Token refresh failed: {error_detail}")
            logger.error(f"Full error response: {e.response.text}")  # Add this
            raise QBOAuthError(f"Failed to refresh token: {error_detail}") from e
        except requests.exceptions.RequestException as e:
            logger.error(f"Token refresh request failed: {e}")
            raise QBOError(f"Token refresh request failed: {e}") from e

    def _create_headers(self) -> dict[str, str]:
        """
        # `_create_headers` Function

        This function creates the headers for the API requests.

        ## Usage

        ```python
        vault_values = read_from_vault()
        headers = _create_headers(vault_values)
        ```

        ## Arguments

        - `vault_values`: The dictionary with the vault values.
        - `minorversion`: The minor version to use. Default is MINOR_VERSION.

        ## Returns

        This function returns the headers dictionary.
        """
        headers = {
            "Authorization": f"Bearer {self.vault_values['access_token']}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        return headers

    @retry_on_failure()
    def query_a_customer(self, query: str, minorversion: int = MINOR_VERSION) -> dict[str, Any]:
        """
        # `query_a_customer` Function

        This function queries a customer.

        ## Usage

        ```python

        vault_values = read_from_vault()
        customer = query_a_customer(vault_values, "select * from Customer Where FullyQualifiedName LIKE '10003 - %'")
        ```

        ## Arguments

        - `vault_values`: The dictionary with the vault values.
        - `query`: The query to run. Format is SQL. Example: "select * from Customer Where FullyQualifiedName LIKE '10003 - %'"
        - `minorversion`: The minor version to use. Default is MINOR_VERSION.

        ## Returns

        This function returns the response from the query.

        """
        url = f"{BASE_URL}/v3/company/{self.vault_values['realm_id']}/query"
        headers = self._create_headers()
        params = {"query": query, "minorversion": minorversion}
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    @retry_on_failure()
    def create_a_customer(self, customer: dict[str, Any]) -> dict[str, Any]:
        """
        # `create_a_customer` Function

        This function creates a customer.

        ## Usage

        ```python
        vault_values = read_from_vault()
        customer = {
            "DisplayName": "Automata Test",
            "PrimaryEmailAddr": {"Address": ""},
        }
        response = create_a_customer(vault_values, customer)
        ```

        ## Arguments

        - `vault_values`: The dictionary with the vault values.
        - `customer`: The customer dictionary to create. Reference the documentation for the full list of fields.
        - `minorversion`: The minor version to use. Default is MINOR_VERSION.

        ## Returns

        This function returns the response from the query.
        """

        url = f"{BASE_URL}/v3/company/{self.vault_values['realm_id']}/customer"
        headers = self._create_headers()
        response = requests.post(url, headers=headers, json=customer, timeout=30)
        response.raise_for_status()
        return response.json()

    @retry_on_failure()
    def read_a_recurring_transaction(self) -> dict[str, Any]:
        """
        # `read_a_recurring_transaction` Function

        This function reads a recurring transaction.

        ## Usage

        ```python
        vault_values = read_from_vault()
        response = read_a_recurring_transaction(vault_values)
        ```

        ## Arguments

        - `vault_values`: The dictionary with the vault values.

        ## Returns

        This function returns the response from the query.
        """
        url = f"{BASE_URL}/v3/company/{self.vault_values['realm_id']}/recurringtransaction"
        headers = self._create_headers()
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()

    @retry_on_failure()
    def create_a_recurring_transaction(self, recurring_transaction: dict[str, Any]) -> dict[str, Any]:
        """
        # `create_a_recurring_transaction` Function

        This function creates a recurring transaction.
        The recurring transaction dictionary uses Automata's example values for a new client for Amounts, Line Items, Names, email addresses, etc.
        The example dictionary for the `recurring_transaction` is not necessarily complete. Please refer to the QuickBooks API documentation for the full list of fields.

        ## Usage

        ```python
        vault_values = read_from_vault()
        recurring_transaction = {
            "AllowOnlineCreditCardPayment": true,
            "AllowOnlineACHPayment": true,
            "Line": [
                {
                "LineNum": 1,
                "Amount": "6000",
                "DetailType": "SalesItemLineDetail",
                "SalesItemLineDetail": {
                    "ItemRef": {
                        "value": "11",
                        "name": "Managed Automation Services"
                    },
                    "UnitPrice": "6000",
                    "Qty": 1,
                    "ItemAccountRef": {
                    "value": "5",
                    "name": "Services"
                    }
                }
                },
                {
                "Amount": "6000",
                "DetailType": "SubTotalLineDetail"
                }
            ],
            "RecurringInfo": {
                "Name": "X0005 - Test Client Accounting Firm",
                "RecurType": "Automated",
                "Active": true,
                "ScheduleInfo": {
                "IntervalType": "Monthly",
                "NumInterval": 1,
                "DayOfMonth": 8,
                "StartDate": "2024-04-08",
                "NextDate": "2024-04-08"
                }
            },
            "CustomerRef": {
                "value": "57",
                "name": "X0005 - Test Client Accounting Firm"
            },
            "SalesTermRef": {
                "value": "1",
                "name": "Due on receipt"
            },
            "PrintStatus": "NotSet",
            "EmailStatus": "NeedToSend",
            "BillEmail": {
                "Address": "whartman@automatapracdev.com"
            },
            "DeliveryInfo": {
                "DeliveryType": "Email"
            },
            "BillEmailCc": {
                "Address": "sentinvoices@automatapracdev.com"
            }
            }
        response = create_a_recurring_transaction(vault_values, recurring_transaction)
        ```
        ## Arguments

        - `vault_values`: The dictionary with the vault values.
        - `recurring_transaction`: The recurring transaction dictionary to create.

        ## Returns

        This function returns the response from the query.
        """
        url = f"{BASE_URL}/v3/company/{self.vault_values['realm_id']}/recurringtransaction"
        headers = self._create_headers()
        response = requests.post(url, headers=headers, json=recurring_transaction, timeout=30)
        response.raise_for_status()
        return response.json()

    @retry_on_failure()
    def create_invoice(self, invoice: dict[str, Any], minorversion: int = MINOR_VERSION) -> dict[str, Any]:
        """
        # `create_a_invoice` Function

        This function creates an invoice.

        ## Usage

        ```python
        vault_values = read_from_vault()
        invoice = {
            "AllowIPNPayment": true,
            "AllowOnlineCreditCardPayment": true,
            "AllowOnlineACHPayment": true,
            "Line": [
                {
                    "DetailType": "SalesItemLineDetail",
                    "Amount": 5000,
                    "SalesItemLineDetail": {
                        "ItemRef": {
                            "value": "11",
                            "name": "Managed Automation Services"
                        }
                    }
                }
            ],
            "CustomerRef": {
                "value": "49"
            },
            "BillEmail": {
                "Address": "user@domain.com"
            },
            "SalesTermRef": {
                "value": "1"
            }
        }
        response = create_a_invoice(vault_values, invoice)
        ```
        ## Arguments

        - `vault_values`: The dictionary with the vault values.
        - `invoice`: The invoice dictionary to create.

        ## Returns

        This function returns the response from the query.
        """

        url = f"{BASE_URL}/v3/company/{self.vault_values['realm_id']}/invoice"
        headers = self._create_headers()
        query_params = {"minorversion": minorversion}
        response = requests.post(url, headers=headers, json=invoice, params=query_params, timeout=30)
        response.raise_for_status()
        return response.json()

    @retry_on_failure()
    def send_invoice(self, invoice_id: str, minorversion: int = MINOR_VERSION) -> dict[str, Any]:
        """
        # `send_invoice` Function

        This function sends an invoice.

        ## Usage

        ```python
        invoice_id = "123"
        response = send_invoice(invoice_id, "123")
        ```

        ## Arguments

        - `invoice_id`: The invoice ID to send.
        - `minorversion`: The minor version to use. Default is MINOR_VERSION.

        ## Returns

        This function returns the response from the query.
        """
        url = f"{BASE_URL}/v3/company/{self.vault_values['realm_id']}/invoice/{invoice_id}/send"
        headers = self._create_headers()
        headers['Content-Type'] = "application/octet-stream"
        query_params = {"minorversion": minorversion}
        response = requests.post(url, headers=headers, params=query_params, timeout=30)
        response.raise_for_status()
        return response.json()

    @retry_on_failure()
    def query_invoices(self, query: str, minorversion: int = MINOR_VERSION) -> dict[str, Any]:
        """
        # `query_an_invoice` Function

        This function queries an invoice.

        ## Usage

        ```python
        query = "select * from Invoice"
        invoice = query_an_invoice(query)
        ```

        ## Arguments

        - `vault_values`: The dictionary with the vault values.
        - `query`: The query to run. Format is SQL. Example: "select * from Invoice" or "select * from Invoice where TxnDate = '2024-04-08'"

        ## Returns

        This function returns the response from the query.
        """
        url = f"{BASE_URL}/v3/company/{self.vault_values['realm_id']}/query"
        headers = self._create_headers()
        params = {"query": query, "minorversion": minorversion}
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    @retry_on_failure()
    def upload_attachment(self, file_path: str, object_type: str, object_id: str, minorversion: int = MINOR_VERSION) -> dict[str, Any]:
        """
        # `upload_attachment` Function

        This function uploads an attachment to a specific object in QuickBooks Online.

        ## Arguments

        - `file_path`: The path to the file to upload.
        - `object_type`: The type of the object to attach the file to (e.g., "Invoice").
        - `object_id`: The ID of the object to attach the file to.
        - `minorversion`: The minor version to use. Default is MINOR_VERSION.

        ## Returns

        This function returns the response from the upload request.
        """
        url = f"{BASE_URL}/v3/company/{self.vault_values['realm_id']}/upload"
        params = {
            "minorversion": minorversion,
        }
        headers = self._create_headers()
        headers.pop("Content-Type")  # Remove Content-Type to let requests set it with the multipart boundary
        content_type, _ = mimetypes.guess_type(file_path)
        if not content_type:
            raise ValueError("Unable to determine the content type of the file.")
        file_name = os.path.basename(file_path)
        metadata = {
            "AttachableRef": [
                {
                    "EntityRef": {"type": object_type, "value": object_id}, 
                    "IncludeOnSend": True
                }
            ],
            "ContentType": content_type,
            "FileName": file_name,
        }

        with open(file_path, 'rb') as file_data:
            files = {
                'file_metadata_01': ('metadata.json', json.dumps(metadata), 'application/json'),
                'file_content_01': (file_name, file_data, content_type)
            }

            response = requests.post(url, headers=headers, params=params, files=files, timeout=60)
            response.raise_for_status()
            return response.json()
