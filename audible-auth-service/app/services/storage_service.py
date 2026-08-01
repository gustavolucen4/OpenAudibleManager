import os
import re
import shutil
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models import Setting


class StorageService:
    """Service responsible for file storage, directory operations, settings, and FFmpeg discovery."""

    @staticmethod
    def find_ffmpeg() -> Optional[str]:
        """Finds ffmpeg executable path on Windows system or standard PATH."""
        which_path = shutil.which("ffmpeg")
        if which_path:
            return which_path

        search_dirs = [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Packages"),
            r"C:\ProgramData\chocolatey\bin",
            r"C:\Users\Public\scoop\shims",
            os.path.join(os.environ.get("USERPROFILE", ""), "scoop", "shims"),
            r"C:\ffmpeg\bin",
        ]

        candidates = []
        for s_dir in search_dirs:
            if os.path.exists(s_dir):
                for root, _, files in os.walk(s_dir):
                    if "ffmpeg.exe" in files:
                        candidates.append(os.path.join(root, "ffmpeg.exe"))

        return candidates[0] if candidates else None

    @staticmethod
    def sanitize_folder_name(name: str) -> str:
        """Sanitizes string to be safe for directory and file names."""
        if not name:
            return "Unknown"
        cleaned = re.sub(r'[\\/*?:"<>|]', '', name).strip()
        return cleaned or "Audiobook"

    @staticmethod
    def get_configured_settings(db: Session) -> Dict[str, str]:
        """Fetch configured download directory and activation bytes from DB settings."""
        setting_dir = db.query(Setting).filter(Setting.key == "download_dir").first()
        setting_bytes = db.query(Setting).filter(Setting.key == "activation_bytes").first()

        download_dir = setting_dir.value if (setting_dir and setting_dir.value) else os.path.abspath(os.path.join(".", "data", "audiobooks"))
        activation_bytes = setting_bytes.value if (setting_bytes and setting_bytes.value) else ""

        return {
            "download_dir": download_dir,
            "activation_bytes": activation_bytes
        }

    @staticmethod
    def browse_directories(path: Optional[str] = None) -> Dict[str, Any]:
        """Lists accessible system drives or subdirectories for folder picker UI."""
        if not path or path.strip() in ("", "/", "\\"):
            drives = []
            if os.name == 'nt':
                import string
                for letter in string.ascii_uppercase:
                    d_path = f"{letter}:\\"
                    if os.path.exists(d_path):
                        drives.append(d_path)
            else:
                drives = ["/"]

            return {
                "current_path": "",
                "parent_path": "",
                "is_root": True,
                "drives": drives,
                "directories": []
            }

        target_path = os.path.abspath(path.strip())

        if not os.path.exists(target_path) or not os.path.isdir(target_path):
            return {
                "error": f"Caminho não encontrado ou não é um diretório: {path}",
                "current_path": path,
                "directories": []
            }

        parent_path = os.path.dirname(target_path)
        if parent_path == target_path:
            parent_path = ""

        directories = []
        try:
            with os.scandir(target_path) as entries:
                for entry in entries:
                    if entry.is_dir(follow_symlinks=False) and not entry.name.startswith('.'):
                        directories.append({
                            "name": entry.name,
                            "path": entry.path
                        })

            directories.sort(key=lambda x: x["name"].lower())
        except PermissionError:
            return {
                "error": "Acesso negado a este diretório.",
                "current_path": target_path,
                "parent_path": parent_path,
                "directories": []
            }
        except Exception as e:
            return {
                "error": str(e),
                "current_path": target_path,
                "parent_path": parent_path,
                "directories": []
            }

        drives = []
        if os.name == 'nt':
            import string
            for letter in string.ascii_uppercase:
                d_path = f"{letter}:\\"
                if os.path.exists(d_path):
                    drives.append(d_path)
        else:
            drives = ["/"]

        return {
            "current_path": target_path,
            "parent_path": parent_path,
            "is_root": False,
            "drives": drives,
            "directories": directories
        }

    @staticmethod
    def remove_file_and_empty_parents(file_path: str) -> bool:
        """Safely removes a file and its parent directories if they become empty."""
        if not file_path or not os.path.exists(file_path):
            return False

        try:
            os.remove(file_path)
            parent_dir = os.path.dirname(file_path)
            if os.path.exists(parent_dir) and not os.listdir(parent_dir):
                os.rmdir(parent_dir)
                grandparent_dir = os.path.dirname(parent_dir)
                if os.path.exists(grandparent_dir) and not os.listdir(grandparent_dir):
                    os.rmdir(grandparent_dir)
            return True
        except Exception as e:
            print(f"Error removing file {file_path}: {e}")
            return False
