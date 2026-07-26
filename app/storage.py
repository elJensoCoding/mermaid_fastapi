from __future__ import annotations

import re
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


DATABASE_PATH = Path(__file__).resolve().parent.parent / "data" / "diagrams.db"


@dataclass
class DiagramRecord:
    key: str
    slug: Optional[str]
    title: Optional[str]
    source: str
    rendered_svg: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


SLUG_PATTERN = re.compile(r"[^a-z0-9-]+")
MAX_SLUG_LENGTH = 80
MAX_TITLE_LENGTH = 120
MAX_SOURCE_LENGTH = 50_000
MAX_SVG_LENGTH = 500_000


def init_db() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS diagrams (
                key TEXT PRIMARY KEY,
                slug TEXT UNIQUE,
                title TEXT,
                source TEXT NOT NULL,
                rendered_svg TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(diagrams)").fetchall()
        }
        if "rendered_svg" not in columns:
            connection.execute("ALTER TABLE diagrams ADD COLUMN rendered_svg TEXT")


def slugify(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-").replace(" ", "-")
    normalized = SLUG_PATTERN.sub("-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    if not normalized:
        raise ValueError("Slug ist leer oder ungueltig.")
    if len(normalized) > MAX_SLUG_LENGTH:
        raise ValueError(f"Slug darf hoechstens {MAX_SLUG_LENGTH} Zeichen lang sein.")
    return normalized


def _truncate(value: str, max_length: int) -> str:
    return value[:max_length].rstrip("- ").strip()


def _slug_exists(connection: sqlite3.Connection, slug: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM diagrams WHERE slug = ?",
        (slug,),
    ).fetchone()
    return row is not None


def _next_copy_title(title: Optional[str]) -> str:
    base = (title or "Diagramm").strip() or "Diagramm"
    match = re.match(r"^(.*?)(?:\s+Kopie(?:\s+(\d+))?)?$", base)
    if match:
        root = match.group(1).strip() or "Diagramm"
        had_copy_suffix = bool(match.group(0) != root)
        number = int(match.group(2) or ("1" if had_copy_suffix else "0"))
    else:
        root = base
        number = 0

    next_number = number + 1
    if next_number == 1:
        return _truncate(f"{root} Kopie", MAX_TITLE_LENGTH)

    return _truncate(f"{root} Kopie {next_number}", MAX_TITLE_LENGTH)


def _next_copy_slug(connection: sqlite3.Connection, slug: Optional[str]) -> Optional[str]:
    if not slug:
        return None

    base_slug = slugify(slug)
    match = re.match(r"^(.*?)-copy(?:-(\d+))?$", base_slug)
    if match:
        root = match.group(1).strip("-") or base_slug
        number = int(match.group(2) or "1")
    else:
        root = base_slug
        number = 0

    next_number = number + 1
    suffix = "-copy" if next_number == 1 else f"-copy-{next_number}"
    truncated_root = _truncate(root[: MAX_SLUG_LENGTH - len(suffix)], MAX_SLUG_LENGTH)
    candidate = f"{truncated_root}{suffix}"

    while _slug_exists(connection, candidate):
        next_number += 1
        suffix = f"-copy-{next_number}"
        truncated_root = _truncate(root[: MAX_SLUG_LENGTH - len(suffix)], MAX_SLUG_LENGTH)
        candidate = f"{truncated_root}{suffix}"

    return candidate


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def create_or_update_diagram(
    source: str,
    *,
    key: Optional[str] = None,
    slug: Optional[str] = None,
    title: Optional[str] = None,
    rendered_svg: Optional[str] = None,
) -> DiagramRecord:
    if not source.strip():
        raise ValueError("Diagramm-Quelltext darf nicht leer sein.")
    if len(source) > MAX_SOURCE_LENGTH:
        raise ValueError(f"Diagramm-Quelltext ist zu gross. Maximal {MAX_SOURCE_LENGTH} Zeichen.")
    if not rendered_svg or not rendered_svg.strip():
        raise ValueError("Gerendertes SVG fehlt. Bitte Vorschau laden und erneut speichern.")
    if len(rendered_svg) > MAX_SVG_LENGTH:
        raise ValueError(f"Gerendertes SVG ist zu gross. Maximal {MAX_SVG_LENGTH} Zeichen.")
    if title and len(title) > MAX_TITLE_LENGTH:
        raise ValueError(f"Titel darf hoechstens {MAX_TITLE_LENGTH} Zeichen lang sein.")

    slug_value = slugify(slug) if slug else None
    key_value = key or str(uuid.uuid4())

    with _connect() as connection:
        existing = connection.execute(
            "SELECT key, slug, title, source, rendered_svg, created_at, updated_at FROM diagrams WHERE key = ?",
            (key_value,),
        ).fetchone()

        if existing:
            connection.execute(
                """
                UPDATE diagrams
                SET slug = ?, title = ?, source = ?, rendered_svg = ?, updated_at = CURRENT_TIMESTAMP
                WHERE key = ?
                """,
                (slug_value, title, source, rendered_svg, key_value),
            )
        else:
            connection.execute(
                """
                INSERT INTO diagrams (key, slug, title, source, rendered_svg)
                VALUES (?, ?, ?, ?, ?)
                """,
                (key_value, slug_value, title, source, rendered_svg),
            )

        row = connection.execute(
            "SELECT key, slug, title, source, rendered_svg, created_at, updated_at FROM diagrams WHERE key = ?",
            (key_value,),
        ).fetchone()

    return DiagramRecord(
        key=row["key"],
        slug=row["slug"],
        title=row["title"],
        source=row["source"],
        rendered_svg=row["rendered_svg"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def get_diagram(identifier: str) -> Optional[DiagramRecord]:
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT key, slug, title, source, rendered_svg, created_at, updated_at
            FROM diagrams
            WHERE key = ? OR slug = ?
            """,
            (identifier, identifier),
        ).fetchone()

    if not row:
        return None

    return DiagramRecord(
        key=row["key"],
        slug=row["slug"],
        title=row["title"],
        source=row["source"],
        rendered_svg=row["rendered_svg"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def update_diagram(
    identifier: str,
    *,
    source: str,
    rendered_svg: Optional[str] = None,
    slug: Optional[str] = None,
    title: Optional[str] = None,
) -> Optional[DiagramRecord]:
    existing = get_diagram(identifier)
    if not existing:
        return None

    return create_or_update_diagram(
        source,
        key=existing.key,
        slug=slug,
        title=title,
        rendered_svg=rendered_svg,
    )


def delete_diagram(identifier: str) -> bool:
    with _connect() as connection:
        result = connection.execute(
            "DELETE FROM diagrams WHERE key = ? OR slug = ?",
            (identifier, identifier),
        )
        return result.rowcount > 0


def list_diagrams(search: Optional[str] = None) -> list[DiagramRecord]:
    query = """
        SELECT key, slug, title, source, rendered_svg, created_at, updated_at
        FROM diagrams
    """
    params: tuple[object, ...] = ()
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query += """
        WHERE key LIKE ? OR slug LIKE ? OR title LIKE ? OR source LIKE ?
        """
        params = (pattern, pattern, pattern, pattern)

    query += " ORDER BY datetime(updated_at) DESC, datetime(created_at) DESC"

    with _connect() as connection:
        rows = connection.execute(query, params).fetchall()

    return [
        DiagramRecord(
            key=row["key"],
            slug=row["slug"],
            title=row["title"],
            source=row["source"],
            rendered_svg=row["rendered_svg"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


def duplicate_diagram(identifier: str) -> Optional[DiagramRecord]:
    existing = get_diagram(identifier)
    if not existing:
        return None

    with _connect() as connection:
        new_slug = _next_copy_slug(connection, existing.slug)

    return create_or_update_diagram(
        existing.source,
        title=_next_copy_title(existing.title),
        slug=new_slug,
        rendered_svg=existing.rendered_svg,
    )
