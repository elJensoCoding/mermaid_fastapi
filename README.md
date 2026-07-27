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
- Kleine Listenansicht fuer gespeicherte Diagramme
- Optionaler Basic-Auth-Schutz fuer Editor und Schreibzugriffe
- Diagramme koennen als neue Kopie dupliziert werden
- PNG-Export direkt aus der Browser-Vorschau

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

## Betrieb als eigener Container

Wenn du den Mermaid-Service lieber separat neben deinen Hauptservice stellen willst, ist das hier der einfachste Weg.

Image mit Podman bauen:

```bash
podman build -t mermaid-fastapi -f Containerfile .
```

Container mit Podman starten:

```bash
podman run --rm -p 8000:8000 -v mermaid-fastapi-data:/app/data:Z mermaid-fastapi
```

Mit Basic Auth:

```bash
podman run --rm -p 8000:8000 \
  -e MERMAID_EDITOR_USERNAME=admin \
  -e MERMAID_EDITOR_PASSWORD=ein-sicheres-passwort \
  -v mermaid-fastapi-data:/app/data:Z \
  mermaid-fastapi
```

Mit Compose-Datei:

```bash
docker compose up --build
```

Oder mit Podman Compose:

```bash
podman-compose up --build
```

Hinweise zum Container-Betrieb:

- die SQLite-Datenbank liegt im Container unter `/app/data/diagrams.db`
- das Volume `/app/data` sollte persistent gemountet werden
- der Container startet absichtlich nur `uvicorn` und braucht keine weiteren Systempakete
- der Service ist damit gut als kleiner Sidecar- oder Zusatzservice hinter Reverse Proxy nutzbar
- bei Podman ist das `:Z` am Volume-Mount fuer SELinux-Kontexte oft sinnvoll

## Routen

- `GET /` zeigt einen neuen Editor mit Beispiel-Diagramm
- `GET /diagrams` zeigt die gespeicherten Diagramme als Liste
- `GET /edit/{identifier}` oeffnet ein bestehendes Diagramm zur Bearbeitung
- `POST /edit` speichert ein Diagramm aus dem HTML-Formular
- `POST /edit/{identifier}/delete` loescht ein Diagramm aus dem Editor heraus
- `POST /edit/{identifier}/duplicate` erstellt eine Kopie eines Diagramms
- `POST /api/diagrams` speichert ein Diagramm per JSON
- `GET /api/diagrams/{identifier}` liefert Diagramm-Metadaten und Source als JSON
- `PUT /api/diagrams/{identifier}` aktualisiert ein bestehendes Diagramm
- `DELETE /api/diagrams/{identifier}` loescht ein Diagramm
- `POST /api/diagrams/{identifier}/duplicate` erstellt per API eine Kopie
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

Diagramm duplizieren:

```bash
curl -X POST http://127.0.0.1:8000/api/diagrams/netzwerk/duplicate
```

## Wichtiger Hinweis zur SVG-Erzeugung

Das SVG wird im Browser durch Mermaid gerendert und beim Speichern mit abgelegt. Dadurch kann die Share-Route das fertige SVG direkt ausliefern, ohne serverseitig einen Headless-Browser starten zu muessen.

Die Mermaid-Bibliothek wird lokal unter `static/vendor/` mit ausgeliefert. Dadurch ist fuer den Editor kein externer CDN-Zugriff noetig.

Der PNG-Export passiert ebenfalls lokal im Browser: Die aktuelle SVG-Vorschau wird auf ein Canvas gezeichnet und dann als PNG heruntergeladen.

Falls du bestehende Diagramme aus einer aelteren Version der App hast, sollten diese einmal im Editor neu gespeichert werden, damit das gerenderte SVG mit in der Datenbank liegt.

## Entwicklung

- Die lokale Datenbank liegt in `data/diagrams.db`
- Laufzeit-Logs wie `uvicorn.out.log` und `uvicorn.err.log` sind nicht fuer Git gedacht
- Die Anwendung ist aktuell bewusst klein gehalten und eignet sich gut als Basis fuer zusaetzliche API-Routen wie Update, Delete oder Auth

## Integration in einen bestehenden FastAPI Service

Wenn du die Funktion morgen in einen bestehenden Service uebernehmen willst, ist der einfachste Weg meistens kein kompletter 1:1-Umzug der App, sondern das Einhaengen der Bausteine:

1. `app/storage.py` uebernehmen
2. die Mermaid-UI-Dateien unter `templates/`, `static/` und `static/vendor/` mitnehmen
3. die relevanten Routen aus `app/main.py` in deinen bestehenden Router oder in ein eigenes Modul verschieben
4. `init_db()` beim App-Start aufrufen

Praktisch sind dabei diese Teile:

- `app/storage.py` fuer Persistenz, Slugs, Duplikate und Listenlogik
- `templates/editor.html` und `templates/list.html` fuer Editor und Uebersicht
- `static/editor.js`, `static/editor.css` und `static/vendor/mermaid.min.js` fuer Preview, PNG-Export und UI

Wenn dein bestehender Service schon ein `FastAPI()`-Objekt hat, ist ein Router-Ansatz oft am saubersten:

```python
from fastapi import APIRouter

router = APIRouter(prefix="/mermaid", tags=["mermaid"])

# hier die Mermaid-Routen an den Router haengen
# danach:
# app.include_router(router)
```

Dann werden daraus zum Beispiel:

- `/mermaid/`
- `/mermaid/diagrams`
- `/mermaid/edit/{identifier}`
- `/mermaid/d/{identifier}`

Wenn du einen Prefix nutzt, achte auf diese Punkte:

- Links in den Templates sollten dann relativ zum Prefix passen
- `StaticFiles` sollte unter demselben Prefix oder zentral im Hauptservice gemountet sein
- `request.base_url` in den JSON-Antworten bleibt nutzbar, aber die Pfade muessen zum Prefix passen

Fuer einen schnellen Umbau ist diese Reihenfolge am angenehmsten:

1. `storage.py` und DB-Initialisierung uebernehmen
2. statische Assets und Templates einhaengen
3. erst `GET /d/{identifier}` und `POST /api/diagrams` integrieren
4. danach Editor, Liste, Delete, Duplicate und PNG-Export anschliessen

Worauf du besonders achten solltest:

- `python-multipart` wird fuer das HTML-Formular benoetigt
- bestehende Alt-Datensaetze ohne `rendered_svg` muessen einmal neu gespeichert werden
- `static/vendor/mermaid.min.js` muss wirklich mit ausgerollt werden
- wenn dein Hauptservice schon Auth hat, kannst du die eingebaute Basic-Auth-Logik in `app/main.py` meist weglassen oder an dein System anpassen

## Optionaler Basic Auth Schutz

Wenn Editor und schreibende API-Routen geschuetzt werden sollen, koennen diese Umgebungsvariablen gesetzt werden:

```powershell
$env:MERMAID_EDITOR_USERNAME="admin"
$env:MERMAID_EDITOR_PASSWORD="ein-sicheres-passwort"
```

Geschuetzt werden dann:

- `GET /`
- `GET /diagrams`
- `GET /edit/{identifier}`
- `POST /edit`
- `POST /edit/{identifier}/delete`
- `POST /api/diagrams`
- `PUT /api/diagrams/{identifier}`
- `DELETE /api/diagrams/{identifier}`

Die reine SVG-Auslieferung ueber `GET /d/{identifier}` bleibt weiterhin offen.
