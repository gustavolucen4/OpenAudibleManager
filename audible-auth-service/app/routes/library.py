import os
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models import Book, Setting
from app.schemas import BookResponse, BookSyncStats
from app.services.auth_service import AuthService
from app.services.library_service import LibraryService
from app.services.download_service import DownloadService
from app.services.storage_service import StorageService

router = APIRouter(prefix="/audible", tags=["Audible Library & Downloads"])


class SettingsSchema(BaseModel):
    download_dir: str
    activation_bytes: Optional[str] = ""


def get_library_service(db: Session = Depends(get_db)) -> LibraryService:
    return LibraryService(db)


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


@router.get("/library-ui", response_class=HTMLResponse)
def get_library_ui(auth_service: AuthService = Depends(get_auth_service)):
    """Serves the interactive Dark Mode Web UI Dashboard for library management if authenticated."""
    if not auth_service.is_authenticated():
        return RedirectResponse(url="/auth/login", status_code=302)

    template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "library.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    return HTMLResponse(content="<h1>Template library.html não encontrado</h1>", status_code=404)


@router.get("/browse-dirs")
def browse_directories(path: Optional[str] = Query(None, description="Path to browse")):
    """Interactively lists accessible system drives or subdirectories for folder picker UI."""
    return StorageService.browse_directories(path)


@router.get("/settings", response_model=SettingsSchema)
def get_settings(db: Session = Depends(get_db)):
    """Returns current system settings including download directory and activation bytes."""
    conf = StorageService.get_configured_settings(db)
    return SettingsSchema(
        download_dir=conf["download_dir"],
        activation_bytes=conf["activation_bytes"]
    )


@router.post("/settings", response_model=SettingsSchema)
def update_settings(payload: SettingsSchema, db: Session = Depends(get_db)):
    """Updates system settings like download directory and activation bytes."""
    raw_dir = payload.download_dir.strip().strip('"').strip("'")
    if not raw_dir:
        raise HTTPException(status_code=400, detail="Caminho da pasta de download inválido.")

    raw_bytes = (payload.activation_bytes or "").strip()

    try:
        norm_dir = os.path.abspath(raw_dir)
    except Exception:
        norm_dir = raw_dir

    if not os.path.exists(norm_dir):
        try:
            os.makedirs(norm_dir, exist_ok=True)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Não foi possível criar/acessar a pasta '{norm_dir}': {str(e)}"
            )

    setting_dir = db.query(Setting).filter(Setting.key == "download_dir").first()
    if not setting_dir:
        setting_dir = Setting(key="download_dir", value=norm_dir)
        db.add(setting_dir)
    else:
        setting_dir.value = norm_dir

    setting_bytes = db.query(Setting).filter(Setting.key == "activation_bytes").first()
    if not setting_bytes:
        setting_bytes = Setting(key="activation_bytes", value=raw_bytes)
        db.add(setting_bytes)
    else:
        setting_bytes.value = raw_bytes

    db.commit()

    # Automatically scan newly selected directory for already downloaded audiobooks
    try:
        LibraryService(db).sync_local_disk_status()
    except Exception:
        pass

    return SettingsSchema(
        download_dir=norm_dir,
        activation_bytes=raw_bytes
    )


@router.get("/books", response_model=List[BookResponse])
def get_stored_books(library_service: LibraryService = Depends(get_library_service)):
    """Returns list of all synced books stored in local database with active disk verification."""
    return library_service.get_stored_books()


@router.post("/sync", response_model=BookSyncStats)
def sync_library_with_audible(library_service: LibraryService = Depends(get_library_service)):
    """Fetches user audiobooks from Audible Brasil API and synchronizes SQLite database."""
    try:
        res = library_service.sync_user_library()
        return BookSyncStats(**res)
    except ValueError as ve:
        err_msg = str(ve)
        if "Token" in err_msg or "login" in err_msg:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
    except Exception as e:
        err_msg = str(e)
        if "Invalid token" in err_msg or "401" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sessão expirada. Acesse http://localhost:8085/auth/login e faça login novamente."
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao sincronizar com a API da Audible Brasil: {err_msg}"
        )


@router.post("/download/{asin}")
def download_audiobook(
    asin: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Triggers background real download for a specific audiobook by ASIN."""
    book = db.query(Book).filter(Book.asin == asin).first()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audiolivro não encontrado.")

    if book.download_status == "downloading" and book.local_path and os.path.exists(book.local_path):
        return {"status": "already_downloading", "asin": asin}

    book.download_status = "downloading"
    book.download_progress = 1
    db.commit()

    background_tasks.add_task(DownloadService.execute_audiobook_download, asin, SessionLocal)
    return {"status": "download_started", "asin": asin, "title": book.title}


@router.post("/convert/{asin}")
def convert_aax_to_m4b(
    asin: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Converts an already-downloaded .aax to .m4b using the configured activation_bytes."""
    book = db.query(Book).filter(Book.asin == asin).first()
    if not book:
        raise HTTPException(status_code=404, detail="Audiolivro não encontrado.")

    if not book.local_path or not book.local_path.lower().endswith(".aax"):
        raise HTTPException(status_code=400, detail="O arquivo não está no formato .aax ou não foi baixado.")

    conf = StorageService.get_configured_settings(db)
    if not conf["activation_bytes"]:
        raise HTTPException(
            status_code=400,
            detail="Bytes de Ativação não configurados. Preencha o campo nas configurações e tente novamente."
        )

    background_tasks.add_task(DownloadService.execute_aax_conversion, asin, SessionLocal)
    return {"status": "converting", "asin": asin}


@router.post("/download/{asin}/cancel")
def cancel_audiobook_download(asin: str, db: Session = Depends(get_db)):
    """Cancels an in-progress download and cleans up temporary partial files."""
    try:
        return DownloadService.cancel_download(asin, db)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))


@router.post("/download/{asin}/delete")
@router.delete("/download/{asin}")
def delete_audiobook_file(asin: str, db: Session = Depends(get_db)):
    """Deletes the downloaded audiobook file (.m4b/.aax) from disk and resets book download status."""
    try:
        return DownloadService.delete_download_file(asin, db)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
