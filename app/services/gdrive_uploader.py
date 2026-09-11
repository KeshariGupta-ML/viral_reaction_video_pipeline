import os
import asyncio
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from config import settings
from app.core.logger import logger

SCOPES = ["https://www.googleapis.com/auth/drive"]


class GoogleDriveUploader:
    def __init__(self):
        self.folder_id = str(getattr(settings, "GOOGLE_DRIVE_FOLDER_ID", "")).strip()
        self.credentials_path = Path(settings.ASSETS_DIR) / getattr(settings, "GOOGLE_OAUTH_CREDENTIALS", "credentials.json")
        self.token_path = Path(settings.ASSETS_DIR) / "token.json"

    def _get_drive_service(self):
        creds = None
        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not self.credentials_path.exists():
                    raise FileNotFoundError(
                        f"OAuth credentials not found at {self.credentials_path}. "
                        f"Download Desktop OAuth Client JSON from GCP to assets/credentials.json"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_path), SCOPES)
                creds = flow.run_local_server(port=0)

            with open(self.token_path, "w") as token:
                token.write(creds.to_json())

        return build("drive", "v3", credentials=creds)

    def _upload_file_sync(self, file_path: str | Path, mime_type: str, custom_filename: str = None) -> dict:
        file_path_obj = Path(file_path).resolve()
        if not file_path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path_obj}")

        service = self._get_drive_service()
        file_name = custom_filename or file_path_obj.name

        file_metadata = {
            "name": file_name,
            "parents": [self.folder_id] if self.folder_id else []
        }

        media = MediaFileUpload(
            str(file_path_obj),
            mimetype=mime_type,
            resumable=True
        )

        logger.info(f"📤 Uploading '{file_name}' to Google Drive folder [{self.folder_id}]...")

        try:
            request = service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id, name, webViewLink",
                supportsAllDrives=True
            )

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    logger.info(f"Uploading {file_name}: {int(status.progress() * 100)}%")

            logger.info(f"✅ Successfully uploaded '{file_name}'! ID: {response.get('id')}")
            return response

        except HttpError as err:
            logger.error(f"❌ Google Drive API HttpError: {err.content.decode('utf-8') if hasattr(err, 'content') else err}")
            raise RuntimeError(f"Drive API Error: {err}")
        except Exception as err:
            logger.error(f"❌ Unexpected upload error: {str(err)}")
            raise err

    async def upload_file(
        self,
        file_path: str | Path,
        mime_type: str = "application/octet-stream",
        custom_filename: str = None
    ) -> dict:
        return await asyncio.to_thread(self._upload_file_sync, file_path, mime_type, custom_filename)

    def _search_files_in_folder_sync(self, folder_id: str) -> list:
        """Searches and returns non-trashed files in a specific Google Drive folder."""
        service = self._get_drive_service()
        query = f"'{folder_id}' in parents and trashed = false"

        results = service.files().list(
            q=query,
            fields="files(id, name, mimeType)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()

        return results.get("files", [])

    async def list_temp_files(self, folder_id: str = None) -> list:
        target_folder = folder_id or self.folder_id
        return await asyncio.to_thread(self._search_files_in_folder_sync, target_folder)

gdrive_service = GoogleDriveUploader()