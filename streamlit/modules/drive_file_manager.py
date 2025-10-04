import streamlit as st
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

from datetime import datetime
import io
import json

# Define the Google Drive API scope
SCOPES = ['https://www.googleapis.com/auth/drive']

def get_parent_folder_id():
    try:
        return st.secrets["folder_id"]
    except (KeyError, AttributeError):
        return None

def get_drive_info():
    try:
        return dict(st.secrets["drive"])
    except (KeyError, AttributeError):
        return None

# Authenticates using service account credentials
def authenticate():
    info = get_drive_info()
    if not info:
        raise RuntimeError("Google Drive credentials not found in secrets.")
    creds = service_account.Credentials.from_service_account_info(info)
    return creds

# Uploads a string as a txt file to Google Drive
def upload_text_as_file(text_content, filename):
    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)
    parent_folder_id = get_parent_folder_id()
    # Encode text content as UTF-8
    file_stream = io.BytesIO(text_content.encode('utf-8'))  # Encode to UTF-8 to handle special characters
    media = MediaIoBaseUpload(file_stream, mimetype='text/plain')

    file_metadata = {
        'name': f"{filename}.txt",
        'parents': [parent_folder_id] if parent_folder_id else []
    }

    service.files().create(body=file_metadata, media_body=media, fields='id').execute()

# Returns the id of a file in Google Drive (if it exists), using its name 
def find_file_by_name(filename):
    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)
    parent_folder_id = get_parent_folder_id()
    q = f"name='{filename}' and trashed=false"
    if parent_folder_id:
        q += f" and '{parent_folder_id}' in parents"
    results = service.files().list(
        q=q,
        spaces='drive',
        fields='files(id, name)',
        pageSize=10
    ).execute()
    items = results.get('files', [])
    if not items:
        print(f'No files found with the name: {filename}')
        return None
    for item in items:
        if item['name'] == filename:
            return item['id']
    return None

# Reads the content of a file in Google Drive, using its id
def read_file_content(file_id):
    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)
    request = service.files().get_media(fileId=file_id)
    file_stream = io.BytesIO()
    downloader = MediaIoBaseDownload(file_stream, request)
    done = False
    while done is False:
        _,done = downloader.next_chunk()
    file_stream.seek(0)
    content = file_stream.read().decode('utf-8')
    return content

# Combines find_file_by_name and read_file_content in a single function
def get_text_from_file(filename_to_read):
    file_id_to_read = find_file_by_name(filename_to_read)
    if file_id_to_read:
        file_content = read_file_content(file_id_to_read)
        return file_content
    return None

# Finds a file in Google Drive by matching the user_id_game_id pattern, ignoring the timestamp.
def find_file_by_name_without_timestamp(base_filename):
    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)
    parent_folder_id = get_parent_folder_id()
    # Search for files in the parent folder with a name that starts with the base filename
    query = (
        f"name contains '{base_filename}' and trashed=false"
    )
    if parent_folder_id:
        query += f" and '{parent_folder_id}' in parents"
    results = service.files().list(
        q=query,
        spaces='drive',
        fields='files(id, name)',
        pageSize=50 # TODO: This is not scalable to large folders. We must do something about it.
    ).execute()
    items = results.get('files', [])
    if not items:
        print(f"No files found with the pattern: {base_filename}")
        return None
    # Return all matching file IDs
    matching_ids = []
    for item in items:
        if base_filename in item['name']:
            matching_ids.append(item['id'])
    return matching_ids if matching_ids else None

# Combines find_file_by_name (without timestamp) and read_file_content in a single function
def get_text_from_file_without_timestamp(filename_to_read):
    file_ids = find_file_by_name_without_timestamp(filename_to_read)
    if not file_ids:
        return None
    # Combine contents of all matching files
    all_contents = []
    for file_id in file_ids:
        content = read_file_content(file_id)
        if content:
            all_contents.append(content)
    return "\n\n---\n\n".join(all_contents) if all_contents else None

# Deletes a file in Google Drive using its ID
def delete_file_by_id(file_id):
    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)
    service.files().delete(fileId=file_id).execute()
    print(f"File with ID '{file_id}' deleted successfully.")

# Function to overwrite a file (check if exists, delete, then upload)
def overwrite_text_file(text_content, filename, remove_timestamp=True):
    if remove_timestamp == True:
        # Extract base_filename (user_id_game_id) by removing the timestamp
        base_filename = "_".join(filename.split("_")[:-1]) + "_" # keep the last underscore
        # Check if a file with the same name exists
        file_id_to_delete = find_file_by_name_without_timestamp(base_filename)
    elif remove_timestamp == False:
        file_id_to_delete = find_file_by_name(filename)
        filename = filename.split('.txt')[0]
    if file_id_to_delete:
        # Delete the existing file
        delete_file_by_id(file_id_to_delete)
    # Upload the new file
    upload_text_as_file(text_content, filename)
    print(f"New file '{filename}.txt' uploaded successfully.")

# Function to find and delete a file
def find_and_delete(filename):
    file_id_to_delete = find_file_by_name(filename)
    if file_id_to_delete:
        delete_file_by_id(file_id_to_delete)
