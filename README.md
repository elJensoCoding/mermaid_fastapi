# Mermaid FastAPI Host

Kleiner FastAPI-Webservice zum Hosten von Mermaid-Diagrammen fuer Intranet-Apps.

Die Anwendung bringt einen einfachen Editor mit Live-Preview mit. Diagramme koennen gespeichert, ueber UUID oder optionalen Slug geteilt und direkt als SVG ausgeliefert werden.

## Features

- Mini-Editor im Browser
- Live-Preview mit Mermaid
- Speicherung per UUID
- Optional sprechende URLs per Slug
- Direkte SVG-Auslieferung ueber Share-URL
- Bearbeiten bereits gespeicherter Diagramme

## Stack

- Python 3.12+
- FastAPI
- Jinja2 Templates
- SQLite als lokale Persistenz
- Mermaid im Browser, lokal vom FastAPI-Service ausgeliefert

## Projektstruktur

```text
app/
  main.py         # FastAPI-Routen
  storage.py      # SQLite-Zugriff
templates/
  editor.html     # Editor-Ansicht
static/
  editor.js       # Preview-Logik
  editor.css      # UI-Styling
data/
  diagrams.db     # lokale SQLite-Datenbank
```

## Lokaler Start

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Danach ist der Editor unter [http://127.0.0.1:8000/](http://127.0.0.1:8000/) erreichbar.

## Routen

- `GET /` zeigt einen neuen Editor mit Beispiel-Diagramm
- `GET /edit/{identifier}` oeffnet ein bestehendes Diagramm zur Bearbeitung
- `POST /edit` speichert ein Diagramm aus dem HTML-Formular
- `POST /api/diagrams` speichert ein Diagramm per JSON
- `GET /api/diagrams/{identifier}` liefert Diagramm-Metadaten und Source als JSON
- `PUT /api/diagrams/{identifier}` aktualisiert ein bestehendes Diagramm
- `DELETE /api/diagrams/{identifier}` loescht ein Diagramm
- `GET /d/{identifier}` liefert das gespeicherte SVG direkt aus

`{identifier}` kann entweder die UUID oder ein optional gesetzter Slug sein.

## API Beispiel

Neues Diagramm speichern:

```bash
curl -X POST http://127.0.0.1:8000/api/diagrams \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Netzwerk",
    "slug": "netzwerk",
    "source": "flowchart LR; A-->B",
    "rendered_svg": "<svg>...</svg>"
  }'
```

Beispielantwort:

```json
{
  "key": "49cd2c3c-32e0-495c-a1ec-bb2861ea632d",
  "slug": "netzwerk",
  "title": "Netzwerk",
  "share_url": "http://127.0.0.1:8000/d/netzwerk",
  "edit_url": "http://127.0.0.1:8000/edit/49cd2c3c-32e0-495c-a1ec-bb2861ea632d"
}
```

Bestehendes Diagramm aktualisieren:

```bash
curl -X PUT http://127.0.0.1:8000/api/diagrams/netzwerk \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Netzwerk v2",
    "slug": "netzwerk",
    "source": "flowchart LR; A-->B; B-->C",
    "rendered_svg": "<svg>...</svg>"
  }'
```

Diagramm lesen:

```bash
curl http://127.0.0.1:8000/api/diagrams/netzwerk
```

Diagramm loeschen:

```bash
curl -X DELETE http://127.0.0.1:8000/api/diagrams/netzwerk
```

## Wichtiger Hinweis zur SVG-Erzeugung

Das SVG wird im Browser durch Mermaid gerendert und beim Speichern mit abgelegt. Dadurch kann die Share-Route das fertige SVG direkt ausliefern, ohne serverseitig einen Headless-Browser starten zu muessen.

Die Mermaid-Bibliothek wird lokal unter `static/vendor/` mit ausgeliefert. Dadurch ist fuer den Editor kein externer CDN-Zugriff noetig.

Falls du bestehende Diagramme aus einer aelteren Version der App hast, sollten diese einmal im Editor neu gespeichert werden, damit das gerenderte SVG mit in der Datenbank liegt.

## Entwicklung

- Die lokale Datenbank liegt in `data/diagrams.db`
- Laufzeit-Logs wie `uvicorn.out.log` und `uvicorn.err.log` sind nicht fuer Git gedacht
- Die Anwendung ist aktuell bewusst klein gehalten und eignet sich gut als Basis fuer zusaetzliche API-Routen wie Update, Delete oder Auth
