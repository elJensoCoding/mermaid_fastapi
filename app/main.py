from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .storage import DiagramRecord, create_or_update_diagram, get_diagram, init_db


BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

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


@app.get("/", response_class=HTMLResponse)
async def root(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "editor.html",
        {
            "request": request,
            "diagram": None,
            "diagram_source": DEFAULT_DIAGRAM,
            "share_path": None,
        },
    )


@app.get("/edit/{identifier}", response_class=HTMLResponse)
async def edit_diagram(request: Request, identifier: str) -> HTMLResponse:
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
        },
    )


@app.post("/edit", response_class=HTMLResponse)
async def save_from_form(
    request: Request,
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
        },
    )


@app.post("/api/diagrams", response_class=JSONResponse)
async def save_diagram(request: Request) -> JSONResponse:
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

    return JSONResponse(
        {
            "key": record.key,
            "slug": record.slug,
            "title": record.title,
            "share_url": str(request.base_url).rstrip("/") + _build_share_path(record),
            "edit_url": str(request.base_url).rstrip("/") + f"/edit/{record.key}",
        }
    )


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
