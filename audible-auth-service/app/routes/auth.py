import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import TokenStatusResponse
from app.amazon import create_auth_session
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])

templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=templates_dir)


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    marketplace: str = Query("br", description="Audible marketplace (e.g. br, us, uk)"),
    format: str = Query("html", description="Return format: html or json")
):
    """Generates official Amazon/Audible BR authorization URL and presents login interface."""
    session_id, auth_url, session_info = create_auth_session(marketplace=marketplace)

    if format == "json":
        return JSONResponse(content={
            "session_id": session_id,
            "auth_url": auth_url,
            "marketplace": marketplace,
            "callback_url": f"{request.base_url}auth/callback",
            "instructions": "Open auth_url in your browser, complete Amazon login. Copy the ENTIRE redirected URL bar containing openid.oa2.authorization_code and paste it to /auth/callback-manual."
        })

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "marketplace": marketplace,
            "auth_url": auth_url,
            "session_id": session_id,
            "base_url": str(request.base_url)
        }
    )


@router.post("/callback-manual", response_class=HTMLResponse)
def handle_manual_callback(
    request: Request,
    response_url: str = Form(..., description="Full redirected response URL from Amazon browser tab"),
    session_id: Optional[str] = Form(None),
    email: Optional[str] = Form("user@audible.com.br"),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Processes redirected URL from Amazon browser tab and registers device tokens."""
    try:
        res = auth_service.process_manual_callback(
            response_url=response_url,
            session_id=session_id,
            email_fallback=email
        )
        return templates.TemplateResponse(
            request=request,
            name="auth_success.html",
            context={
                "user_name": res["user_name"],
                "user_email": res["user_email"]
            }
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro ao registrar dispositivo Audible: {str(e)}"
        )


@router.get("/status", response_model=TokenStatusResponse)
def get_auth_status(auth_service: AuthService = Depends(get_auth_service)):
    """Returns status of stored tokens for the active user."""
    return auth_service.get_auth_status()


@router.post("/logout")
@router.get("/logout")
def logout(auth_service: AuthService = Depends(get_auth_service)):
    """Deletes stored authentication tokens and redirects to login."""
    auth_service.logout_user()
    return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

