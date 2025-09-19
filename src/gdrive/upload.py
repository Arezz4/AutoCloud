"""
Google Drive upload utility for Telegram backup bot.
Requires: google-api-python-client, google-auth-httplib2, google-auth-oauthlib

Setup:
1. Go to https://console.developers.google.com/apis/credentials and create OAuth client ID credentials for Desktop app.
2. Download credentials.json and place it in the same directory as this script.
3. The first run will prompt for Google account authorization and save token.json for future use.
"""
import os
import socket
import pickle
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

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

	def progress_bar(current, total):
		bar_len = 30
		if total == 0:
			percent = 0
		else:
			percent = current / total
		filled_len = int(bar_len * percent)
		bar = '=' * filled_len + '-' * (bar_len - filled_len)
		mb_current = current / (1024 * 1024)
		mb_total = total / (1024 * 1024) if total else 0
		print(f'\r[Google Drive Upload] |{bar}| {mb_current:.2f}/{mb_total:.2f} MB', end='', flush=True)
		if current == total:
			print()  # Newline after complete

	# Set chunk size to 5MB
	chunk_size = 5 * 1024 * 1024
	media = MediaFileUpload(filepath, resumable=True, chunksize=chunk_size)
	# Set unlimited timeout for upload
	orig_socket_timeout = socket.getdefaulttimeout()
	socket.setdefaulttimeout(None)
	try:
		request = service.files().create(body=file_metadata, media_body=media, fields='id')
		response = None
		while response is None:
			status, response = request.next_chunk()
			if status:
				progress_bar(status.resumable_progress, media.size())
		progress_bar(media.size(), media.size())
	finally:
		socket.setdefaulttimeout(orig_socket_timeout)
	return response.get('id')
