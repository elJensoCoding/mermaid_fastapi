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


SLUG_PATTERN = re.compile(r"[^a-z0-9-]+")


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
    return normalized


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
    if not rendered_svg or not rendered_svg.strip():
        raise ValueError("Gerendertes SVG fehlt. Bitte Vorschau laden und erneut speichern.")

    slug_value = slugify(slug) if slug else None
    key_value = key or str(uuid.uuid4())

    with _connect() as connection:
        existing = connection.execute(
            "SELECT key, slug, title, source, rendered_svg FROM diagrams WHERE key = ?",
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
            "SELECT key, slug, title, source, rendered_svg FROM diagrams WHERE key = ?",
            (key_value,),
        ).fetchone()

    return DiagramRecord(
        key=row["key"],
        slug=row["slug"],
        title=row["title"],
        source=row["source"],
        rendered_svg=row["rendered_svg"],
    )


def get_diagram(identifier: str) -> Optional[DiagramRecord]:
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT key, slug, title, source, rendered_svg
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
    )
