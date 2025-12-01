"""
Version: 1.001.000"""

import requests
from time import sleep

clickup_api_url = "https://api.clickup.com/api/v2/"


def get_tasks(vault_values, list_id, include_closed=True, query_parameters=None):
    """
    # Function: get_tasks

    ## Description
    This function is used to get tasks from a specific list in ClickUp.

    ## Parameters
    - `vault_values` (dict): The dictionary containing the authorization token.
    - `list_id` (str): The ID of the list from which tasks will be fetched.
    - `query_parameters` (dict, optional): Additional parameters to filter the tasks. Defaults to None.

    ## Returns
    - `tasks` (list): The list of tasks fetched from the ClickUp API.

    ## Example
    ```python
    tasks = get_tasks(vault_values={"token": "your_token"}, list_id="list123", query_parameters={"include_closed": "true"})
    ```

    ## Output
    This function returns a list of tasks. Each task is a dictionary containing information about the task.
    """
    tasks = []
    page = 0
    max_attempts = 3
    while True:
        url = f"{clickup_api_url}list/{list_id}/task"
        headers = {"Authorization": vault_values["token"]}
        params = {}
        if include_closed:
            params = {"include_closed": "true"}
        if query_parameters:
            params.update(query_parameters)
        if page > 0:  # Add the page parameter starting from the second request
            params["page"] = page
        
        attempts = 0
        while attempts < max_attempts:
            try:
                response = requests.get(url=url, headers=headers, params=params)
                response.raise_for_status()  # Raise an exception for HTTP errors
                break
            except requests.exceptions.RequestException as e:
                attempts += 1
                if attempts == max_attempts:
                    raise e
                sleep(2 ** attempts)  # Exponential backoff
        
        data = response.json()
        if "tasks" in data:
            tasks.extend(data["tasks"])
            if data["last_page"]:
                break
        else:
            break
        page += 1  # Increment the page number after the first request
    return tasks


def get_task(vault_values, task_id):
    """
    # Function: get_task

    ## Description
    This function is used to get a specific task from ClickUp.

    ## Parameters
    - `vault_values` (dict): The dictionary containing the authorization token.
    - `task_id` (str): The ID of the task to be fetched.

    ## Returns
    - `response.json()` (dict): The response from the ClickUp API as a JSON object. This will contain information about the fetched task.

    ## Example
    ```python
    task = get_task(vault_values={"token": "your_token"}, task_id="task123")
    ```

    ## Output
    This function returns a dictionary containing information about the fetched task.
    """
    url = f"{clickup_api_url}task/{task_id}"
    headers = {"Authorization": vault_values["token"]}
    response = requests.get(url=url, headers=headers)
    return response.json()


def create_task(vault_values, list_id, task_name="", args=None):
    """
    # Function: create_task

    ## Description
    This function is used to create a new task in a specific list in ClickUp.

    ## Parameters
    - `vault_values` (dict): The dictionary containing the authorization token.
    - `list_id` (str): The ID of the list where the task will be created.
    - `task_name` (str, optional): The name of the task to be created. Defaults to an empty string.
    - `args` (dict, optional): Additional parameters for the task. This dictionary should match the API Documentation in Click Up. If a task name is provided in both `task_name` and `args`, the one in `args` will be used. Defaults to None.

    ## Returns
    - `response.json()` (dict): The response from the ClickUp API as a JSON object. This will contain information about the created task.

    ## Example
    ```python
    task = create_task(vault_values={"token": "your_token"}, list_id="list123", task_name="New Task", args={"description": "Task description"})
    ```

    ## Output
    This function returns a dictionary containing information about the created task.
    """
    url = f"{clickup_api_url}list/{list_id}/task"
    headers = {"Authorization": vault_values["token"]}
    if args is None:
        final_object = {"name": task_name}
    else:
        final_object = args
        if task_name != "":
            final_object["name"] = task_name

        if "name" not in final_object:
            raise ValueError(
                "DEV Error: Task name is required in arguments, or as pass-in value to create_task() function."
            )

    response = requests.post(url=url, headers=headers, json=final_object)
    if response.status_code != 200:
        print(response.json())
        raise ValueError("Error creating task")
    return response.json()


def update_task(vault_values, task_id, task_name, task_description):
    url = f"{clickup_api_url}task/{task_id}"
    headers = {"Authorization": vault_values["token"]}
    response = requests.put(
        url=url, headers=headers, json={"name": task_name, "content": task_description}
    )
    return response.json()


def delete_task(vault_values, task_id):
    url = f"{clickup_api_url}task/{task_id}"
    headers = {"Authorization": vault_values["token"]}
    response = requests.delete(url=url, headers=headers)
    return response


def get_lists(vault_values, space_id):
    url = f"{clickup_api_url}space/{space_id}/list"
    headers = {"Authorization": vault_values["token"]}
    response = requests.get(url=url, headers=headers)
    return response.json()

def get_folder(vault_values, folder_id):
    url = f"{clickup_api_url}folder/{folder_id}"
    headers = {"Authorization": vault_values["token"]}
    response = requests.get(url=url, headers=headers)
    return response.json()

def get_lists_in_folder(vault_values, folder_id):
    folder = get_folder(vault_values, folder_id)
    return folder["lists"]

def create_folderless_list(vault_values, space_id, list_name):
    url = f"{clickup_api_url}space/{space_id}/list"
    headers = {"Authorization": vault_values["token"]}
    response = requests.post(url=url, headers=headers, json={"name": list_name})
    return response.json()


def create_list_in_folder(vault_values, folder_id, list_name):
    url = f"{clickup_api_url}/folder/{folder_id}/list"
    headers = {"Authorization": vault_values["token"]}
    response = requests.post(url=url, headers=headers, json={"name": list_name})
    return response.json()


def update_list(vault_values, list_id, list_name):
    url = f"{clickup_api_url}list/{list_id}"
    headers = {"Authorization": vault_values["token"]}
    response = requests.put(url=url, headers=headers, json={"name": list_name})
    return response.json()


def delete_list(vault_values, list_id):
    url = f"{clickup_api_url}list/{list_id}"
    headers = {"Authorization": vault_values["token"]}
    response = requests.delete(url=url, headers=headers)
    return response.json()


def get_accessible_custom_fields(vault_values, list_id):
    url = f"{clickup_api_url}list/{list_id}/field"
    headers = {"Authorization": vault_values["token"]}
    response = requests.get(url=url, headers=headers)
    return response.json()


def set_custom_field_value(vault_values, task_id, custom_field_id, value):
    url = f"{clickup_api_url}task/{task_id}/field/{custom_field_id}"
    headers = {"Authorization": vault_values["token"]}
    response = requests.post(url=url, headers=headers, json={"value": value})
    return response.json()


def create_task_comment(
    vault_values, task_id, comment_text, assignee_id, notify_all=False
):
    """
    # Function: create_task_comment

    ## Description
    This function is used to create a comment on a specific task in ClickUp.


    ## Parameters
    - `task_id` (str): The ID of the task where the comment will be added.
    - `comment_text` (str): The text of the comment to be added.
    - `assignee_id` (int): The ID of the user who will be assigned to the comment.
    - `notify_all` (bool, optional): If set to True, all members of the task will be notified about the comment. Defaults to False.

    ## Returns
    - `response.json()` (dict): The response from the ClickUp API as a JSON object. This will contain information about the created comment.

    ## Example
    ```python
    response = create_task_comment(task_id="task123", comment_text="This is a comment", assignee_id=123456, notify_all=True)
    ```

    ## Output

    This function doesn't return any value. It stores the vault values in the global variable `vault_values`.
    """

    url = f"{clickup_api_url}task/{task_id}/comment"
    headers = {"Authorization": vault_values["token"]}
    json = {
        "comment_text": comment_text,
        "assignee": assignee_id,
        "notify_all": notify_all,
    }
    response = requests.post(url=url, headers=headers, json=json)
    return response.json()

def get_custom_label_field_by_name(vault_values, list_id, custom_field_name):
    print("Getting custom field by name.")
    response = get_accessible_custom_fields(vault_values, list_id)
    for field in response["fields"]:
        if field["name"] == custom_field_name:
            print(f"Found custom field by name: {custom_field_name}")
            options = [
                {"name": option["label"], "id": option["id"]}
                for option in field["type_config"]["options"]
            ]
            field_id = field["id"]
            return field_id, options
    print(f"Custom field not found by name: {custom_field_name}")
    return {}

def get_custom_dropdown_field_by_name(vault_values, list_id, custom_field_name):
    print("Getting custom field by name.")
    response = get_accessible_custom_fields(vault_values, list_id)
    for field in response["fields"]:
        if field["name"] == custom_field_name:
            print(f"Found custom field by name: {custom_field_name}")
            options = [
                {"name": option["name"], "id": option["id"]}
                for option in field["type_config"]["options"]
            ]
            field_id = field["id"]
            return field_id, options
    print(f"Custom field not found by name: {custom_field_name}")
    return None
