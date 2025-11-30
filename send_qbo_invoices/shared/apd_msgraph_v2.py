import json
from typing import Tuple
import requests
import logging
from jsonpath_ng.ext import parse
from datetime import datetime, timedelta

BASE_URL = "https://graph.microsoft.com/v1.0"

class MsGraph:
    def __init__(self, client_id:str, client_secret:str, tenant:str):
        """
        # `MsGraph` Class
        A class for interacting with the Microsoft Graph API.
        This class provides methods for sending emails and interacting with Sharepoint sites, lists, and drives.
        The class requires a dictionary of vault values that include the necessary credentials and information for authentication.
        The class handles the retrieval of an access token and includes methods for sending emails and interacting with Sharepoint resources.
        The class is designed to be used in conjunction with the `vault` module in Robocorp.
        """
        self.vault_values = {
            "tenant": tenant,
            "client_id": client_id,
            "client_secret_value": client_secret,
        }
        self.access_token = self.request_access_token()

    def refresh_client_secret(self):
        """
        # `refresh_client_secret` Function

        This function refreshes the client secret for the Microsoft Graph API.
        Refer to this link for more information: https://learn.microsoft.com/en-us/graph/api/application-addpassword?view=graph-rest-1.0&tabs=http
        If getting errors, check the permissions for the application in the Azure portal.

        ## Usage

        ```python
        refresh_client_secret()
        ```

        ## Returns

        This function returns the updated `vault_values` dictionary with the new client secret added.

        """
        print("Refreshing Client Secret")
        try:
            new_secret = self._add_password_credential()
            new_secret_key_id = new_secret["keyId"]
            self.vault_values["client_secret_value"] = new_secret["secretText"]
            self._remove_old_password_credentials(new_secret_key_id)
        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")
            raise e
        except KeyError as e:
            print(f"Key error: {e}")
            raise e

    def _add_password_credential(self, new_secret_display_name=None, new_secret_expiration=None):
        """
        # `_add_password_credential` Function

        This function adds a new password credential (client secret) to the specified application.

        ## Usage

        ```python
        _add_password_credential()
        ```

        ## Returns

        This function returns the response object from the POST request.

        """
        print("Adding a new password credential...")
        if new_secret_display_name is None:
            today_date = datetime.now().strftime("%Y-%m-%d")
            new_secret_display_name = f"Automata Connection {today_date}"
        if new_secret_expiration is None:
            new_secret_expiration = (datetime.now() + timedelta(days=730)).isoformat()
        url = f"{BASE_URL}/applications(appId='{self.vault_values['client_id']}')/addPassword"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "passwordCredential": {
                "displayName": new_secret_display_name,
                "endDateTime": new_secret_expiration,
            }
        }
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        print(f"New client secret created: {new_secret_display_name}")
        print("====================================")
        return response.json()

    def _remove_old_password_credentials(self, new_secret_key_id):
        print("Removing old password credentials...")
        url = f"{BASE_URL}/applications(appId='{self.vault_values['client_id']}')"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        existing_credentials = self._get_existing_password_credentials()
        
        # Keep only the new credential
        updated_credentials = [
            cred for cred in existing_credentials if cred["keyId"] == new_secret_key_id
        ]
        
        payload = {"passwordCredentials": updated_credentials}
        response = requests.patch(url, headers=headers, json=payload)
        response.raise_for_status()
        print("Old credentials removed successfully.")
        print("====================================")

    def _get_existing_password_credentials(self):
        url = f"{BASE_URL}/applications(appId='{self.vault_values['client_id']}')"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()["passwordCredentials"]

    def request_access_token(self):
        """
        # `request_access_token` Function

        This function requests an access token from Microsoft Graph API.

        ## Parameters

        `vault_values` (dict) must have the following keys: `tenant`, `client_id`, `client_secret_value`.

        ## Usage

        ```python
        request_access_token(vault_values)
        ```

        ## Returns

        This function returns the updated `vault_values` dictionary with the access token added.

        """
        print("Getting Access Token")
        url = (
            f"https://login.microsoftonline.com/{self.vault_values['tenant']}/oauth2/v2.0/token"
        )
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "client_id": self.vault_values["client_id"],
            "scope": "https://graph.microsoft.com/.default",
            "client_secret": self.vault_values["client_secret_value"],
            "grant_type": "client_credentials",
        }
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()  # This will raise an exception for HTTP error responses
        access_token = response.json().get("access_token")
        if access_token:
            return access_token
        else:
            raise ValueError("Failed to retrieve access token")

    def get_with_error_handling(self, url, headers, params=None):
        """
        # `get_with_error_handling` Function

        This function sends a GET request to the specified URL with the specified headers and parameters.

        ## Parameters

        `url` (str): The URL to which the GET request is to be sent.
        `headers` (dict): The headers to be included in the request.
        `params` (dict, optional): The parameters to be included in the request. Defaults to None.


        ## Usage

            ```python
            response = get_with_error_handling(url, headers, params)
            ```

        ## Returns

        This function returns the response object from the GET request.

        """
        print(f"Sending call to: {url}")
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
        except requests.exceptions.HTTPError as http_err:
            logging.error(f"HTTP error occurred: {http_err}")
            raise
        except requests.exceptions.RequestException as err:
            logging.error(f"Request error occurred: {err}")
            raise
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            raise
        else:
            return response

    def get_sharepoint_site(self, site_name):
        """
        # `get_sharepoint_site` Function

        This function gets the Sharepoint site with the specified name.

        ## Parameters

        `vault_values` (dict): The dictionary containing the vault values.
        `site_name` (str): The name of the Sharepoint site to be retrieved.

        ## Usage

        ```python
        get_sharepoint_site(vault_values, site_name)
        ```

        ## Returns

        This function returns the response object containing the Sharepoint site information.

        """
        print("Getting Sharepoint Site")
        url = f"{BASE_URL}/sites/{self.vault_values['SharepointHostName']}:/sites/{site_name}"
        print(url)
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        return self.get_with_error_handling(url, headers)

    def get_sharepoint_drives(self, siteid):
        """

        # `get_sharepoint_drives` Function

        This function gets the Sharepoint drive from the specified site.

        ## Parameters

        `vault_values` (dict): The dictionary containing the vault values.
        `siteid` (str): The ID of the Sharepoint site.

        ## Usage

        ```python
        get_sharepoint_drives(self, siteid)
        ```

        ## Returns

        This function returns the response object containing the Sharepoint drive information.

        """
        print("Getting Sharepoint drive from Site")
        url = f"{BASE_URL}/sites/{siteid}/drives"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        return self.get_with_error_handling(url, headers)

    def get_drive_id_by_name(self, drive_list_json, library_name):
        """
        # `get_drive_id_by_name` Function

        This function gets the drive ID by name from the list of drives.

        ## Parameters

        `drive_list_json` (list): The list of drives.
        `library_name` (str): The name of the library.

        ## Usage

        ```python
        get_drive_id_by_name(drive_list_json, library_name)
        ```

        ## Returns

        This function returns the ID of the drive.
        """
        print(f"Getting drive by name: {library_name}")
        drive_ids = []
        jsonpath_expression = parse(f"$.value[?(@.name == '{library_name}')].id")
        for match in jsonpath_expression.find(drive_list_json):
            drive_ids.append(match.value)
        if len(drive_ids) != 1:
            print("Error: Drive ID not found or multiple IDs")
            raise
        return drive_ids[0]
    
    def get_folders_in_drive(self, drive_id):
        """
        # `get_folders_in_drive` Function

        This function gets the folders in the specified Sharepoint drive.

        ## Parameters

        `vault_values` (dict): The dictionary containing the vault values.
        `drive_id` (str): The ID of the Sharepoint drive.

        ## Usage

        ```python
        get_folders_in_drive(vault_values, drive_id)
        ```

        ## Returns

        This function returns a list of folders in the Sharepoint drive.

        """
        print(f"Getting Folders in Drive")
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        url = f"{BASE_URL}/drives/{drive_id}/items/root/children"
        folders_json = []
        next_page = url
        while next_page is not None:
            response = self.get_with_error_handling(next_page, headers=headers)
            data = response.json()
            folders_json.extend(data.get("value", []))
            next_page = data.get("@odata.nextLink")

        return folders_json

    def get_item_name_starts_with(self, folder_list_json, starts_with):
        """

        # `get_folder_name_starts_with` Function

        This function gets the folder name that starts with the specified string.

        ## Parameters

        `folder_list_json` (list): The list of folders.
        `starts_with` (str): The string with which the folder name should start.

        ## Usage

        ```python
        get_folder_name_starts_with(folder_list_json, starts_with)
        ```

        ## Returns

        This function returns the name of the folder that starts with the specified string and the id of the folder.
        """
        print(f"Getting folder that starts with: {starts_with}")
        folder_names = []
        jsonpath_expression = parse(f"$[?(@.name =~ '{starts_with}.*')]")
        for match in jsonpath_expression.find(folder_list_json):
            folder_names.append(match.value)
        if len(folder_names) == 0:
            print("No folders found")
            return None, None
        elif len(folder_names) > 1:
            print("Error: multiple results found")
            print(folder_names)
            raise
        return folder_names[0]["name"], folder_names[0]["id"]

    def get_items_in_folder(self, drive_id, folder_id):
        """
        # `get_folders_in_folder` Function

        This function gets the folders in the specified Sharepoint folder.

        ## Parameters

        `vault_values` (dict): The dictionary containing the vault values.
        `drive_id` (str): The ID of the Sharepoint drive.
        `folder_id` (str): The ID of the Sharepoint folder.

        ## Usage

        ```python
        get_folders_in_folder(vault_values, drive_id, folder_id)
        ```

        ## Returns

        This function returns a list of folders in the Sharepoint folder.

        """
        print(f"Getting Folders in Folder")
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        url = f"{BASE_URL}/drives/{drive_id}/items/{folder_id}/children"
        folders_json = []
        next_page = url
        while next_page is not None:
            response = self.get_with_error_handling(next_page, headers=headers)
            data = response.json()
            folders_json.extend(data.get("value", []))
            next_page = data.get("@odata.nextLink")

        return folders_json
    
    def folder_path_exists_in_site(self, folder_path:str, site_name:str=None, site_id:str=None) -> bool:
        """
        Checks if a folder path exists in a SharePoint site. Needs either a site name, or the ID if you've already looked it up.
    
        :param folder_path: The path of the folder to check.
        :type folder_path: str
        :param site_name: The name of the SharePoint site. Either site_name or site_id must be provided.
        :type site_name: str, optional
        :param site_id: The ID of the SharePoint site. Either site_name or site_id must be provided.
        :type site_id: str, optional
        :return: True if the folder path exists, False otherwise.
        :rtype: bool
        :raises ValueError: If neither site_name nor site_id is provided.
        """
        if site_id is None:
            if site_name is None:
                raise ValueError("Either site_name or site_id must be provided.")
            site_id = self.get_sharepoint_site(site_name).json()['id']
        
        url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/root:/{folder_path}"
        headers = {
            'Authorization': f'Bearer {self.access_token}'
        }
        response = requests.get(url, headers=headers)
        exists = (response.status_code == 200)
        
        return exists
    
    def get_folder_id_from_path(self, drive_id, nested_path):
        """
        Gets the ID of the specified nested folder path in the SharePoint drive.
    
        :param drive_id: The ID of the SharePoint drive.
        :type drive_id: str
        :param nested_path: The nested path of the folder.
        :type nested_path: str
        :return: The ID of the nested folder.
        :rtype: str
        """
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        url = f"{BASE_URL}/drives/{drive_id}/root:/{nested_path}"
        response = self.get_with_error_handling(url, headers=headers)
        data = response.json()
        folder_id = data.get("id")
    
        return folder_id
    
    def get_file_from_nested_path(self, file_path, should_exist=None) -> dict|None:
        """
        :param str file_path: The path to the file on SharePoint.
        Expected Path - `"APDClientFiles/Documents/10020 - 10020 - YHB CPA/Logs"`
            - The first part of the path is the site name (`APDClientFiles`),
            - The second part of the path is the drive name (`Documents`),
            - The rest is the folder path, broken up by '/' (`10020 - 10020 - YHB CPA/Development/Logs`).
        """
        path_parts = file_path.split('/')
        site_name = path_parts[0]
        drive_name = path_parts[1]
        folder_path = '/'.join(path_parts[2:-1])
        file_name = path_parts[-1]
        #excel_log_parameters = [site_id, drive_id, file_id, table_name, data]
        print(f"••• Getting file from path: {file_path}...")
        print(f"\tSite:\t{site_name}")
        print(f"\tDrive:\t{drive_name}")
        print(f"\tPath:\t{folder_path}")
        print(f"\tFile:\t{file_name}")
        
        site_json = self.get_sharepoint_site(site_name).json()
        site_id = site_json['id']
        drive_list_json = self.get_sharepoint_drives(site_json['id']).json()
        drive_id = self.get_drive_id_by_name(drive_list_json,drive_name)
        folder_exists = self.folder_path_exists_in_site(folder_path, site_id=site_id)
        
        if not folder_exists:
            raise ValueError(f"\n\n\t(!) Folder Path does not exist...\n\t    /{folder_path}/\n\t    ...APD or Client needs to create it.")

        folder_id = self.get_folder_id_from_path(drive_id, folder_path)
        list_of_folder_items = self.get_items_in_folder(drive_id, folder_id)
        file_id = self.get_folder_item_id_by_name(list_of_folder_items, file_name) #test we can get a folder ID from the data
        
        file_exists = file_id is not None
        
        # An optional bit of error handling for static file usage        
        if should_exist and not file_exists:
            print(f"Checking if file exists: {file_path}")
            raise ValueError(f"File does not exist: {file_path}, and the code specified that it should. Check Drive and path.")
        
        item_to_return = None
        for item in list_of_folder_items:
            if item.get('name') == file_name:
                item_to_return = item 
                break

        return item_to_return

    def new_file_from_template_path(self, template_path: str, new_folder_path: str, new_file_name: str = None) -> requests.models.Response:
        """
        Copies a file from the template path to a new file path in SharePoint.
    
        :param template_path: The path to the template file on SharePoint.
        
        :type template_path: str
        
        :param new_folder_path: The path where the new file should be created on SharePoint. If this path contains the Library and Drive names as well and they match the template path, they will be stripped out. Copying to a different drive this this function is currently not supported, but is planned.
        
        :type new_folder_path: str

        :param new_file_name: The name of the new file. If not provided, the template file name will be used.

        :type new_file_name: str, optional

        :return: The response object from the copy operation.

        :rtype: requests.models.Response
        """
        template_file = self.get_file_from_nested_path(template_path, should_exist=True)
        if not template_file:
            raise ValueError(f"Template file does not exist: {template_path}.")

        #NOTE: Strip out the Drive name if its included in the path here from the template path, as it wont be needed on same-drive copies
        new_parts = new_folder_path.split('/')
        final_path = f"{new_folder_path}/{new_file_name}"
        template_parts = template_path.split('/')
        
        if new_parts[1] == template_parts[1] and new_parts[0] == template_parts[0]:
            new_folder_path = '/'.join(new_parts[2:])
        
        #TODO: Make a version that uses a different drive version. This is for same-drive copies
        
        new_file_name = new_file_name or template_file['name']
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        url = f"{BASE_URL}/drives/{template_file['parentReference']['driveId']}/items/{template_file['id']}/copy"
        data = {
            "parentReference": {
                "path": f"/drive/root:/{new_folder_path}"
            },
            "name": new_file_name
        }
        response = requests.post(url, headers=headers, json=data)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"HTTPError: {e}")
            print(f"Response content: {response.content}")
            raise
        file = self.get_file_from_nested_path(final_path, should_exist=True)
        
        return file
        
    def get_folder_item_id_by_name(self, folder_list_json, file_name) -> str|None:
        """
        Gets the file ID by name from the list of files.

        :param list folder_list_json: The list of files.
        :param str file_name: The name of the file.
        :return: The ID of the file.
        :rtype: str

        """
        print(f"Getting file by name: {file_name}")
        file_dict_list = []
        jsonpath_expression = parse(f"$[?(@.name == '{file_name}')].id")
        for match in jsonpath_expression.find(folder_list_json):
            file_dict_list.append(match.value)
        if len(file_dict_list) > 1:
            print("Error: Multiple IDs matched query")
            raise ValueError(f"Error: Multiple IDs matched in {file_name} -> {file_dict_list}")
        return file_dict_list[0] if file_dict_list else None

    def move_file_to_folder(self, drive_id, file_id, new_folder_id, file_name=None) -> requests.models.Response:
        """
        Moves a file to a folder in SharePoint.

        :param str drive_id: The ID of the SharePoint drive.
        :param str file_id: The ID of the file to be moved.
        :param str new_folder_id: The ID of the folder to which the file should be moved.
        :return: The response object from the API call.
        :rtype: requests.models.Response
        """
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        url = f'{BASE_URL}/drives/{drive_id}/items/{file_id}'
        data = {
            'parentReference': {
                'id': new_folder_id
            },
            "name": file_name
        }
        response = requests.patch(url, headers=headers, json=data)
        response.raise_for_status()
        return response    
    
    def upload_file_to_sharepoint(self, drive_id, path, filename, binary_data, content_type="application/json"):
        #TODO: Change to use this instead of create_file_in_folder and add content type
        print(f"preparing to upload file: {filename}")
        import urllib.parse
        encoded_filename = urllib.parse.quote(filename)
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": content_type,
        }
        url = f"{BASE_URL}/drives/{drive_id}/items/root:/{path}/{encoded_filename}:/content"
        try:
            response = requests.put(url, headers=headers, data=binary_data)
            response.raise_for_status()
        except requests.exceptions.HTTPError as http_err:
            logging.error(f"HTTP error occurred: {http_err}")
            raise
        except requests.exceptions.RequestException as err:
            logging.error(f"Request error occurred: {err}")
            raise
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            raise
        else:
            return response

    def download_file_from_sharepoint(self, graph_download_url: str) -> bytes:
        """
        Downloads a file from SharePoint using the Graph API.

        :param str graph_download_url: The download URL for the file. Usually obtained from the `@microsoft.graph.downloadUrl` property of a file.
        :return: The binary data of the file.
        :rtype: bytes
        """
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        url = f"{graph_download_url}"
        response = self.get_with_error_handling(url, headers=headers)
        return response.content

    def send_email(self, payload, alternate_email_username_for_sending=None) -> Tuple[bool, requests.models.Response]:
        """
        Send an Email Using the Microsoft Graph API

        Sends an email on behalf of the user specified in the `vault_values` dictionary using the Microsoft Graph API.
        Constructs the request with appropriate headers and payload containing the email details, then sends the request
        to the Graph API endpoint.

        Parameters:
            vault_values (dict): A dictionary containing the user information.
            payload (dict): A dictionary containing the email message details. The structure of the payload is as follows:
                ```json
                {
                    "message": {
                        "subject": "Your email subject here",
                        "body": {
                            "contentType": "HTML",
                            "content": "Your email body content here"
                        },
                        "toRecipients": [
                            {"emailAddress": {"address": "recipient@example.com"}}
                        ]
                    },
                    "saveToSentItems": "false"
                }
                ```
                This includes recipients, subject, body, and other relevant email parameters required by the Graph API.
            alternate_email_username_for_sending (str, optional): An alternate email address to use for sending the email.
                Overwrites the `vault_values['username']` value if set.

        Returns:
            bool: `False` if the email was sent successfully (HTTP status code 202), `True` if there were issues.
            requests.models.Response: The response object from the Graph API call.

        Notes:
            - Prints the response from the Graph API call.
            - If the response status code is not 202, it sets `issues` to True, indicating a problem with sending the email.
            - Add Graph API permissions for the 'application' to send emails on behalf of the user in the Azure portal.

        Example for adding an attachment:
            ```json
            "attachments": [
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": "Error Log.xlsx",
                    "contentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "contentBytes": "base64-encoded-bytes-here"
                }
            ]
            ```
        """
        response = None
        
        if alternate_email_username_for_sending is not None:
            self.vault_values['username'] = alternate_email_username_for_sending
        
        issues = False
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        
        # post to https://graph.microsoft.com/v1.0/me/sendMail
        url = f"{BASE_URL}/users/{self.vault_values['username']}/sendMail"
        try:
            response = requests.post(url, headers=headers, json=payload)
            print(response)
            
            if(response.status_code != 202):
                issues = True
                # logging.error(f"Error sending email: {response.text}")
                raise ValueError(f"Error sending email: {response.text}")
            
        except requests.exceptions.HTTPError as http_err:
            logging.error(f"HTTP error occurred: {http_err}")
            issues = True
        except requests.exceptions.RequestException as err:
            logging.error(f"Request error occurred: {err}")
            issues = True
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            issues = True
        
        return issues, response

    def search_for_sites(self, site_name):
        """

        # `search_for_sites` Function

        This function searches for Sharepoint sites with the specified name.

        ## Parameters

        `vault_values` (dict): The dictionary containing the vault values.
        `site_name` (str): The name of the Sharepoint site to be searched.

        ## Usage

        ```python
        search_for_sites(vault_values, site_name)
        ```

        ## Returns

        This function returns the response object containing the Sharepoint site information.

        """
        print(f"Searching for Sharepoint Site: {site_name}")
        url = f"{BASE_URL}/sites"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        query = {"search": site_name}
        return self.get_with_error_handling(url=url, headers=headers, params=query)


    def get_lists_in_site(self, site_id):
        """

        # `get_lists_in_site` Function

        This function gets the lists in the specified Sharepoint site.

        ## Parameters

        `vault_values` (dict): The dictionary containing the vault values.
        `site_id` (str): The ID of the Sharepoint site.

        ## Usage

        ```python
        get_lists_in_site(vault_values, site_id)
        ```

        ## Returns

        This function returns a list of lists in the Sharepoint site.

        """
        print(f"Getting Lists in Site")
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        url = f"{BASE_URL}/sites/{site_id}/lists"
        lists_json = []
        next_page = url
        while next_page is not None:
            response = self.get_with_error_handling(next_page, headers=headers)
            data = response.json()
            lists_json.extend(data.get("value", []))
            next_page = data.get("@odata.nextLink")

        return lists_json

    def get_list_id_by_name(self, lists_json, list_name):
        """

        # `get_list_id_by_name` Function

        This function gets the list ID by name from the list of lists.

        ## Parameters

        `lists_json` (list): The list of lists.
        `list_name` (str): The name of the list.

        ## Usage

        ```python
        get_list_id_by_name(lists_json, list_name)
        ```

        ## Returns

        This function returns the ID of the list.

        """
        print(f"Getting list by name: {list_name}")
        list_ids = []
        jsonpath_expression = parse(f"$[?(@['name']=='{list_name}')]['id']")
        for match in jsonpath_expression.find(lists_json):
            list_ids.append(match.value)
        if len(list_ids) != 1:
            print("Error: List ID not found or multiple IDs")
            raise
        return list_ids[0]


    def get_items_in_list(self, site_id, list_id, expand=True):
        """

        # `get_items_in_list` Function

        This function gets the items in the specified Sharepoint list.

        ## Parameters

        `vault_values` (dict): The dictionary containing the vault values.
        `site_id` (str): The ID of the Sharepoint site.
        `list_id` (str): The ID of the Sharepoint list.
        `expand` (bool, optional): Whether to expand the items which will show all the row data. Defaults to True.

        ## Usage

        ```python
        get_items_in_list(vault_values, list_id)
        ```

        ## Returns

        This function returns a list of items in the Sharepoint list.

        """
        print(f"Getting Items in List")
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        url = f"{BASE_URL}/sites/{site_id}/lists/{list_id}/items?"
        if expand:
            url += "expand=fields&"
        items_json = []
        next_page = url
        while next_page is not None:
            response = self.get_with_error_handling(next_page, headers=headers)
            data = response.json()
            items_json.extend(data.get("value", []))
            next_page = data.get("@odata.nextLink")

        return items_json

    def create_list_item(self, site_id, list_id, item_data):
        """

        # `create_list_item` Function

        This function creates an item in the specified Sharepoint list.

        ## Parameters

        `vault_values` (dict): The dictionary containing the vault values.
        `list_id` (str): The ID of the Sharepoint list.
        `item_data` (dict): The data for the item to be created.

        ## Usage

        ```python
        create_list_item(vault_values, list_id, item_data)
        ```

        ## Returns

        This function returns the response object containing the item information.

        """
        print(f"Creating List Item")
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        url = f"{BASE_URL}/sites/{site_id}/lists/{list_id}/items"
        response = requests.post(url, headers=headers, json=item_data)
        response.raise_for_status()
        return response

    def add_row_to_table_in_excel_file(self, site_id, drive_id, file_id, table_id, data):
        """
        Add a Row to a Table in an Excel File

        This function adds a row to a table in an Excel file in SharePoint.
        Use other SharePoint methods to get the `site_id`, `drive_id`, and `file_id`.

        Example Workflow:
            ```python
            response = graph_instance.get_sharepoint_site(msgraph_vault_values, sharepoint_site_name)
            site_id = response.json().get("id")
            response = graph_instance.search_for_sites(msgraph_vault_values, sharepoint_site_name)
            response = graph_instance.get_sharepoint_drives(msgraph_vault_values, site_id)
            drive_id = graph_instance.get_drive_id_by_name(response.json(), document_library_name)
            folder_list_json = graph_instance.get_folders_in_drive(msgraph_vault_values, drive_id)
            folder_name, folder_id = graph_instance.get_item_name_starts_with(folder_list_json, client_id)
            sub_folder_list_json = graph_instance.get_items_in_folder(drive_id, folder_id)
            folder_name, sub_folder_id = graph_instance.get_item_name_starts_with(sub_folder_list_json, "Minutes")
            sub_items_list_json = graph_instance.get_items_in_folder(drive_id, sub_folder_id)
            file_name, file_id = graph_instance.get_item_name_starts_with(sub_items_list_json, "2024-10-25.xlsx")
            ```

        The name of the table is known. Data needs to be in the following format, and the number of values should match the number of columns in the table:

        Example Data Format:
            ```json
            {
                "index": None,
                "values": [
                    ["value1", "value2", "value3"]
                ]
            }
            ```

        Example Usage:
            ```python
            row_data = {
                "id": "dfd",
                "Date Created": "2024-10-25",
                "Organization ID": "asdzvasdc",
                "Client Number": 10000,
                "Client Name": "Test Client",
                "Workspace UUID": "asdfasfd",
                "Workspace Name": "Test Workspace",
                "Process UUID": "afsdfsa",
                "Process Name": "Test Process",
                "Run Number": 12,
                "Run UUID": "asdfsf",
                "Minutes": 30
            }

            columns_order = [
                "id", "Date Created", "Organization ID", "Client Number", "Client Name",
                "Workspace UUID", "Workspace Name", "Process UUID", "Process Name",
                "Run Number", "Run UUID", "Minutes"
            ]
            
            #Create an array of arrays since it can enter multiple rows at once
            row_values = [[row_data[col] for col in columns_order]]
            
            data = {
                "index": None,  # None appends the row at the end
                "values": row_values
            }
            ```

        Parameters:
            site_id (str): The ID of the SharePoint site.
            drive_id (str): The ID of the SharePoint drive.
            file_id (str): The ID of the Excel file.
            table_id (str): The ID of the table in the Excel file.
            data (dict): The data for the row to be added.

        Returns:
            dict: A response object from the API call.

        Usage Example:
            ```python
            add_row_to_table_in_excel_file(site_id, drive_id, file_id, table_id, data)
            ```
        """
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        # url = f'{BASE_URL}/sites/{site_id}/drives/{drive_id}/root:/{file_path}:/workbook/tables/{table_name}/rows/add'
        url = f'{BASE_URL}/sites/{site_id}/drives/{drive_id}/items/{file_id}/workbook/tables/{table_id}/rows/add'

        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response

    def add_table_to_excel_file(self, site_id, drive_id, file_id, table_width):
        """
        Add a Table to an Excel File

        This function adds a table to an Excel file in SharePoint. It is commonly used after creating a new Excel file.

        Parameters:
            site_id (str): The ID of the SharePoint site.
            drive_id (str): The ID of the SharePoint drive.
            file_id (str): The ID of the Excel file.
            table_name (str): The name of the table to be added.
            columns (list): A list of column names for the table.

        Returns:
            dict: A response object containing the table information.

        Usage:
            ```python
            add_table_to_excel_file(site_id, drive_id, file_id, table_name, columns)
            ```
        """
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        url = f'{BASE_URL}/sites/{site_id}/drives/{drive_id}/items/{file_id}/workbook/tables/add'
        end_column = _convert_length_to_excel_column_letter(table_width)
        data = {
            "address": f"A1:{end_column}1",
            "hasHeaders": True,
        }

        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response

    def update_table_in_excel_file(self, site_id, drive_id, file_id, table_id, new_table_properties):
        """
        Update Table in Excel File

        This function updates the properties of a table in an Excel file in SharePoint.

        Parameters:
            site_id (str): The ID of the SharePoint site.
            drive_id (str): The ID of the SharePoint drive.
            file_id (str): The ID of the Excel file.
            table_id (str): The ID of the table to be updated.
            new_table_properties (dict): The new properties for the table.

        Usage:
            ```python
            update_table_in_excel_file(site_id, drive_id, file_id, table_id, new_table_properties)
            ```

        Notes:
            `new_table_properties` should be in the following format, but all fields are optional:
            ```json
            {
                "name": "New Table Name",
                "showHeaders": true,
                "showTotals": true,
                "style": "TableStyle"
            }
            ```
        """

        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        url = f'{BASE_URL}/sites/{site_id}/drives/{drive_id}/items/{file_id}/workbook/tables/{table_id}/'

        response = requests.patch(url, headers=headers, json=new_table_properties)
        response.raise_for_status()
        return response

def _convert_length_to_excel_column_letter(n):
    """Convert a number to an Excel column letter (e.g., 1 -> A, 27 -> AA). """
    letters = ''
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters

# Sample functions
def sample_upload_file_to_sharepoint():
    """
    # `sample_upload_file_to_sharepoint` Function

    This function is a sample function that demonstrates how to upload a file to Sharepoint.
    This was build for the Robocorp environment.

    ## Usage

    ```python
    sample_upload_file_to_sharepoint()
    ```
    """
    from robocorp import vault
    graph_session = MsGraph(vault.get_secret("graph_oauth_microsoft"))
    sharepoint_site_name = "APDClientFiles"
    document_library_name = "Documents"
    client_id = "10001"
    file_name = "test.txt"
    unknown_folder_path = "TaxDomeNoClientID"
    unknown_client_name = "John Doe"
    sub_folder = "TaxDomeImport"

    msgraph_vault_values = vault.get_secret(
        "graph_oauth_microsoft"
    )  # when used in roboframework, this will resolve
    
    response = graph_session.get_sharepoint_site(msgraph_vault_values, sharepoint_site_name)
    siteid = response.json().get("id")
    response = graph_session.search_for_sites(msgraph_vault_values, sharepoint_site_name)
    response = graph_session.get_sharepoint_drives(msgraph_vault_values, siteid)
    drive_id = graph_session.get_drive_id_by_name(response.json(), document_library_name)
    folder_list_json = graph_session.get_folders_in_drive(msgraph_vault_values, drive_id)
    folder_name = graph_session.get_folder_name_starts_with(folder_list_json, client_id)
    print(folder_name)

    with open(file_name, mode="rb") as file:
        fileContent = file.read()
    if folder_name is None:
        graph_session.upload_file_to_sharepoint(
            msgraph_vault_values,
            drive_id,
            f"{unknown_folder_path}/{unknown_client_name}",
            file_name,
            fileContent,
        )
    else:
        graph_session.upload_file_to_sharepoint(
            msgraph_vault_values,
            drive_id,
            f"{folder_name}/{sub_folder}",
            file_name,
            fileContent,
        )

def sample_add_data_to_excel_on_sharepoint():
    # send data into excel files on sharepoint. If the file does not exist, create it. If it does exist, append data to it.
    from . import apd_msgraph_v2 as msgraph # Set the . to resources
    from robocorp import vault
    import openpyxl
    from io import BytesIO
    from datetime import datetime, timedelta
    import random
    import uuid
    msgraph_vault_values = vault.get_secret("graph_oauth_microsoft")
    graph_instance = msgraph.MsGraph(msgraph_vault_values)
    
    # Sharepoint information
    sharepoint_site_name = "APDClientFiles"
    document_library_name = "Documents"
    apd_client_id = "10000"
    sub_folder_name = "Minutes"
    path = f"10000 - Automata Practice Development/Minutes"

    # File creation information
    date_created = (datetime.now()).strftime('%Y-%m-%d')
    # date_created = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
    file_name = f"{date_created}.xlsx"
    content_type_for_new_file = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    table_name = 'RunData'  # Assuming your table is named 'Table1'
    columns_order = ["id", "Date Created","Organization ID", "Client Number","Client Name","Workspace UUID","Workspace Name","Process UUID","Process Name","Run Number","Run UUID","Minutes"]
    
    #Sharepoint navigation
    response = graph_instance.get_sharepoint_site(sharepoint_site_name)
    site_id = response.json().get("id")
    response = graph_instance.search_for_sites(sharepoint_site_name)
    response = graph_instance.get_sharepoint_drives(site_id)
    drive_id = graph_instance.get_drive_id_by_name(response.json(), document_library_name)

    folder_list_json = graph_instance.get_folders_in_drive(drive_id)
    folder_name, folder_id = graph_instance.get_item_name_starts_with(folder_list_json, apd_client_id) # Find the client ID folder
    sub_folder_list_json = graph_instance.get_items_in_folder(drive_id, folder_id)
    folder_name, sub_folder_id = graph_instance.get_item_name_starts_with(sub_folder_list_json, sub_folder_name) # Find the Minutes folder
    sub_items_list_json = graph_instance.get_items_in_folder(drive_id, sub_folder_id)
    
    # Check if the file already exists
    file_exists = any(item['name'] == file_name for item in sub_items_list_json)
    if not file_exists:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "RunData"
        for col_num, column_title in enumerate(columns_order, 1):
            ws.cell(row=1, column=col_num, value=column_title)
        excel_buffer = BytesIO()
        wb.save(excel_buffer)
        excel_buffer.seek(0)
        #  new_file_response = graph_instance.create_file_in_folder(site_id, drive_id, sub_folder_id, file_name, excel_buffer.getvalue(), content_type=content_type_for_new_file)
        new_file_response = graph_instance.upload_file_to_sharepoint(drive_id, path, file_name, excel_buffer.getvalue(), content_type_for_new_file)
        file_id = new_file_response.json()['id']
        new_table_response = graph_instance.add_table_to_excel_file(site_id, drive_id, file_id, len(columns_order))

        new_table_properties = {
            "name": table_name,
        }
        table_update_response = graph_instance.update_table_in_excel_file(site_id, drive_id, file_id, new_table_response.json()['id'], new_table_properties)
    else:
        filename, file_id = graph_instance.get_item_name_starts_with(sub_items_list_json, file_name) # Find the correct file

    test_data = []

    for _ in range(50):
        client_number = str(random.randint(20000, 20020))
        minutes = random.randint(2, 60)
        id_uuid = str(uuid.uuid4())
        org_uuid = str(uuid.uuid4())
        workspace_uuid = str(uuid.uuid4())
        process_uuid = str(uuid.uuid4())
        run_uuid = str(uuid.uuid4())
        client_name = "Test Client"
        workspace_name = "Test Workspace"
        process_name = "Test Process"
        run_number = random.randint(1, 100)

        row_data = {
            "id": id_uuid,
            "Date Created": date_created,
            "Organization ID": org_uuid,
            "Client Number": client_number,
            "Client Name": client_name,
            "Workspace UUID": workspace_uuid,
            "Workspace Name": workspace_name,
            "Process UUID": process_uuid,
            "Process Name": process_name,
            "Run Number": run_number,
            "Run UUID": run_uuid,
            "Minutes": minutes
        }
        row_values = [row_data[col] for col in columns_order]
        test_data.append(row_values)

    data = {
        "index": None,  # None appends the row at the end
        "values": test_data
    }

    response = graph_instance.add_row_to_table_in_excel_file(site_id, drive_id, file_id, table_name, data)


__all__ = ["MsGraph"]