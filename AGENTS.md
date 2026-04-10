# AGENTS.md

## What this is

A Python CLI and library for querying the Georgia General Assembly's legislative data. The GA legislature website is an Angular SPA backed by a REST API; this project reverse-engineered that API and wraps it in a usable interface.

## Running the CLI

```
./ga-cli sessions
./ga-cli members --chamber house
./ga-cli members 754
./ga-cli committees --session 1033 --chamber house
./ga-cli committees 87
./ga-cli titles
./ga-cli list --session 1033 --enacted
./ga-cli list --session 1032 --chamber house --type resolution --limit 20
./ga-cli show 69281
./ga-cli fetch --session 1032 --enacted --dry-run
```

## Project structure

```
ga-cli          # Executable CLI — argparse, subcommands, output formatting, markdown serialization
legis/
  client.py     # Auth token generation + raw HTTP wrapper
  models.py     # Dataclasses: Session, Bill, Member, Committee, CommitteeMember, CodeTitle, etc.
  api/
    __init__.py     # Re-exports all public functions
    sessions.py
    members.py
    committees.py
    titles.py
    legislation.py
```

## API authentication

The GA legislature API at `https://www.legis.ga.gov/api/` uses an obfuscated but public token scheme found in the site's JS bundle:

```python
key = SHA512("QFpCwKfd7f" + obscure_key + "letvarconst" + str(timestamp_ms))
token = GET /api/authentication/token?key={key}&ms={timestamp_ms}
```

The token is a JWT valid for ~5 minutes. All subsequent requests use `Authorization: Bearer {token}`. This is implemented in `legis/client.py`. Tokens are refreshed automatically.

## Key API endpoints

| Endpoint | Notes |
|---|---|
| `GET /api/sessions` | All sessions back to 2001 |
| `GET /api/members/list/{sessionId}` | Full member list with district, party, city |
| `GET /api/members/search-options` | Lightweight member list (no district) |
| `GET /api/committees/list/{sessionId}` | Committee list for a session |
| `GET /api/committees/details/{id}/{sessionId}` | Committee detail with membership and subcommittees |
| `GET /api/georgia-code/titles` | All 53 OCGA titles |
| `GET /api/legislation/detail/{id}` | Full bill detail |
| `POST /api/Legislation/Search/{pageSize}/{page}` | Bill search — body is JSON filter object |
| `GET /api/legislation/html/{library}/{versionId}` | Bill text as array of HTML pages (PDF-rendered) |
| `GET /api/legislation/document/{library}/{versionId}` | Bill PDF (no auth required) |

The `library` key is derived from the session (e.g. `"20252026"` for the 2025-2026 session).

## Key data model facts

- `Bill.id` (`legislationId`) is the global unique key across all sessions
- Natural key: `(session_id, chamber, document_type, number, suffix)` — e.g. "HB 1 of session 1033"
- `documentType`: 1 = Bill, 2 = Resolution
- `chamberType`: 1 = House, 2 = Senate
- Bill statuses containing "Signed by Governor" or "Read and Adopted" indicate enacted legislation
- `party`: 0 = Democrat, 1 = Republican (on Member objects)
- Bill text HTML is PDF-rendered with absolute-positioned spans; `legis/api/legislation.py` extracts plain text and strips line numbers and page headers

## Fetched bill markdown format

Bills written by `fetch` go to `bills/{session-description}/{type-abbr}/{TYPE}-{number:04d}.md` with YAML frontmatter (id, label, session, sponsors, committees, status, enacted) and a `## History` section.
