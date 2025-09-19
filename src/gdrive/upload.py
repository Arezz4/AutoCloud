"""
Google Drive upload utility for Telegram backup bot.
Requires: google-api-python-client, google-auth-httplib2, google-auth-oauthlib

Setup:
1. Go to https://console.developers.google.com/apis/credentials and create OAuth client ID credentials for Desktop app.
2. Download credentials.json and place it in the same directory as this script.
3. The first run will prompt for Google account authorization and save token.json for future use.
"""
import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

SCOPES = ['https://www.googleapis.com/auth/drive.file']
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.abspath(os.path.join(BASE_DIR, '..', '..', 'config', 'credentials.json'))
TOKEN_FILE = os.path.abspath(os.path.join(os.getcwd(), 'gdrive_token.pickle'))

def get_drive_service():
	creds = None
	if os.path.exists(TOKEN_FILE):
		with open(TOKEN_FILE, 'rb') as token:
			creds = pickle.load(token)
	if not creds or not creds.valid:
		if creds and creds.expired and creds.refresh_token:
			creds.refresh(Request())
		else:
			flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
			creds = flow.run_local_server(port=0)
		with open(TOKEN_FILE, 'wb') as token:
			pickle.dump(creds, token)
	return build('drive', 'v3', credentials=creds)

def upload_file_to_gdrive(filepath, folder_id=None):
	"""Upload a file to Google Drive. Optionally specify a folder_id."""
	service = get_drive_service()
	file_metadata = {'name': os.path.basename(filepath)}
	if folder_id:
		file_metadata['parents'] = [folder_id]
	media = MediaFileUpload(filepath, resumable=True)
	file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
	return file.get('id')
