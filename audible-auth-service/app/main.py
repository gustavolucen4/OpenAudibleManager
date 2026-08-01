import sys
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

# Add root directory to sys.path to guarantee robust module resolution across all environments
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.database import init_db, SessionLocal, get_db
from app.models import Book
from app.routes import auth, library
from app.services.auth_service import AuthService


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    # Automatically clean up any orphaned stuck downloads on startup
    try:
        db = SessionLocal()
        stuck_books = db.query(Book).filter(Book.download_status == "downloading").all()
        for b in stuck_books:
            b.download_status = "error"
            b.download_progress = 0
        if stuck_books:
            db.commit()
        db.close()
    except Exception:
        pass

    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="OpenAudible Manager - Serviço de Gerenciamento e Download de Biblioteca Audible Brasil",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    favicon_path = os.path.join(static_dir, "favicon.png")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path, media_type="image/png")
    return HTMLResponse(content="", status_code=404)


# Include Routers
app.include_router(auth.router)
app.include_router(library.router)


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


@app.get("/", response_class=HTMLResponse)
def root(auth_service: AuthService = Depends(get_auth_service)):
    """Serves the main Library Dashboard UI directly at the root URL if authenticated, else redirects to /auth/login."""
    if not auth_service.is_authenticated():
        return RedirectResponse(url="/auth/login", status_code=302)

    template_path = os.path.join(os.path.dirname(__file__), "templates", "library.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    return RedirectResponse(url="/audible/library-ui", status_code=302)


@app.get("/health")
def health_check():
    return {"status": "healthy"}
