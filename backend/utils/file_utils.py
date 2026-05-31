"""File utility functions for managing upload and output directories."""

from pathlib import Path

from config import get_settings


def ensure_directories() -> None:
    """Create required data directories if they don't exist."""
    settings = get_settings()
    directories = [
        settings.UPLOAD_DIR,
        settings.OUTPUT_DIR,
        settings.FAISS_DIR,
    ]
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)


def get_upload_path(filename: str) -> str:
    """Return the full path for an uploaded file."""
    settings = get_settings()
    return str(Path(settings.UPLOAD_DIR) / filename)


def get_workbook_path(filename: str) -> str:
    """Return the full path for a generated workbook file."""
    settings = get_settings()
    return str(Path(settings.OUTPUT_DIR) / filename)
