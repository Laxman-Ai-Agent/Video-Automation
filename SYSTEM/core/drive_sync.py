"""Google Drive Synchronization Utility for Audio-to-Video Pipeline.

Enables seamless offloading of GPU workloads (Whisper, Stable Diffusion, 3D)
to Google Colab by syncing audio files and transcripts via Google Drive API.
"""
from __future__ import annotations

import io
import json
import logging
from pathlib import Path
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

logger = logging.getLogger("drive_sync")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
CREDENTIALS_FILE = CONFIG_DIR / "google_drive_credentials.json"
SCOPES = ["https://www.googleapis.com/auth/drive"]

MAIN_FOLDER_NAME = "AI_Video_Project"


def get_drive_service() -> Any | None:
    """Authenticates and returns the Google Drive API service resource."""
    if not CREDENTIALS_FILE.exists():
        logger.warning("Google Drive credentials not found at %s", CREDENTIALS_FILE)
        return None
    try:
        creds = service_account.Credentials.from_service_account_file(
            str(CREDENTIALS_FILE), scopes=SCOPES
        )
        return build("drive", "v3", credentials=creds)
    except Exception as e:
        logger.error("Failed to authenticate with Google Drive API: %s", e)
        return None


def is_drive_connected() -> bool:
    """Returns True if Google Drive API is reachable and credentials are valid."""
    service = get_drive_service()
    if not service:
        return False
    try:
        res = service.files().list(
            q=f"name = '{MAIN_FOLDER_NAME}' and trashed = false",
            fields="files(id, name)",
            pageSize=1,
        ).execute()
        return len(res.get("files", [])) > 0
    except Exception:
        return False


def get_subfolder_id(service: Any, parent_id: str, subfolder_name: str) -> str | None:
    """Finds the ID of a subfolder within a parent folder."""
    q = f"'{parent_id}' in parents and name = '{subfolder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    res = service.files().list(q=q, fields="files(id, name)").execute()
    files = res.get("files", [])
    if files:
        return files[0]["id"]
    return None


def get_main_folder_id(service: Any) -> str | None:
    """Finds the ID of the main AI_Video_Project folder."""
    q = f"name = '{MAIN_FOLDER_NAME}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    res = service.files().list(q=q, fields="files(id, name)").execute()
    files = res.get("files", [])
    if files:
        return files[0]["id"]
    return None


def sync_transcript_from_drive(target_dir: Path) -> Path | None:
    """Downloads the latest transcript.json from Google Drive into target_dir.

    Returns the Path to target_dir / "transcript.json" if successful, None otherwise.
    """
    service = get_drive_service()
    if not service:
        return None

    main_id = get_main_folder_id(service)
    if not main_id:
        logger.warning("Main folder '%s' not found on Google Drive.", MAIN_FOLDER_NAME)
        return None

    transcripts_id = get_subfolder_id(service, main_id, "transcripts")
    if not transcripts_id:
        logger.warning("'transcripts' folder not found inside %s.", MAIN_FOLDER_NAME)
        return None

    # Find transcript.json in transcripts folder
    q = f"'{transcripts_id}' in parents and name = 'transcript.json' and trashed = false"
    res = service.files().list(q=q, fields="files(id, name, modifiedTime)").execute()
    files = res.get("files", [])
    if not files:
        logger.info("No transcript.json found on Google Drive yet.")
        return None

    file_id = files[0]["id"]
    req = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, req)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    raw_bytes = fh.getvalue()
    target_path = target_dir / "transcript.json"
    target_path.write_bytes(raw_bytes)
    logger.info("Successfully synced transcript.json from Google Drive to %s", target_path)
    return target_path


def upload_audio_to_drive(local_audio_path: Path) -> str | None:
    """Uploads a local audio file to the audio_files folder on Google Drive.

    Returns the Google Drive file ID if successful.
    """
    service = get_drive_service()
    if not service or not local_audio_path.exists():
        return None

    main_id = get_main_folder_id(service)
    if not main_id:
        return None

    audio_folder_id = get_subfolder_id(service, main_id, "audio_files")
    if not audio_folder_id:
        return None

    # Check if a file with the same name already exists
    filename = local_audio_path.name
    q = f"'{audio_folder_id}' in parents and name = '{filename}' and trashed = false"
    res = service.files().list(q=q, fields="files(id, name)").execute()
    existing = res.get("files", [])
    if existing:
        # Update existing file
        media = MediaFileUpload(str(local_audio_path), resumable=True)
        file = service.files().update(fileId=existing[0]["id"], media_body=media).execute()
        return file.get("id")

    # Upload new file
    file_metadata = {"name": filename, "parents": [audio_folder_id]}
    media = MediaFileUpload(str(local_audio_path), resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    return file.get("id")


def sync_images_from_drive(target_dir: Path) -> list[Path]:
    """Downloads all generated scene images from Google Drive into target_dir/assets/raw
    and formats them into assets/work for Remotion video rendering.
    """
    service = get_drive_service()
    if not service:
        return []

    main_id = get_main_folder_id(service)
    if not main_id:
        return []

    images_id = get_subfolder_id(service, main_id, "images")
    if not images_id:
        return []

    raw_dir = target_dir / "assets" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    q = f"'{images_id}' in parents and trashed = false"
    res = service.files().list(q=q, fields="files(id, name, size)").execute()
    files = res.get("files", [])

    downloaded: list[Path] = []
    for f in files:
        file_name = f["name"]
        if not any(file_name.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"]):
            continue
        dest_file = raw_dir / file_name
        req = service.files().get_media(fileId=f["id"])
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, req)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        dest_file.write_bytes(fh.getvalue())
        downloaded.append(dest_file)

    if downloaded:
        try:
            from VIDEO_ENGINE.stages.assets import save_uploads
            save_uploads(target_dir, downloaded)
            logger.info("Synced %d images from Google Drive to %s", len(downloaded), target_dir)
        except Exception as e:
            logger.warning("save_uploads post-process warning: %s", e)

    return downloaded


def sync_videos_from_drive(target_dir: Path) -> list[Path]:
    """Downloads all generated scene video clips from Google Drive into target_dir/assets/raw."""
    service = get_drive_service()
    if not service:
        return []

    main_id = get_main_folder_id(service)
    if not main_id:
        return []

    videos_id = get_subfolder_id(service, main_id, "videos")
    if not videos_id:
        return []

    raw_dir = target_dir / "assets" / "raw"
    work_dir = target_dir / "assets" / "work"
    raw_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    q = f"'{videos_id}' in parents and trashed = false"
    res = service.files().list(q=q, fields="files(id, name, size)").execute()
    files = res.get("files", [])

    downloaded: list[Path] = []
    for f in files:
        file_name = f["name"]
        if not any(file_name.lower().endswith(ext) for ext in [".mp4", ".mov", ".webm", ".mkv"]):
            continue
        dest_file = raw_dir / file_name
        req = service.files().get_media(fileId=f["id"])
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, req)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        dest_file.write_bytes(fh.getvalue())
        # Also copy to work dir for Remotion asset pipeline
        work_file = work_dir / file_name
        work_file.write_bytes(dest_file.read_bytes())
        downloaded.append(dest_file)

    if downloaded:
        logger.info("Synced %d video clips from Google Drive to %s", len(downloaded), target_dir)

    return downloaded

