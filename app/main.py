from __future__ import annotations

import os
import secrets
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .storage import (
    DiagramRecord,
    create_or_update_diagram,
    delete_diagram,
    duplicate_diagram,
    get_diagram,
    init_db,
    list_diagrams,
    update_diagram,
)


BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
security = HTTPBasic(auto_error=False)
EDITOR_USERNAME = os.getenv("MERMAID_EDITOR_USERNAME")
EDITOR_PASSWORD = os.getenv("MERMAID_EDITOR_PASSWORD")

DEFAULT_DIAGRAM = """flowchart TD
    A[Intranet App] --> B[Mermaid Service]
    B --> C[Editor mit Preview]
    B --> D[Sharebare SVG URL]
"""


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Mermaid Host Service", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def _build_share_path(record: DiagramRecord) -> str:
    return f"/d/{record.slug or record.key}"


def _auth_enabled() -> bool:
    return bool(EDITOR_USERNAME and EDITOR_PASSWORD)


def _require_editor_auth(
    credentials: Optional[HTTPBasicCredentials] = Depends(security),
) -> None:
    if not _auth_enabled():
        return

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentifizierung erforderlich.",
            headers={"WWW-Authenticate": "Basic"},
        )

    username_ok = secrets.compare_digest(credentials.username, EDITOR_USERNAME or "")
    password_ok = secrets.compare_digest(credentials.password, EDITOR_PASSWORD or "")

    if username_ok and password_ok:
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentifizierung fehlgeschlagen.",
        headers={"WWW-Authenticate": "Basic"},
    )


def _diagram_payload(request: Request, record: DiagramRecord) -> dict[str, Optional[str]]:
    base_url = str(request.base_url).rstrip("/")
    return {
        "key": record.key,
        "slug": record.slug,
        "title": record.title,
        "source": record.source,
        "rendered_svg": record.rendered_svg,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "share_url": base_url + _build_share_path(record),
        "edit_url": base_url + f"/edit/{record.key}",
    }


@app.get("/", response_class=HTMLResponse)
async def root(request: Request, _: None = Depends(_require_editor_auth)) -> HTMLResponse:
    return templates.TemplateResponse(
        "editor.html",
        {
            "request": request,
            "diagram": None,
            "diagram_source": DEFAULT_DIAGRAM,
            "share_path": None,
            "list_path": "/diagrams",
            "auth_enabled": _auth_enabled(),
        },
    )


@app.get("/edit/{identifier}", response_class=HTMLResponse)
async def edit_diagram(
    request: Request,
    identifier: str,
    _: None = Depends(_require_editor_auth),
) -> HTMLResponse:
    diagram = get_diagram(identifier)
    if not diagram:
        raise HTTPException(status_code=404, detail="Diagramm nicht gefunden.")

    return templates.TemplateResponse(
        "editor.html",
        {
            "request": request,
            "diagram": diagram,
            "diagram_source": diagram.source,
            "share_path": _build_share_path(diagram),
            "list_path": "/diagrams",
            "auth_enabled": _auth_enabled(),
        },
    )


@app.post("/edit", response_class=HTMLResponse)
async def save_from_form(
    request: Request,
    _: None = Depends(_require_editor_auth),
    source: str = Form(...),
    rendered_svg: str = Form(...),
    title: Optional[str] = Form(default=None),
    slug: Optional[str] = Form(default=None),
    key: Optional[str] = Form(default=None),
) -> HTMLResponse:
    try:
        record = create_or_update_diagram(
            source,
            rendered_svg=rendered_svg,
            title=title,
            slug=slug,
            key=key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Slug ist bereits vergeben.") from exc

    return templates.TemplateResponse(
        "editor.html",
        {
            "request": request,
            "diagram": record,
            "diagram_source": record.source,
            "share_path": _build_share_path(record),
            "saved": True,
            "list_path": "/diagrams",
            "auth_enabled": _auth_enabled(),
        },
    )


@app.post("/edit/{identifier}/delete", response_class=HTMLResponse)
async def delete_from_form(
    request: Request,
    identifier: str,
    _: None = Depends(_require_editor_auth),
) -> HTMLResponse:
    deleted = delete_diagram(identifier)
    if not deleted:
        raise HTTPException(status_code=404, detail="Diagramm nicht gefunden.")

    diagrams = list_diagrams()
    return templates.TemplateResponse(
        "list.html",
        {
            "request": request,
            "diagrams": diagrams,
            "query": "",
            "deleted": True,
            "auth_enabled": _auth_enabled(),
        },
    )


@app.post("/edit/{identifier}/duplicate", response_class=HTMLResponse)
async def duplicate_from_form(
    request: Request,
    identifier: str,
    _: None = Depends(_require_editor_auth),
) -> HTMLResponse:
    record = duplicate_diagram(identifier)
    if not record:
        raise HTTPException(status_code=404, detail="Diagramm nicht gefunden.")

    return templates.TemplateResponse(
        "editor.html",
        {
            "request": request,
            "diagram": record,
            "diagram_source": record.source,
            "share_path": _build_share_path(record),
            "saved": True,
            "duplicated": True,
            "list_path": "/diagrams",
            "auth_enabled": _auth_enabled(),
        },
    )


@app.get("/diagrams", response_class=HTMLResponse)
async def diagrams_overview(
    request: Request,
    q: Optional[str] = None,
    _: None = Depends(_require_editor_auth),
) -> HTMLResponse:
    return templates.TemplateResponse(
        "list.html",
        {
            "request": request,
            "diagrams": list_diagrams(q),
            "query": q or "",
            "deleted": False,
            "auth_enabled": _auth_enabled(),
        },
    )


@app.post("/api/diagrams", response_class=JSONResponse)
async def save_diagram(request: Request, _: None = Depends(_require_editor_auth)) -> JSONResponse:
    payload = await request.json()
    try:
        record = create_or_update_diagram(
            payload.get("source", ""),
            rendered_svg=payload.get("rendered_svg"),
            title=payload.get("title"),
            slug=payload.get("slug"),
            key=payload.get("key"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Slug ist bereits vergeben.") from exc

    return JSONResponse(_diagram_payload(request, record), status_code=201)


@app.get("/api/diagrams/{identifier}", response_class=JSONResponse)
async def get_diagram_api(request: Request, identifier: str) -> JSONResponse:
    diagram = get_diagram(identifier)
    if not diagram:
        raise HTTPException(status_code=404, detail="Diagramm nicht gefunden.")

    return JSONResponse(_diagram_payload(request, diagram))


@app.put("/api/diagrams/{identifier}", response_class=JSONResponse)
async def update_diagram_api(
    request: Request,
    identifier: str,
    _: None = Depends(_require_editor_auth),
) -> JSONResponse:
    payload = await request.json()
    try:
        record = update_diagram(
            identifier,
            source=payload.get("source", ""),
            rendered_svg=payload.get("rendered_svg"),
            title=payload.get("title"),
            slug=payload.get("slug"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Slug ist bereits vergeben.") from exc

    if not record:
        raise HTTPException(status_code=404, detail="Diagramm nicht gefunden.")

    return JSONResponse(_diagram_payload(request, record))


@app.delete("/api/diagrams/{identifier}", response_class=JSONResponse)
async def delete_diagram_api(
    identifier: str,
    _: None = Depends(_require_editor_auth),
) -> JSONResponse:
    deleted = delete_diagram(identifier)
    if not deleted:
        raise HTTPException(status_code=404, detail="Diagramm nicht gefunden.")

    return JSONResponse({"deleted": True, "identifier": identifier})


@app.post("/api/diagrams/{identifier}/duplicate", response_class=JSONResponse)
async def duplicate_diagram_api(
    request: Request,
    identifier: str,
    _: None = Depends(_require_editor_auth),
) -> JSONResponse:
    record = duplicate_diagram(identifier)
    if not record:
        raise HTTPException(status_code=404, detail="Diagramm nicht gefunden.")

    return JSONResponse(_diagram_payload(request, record), status_code=201)


@app.get("/d/{identifier}")
async def get_svg(identifier: str) -> Response:
    diagram = get_diagram(identifier)
    if not diagram:
        raise HTTPException(status_code=404, detail="Diagramm nicht gefunden.")
    if not diagram.rendered_svg:
        raise HTTPException(
            status_code=409,
            detail="Fuer dieses Diagramm ist noch kein gespeichertes SVG vorhanden. Bitte im Editor erneut speichern.",
        )

    return Response(content=diagram.rendered_svg, media_type="image/svg+xml")
