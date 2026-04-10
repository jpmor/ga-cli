# AGENTS.md

## What this is

A Python CLI and library for querying the Georgia General Assembly's legislative data and the Official Code of Georgia (OCGA). Two data sources:

- **GA legislature API** (`legis.ga.gov/api/`) — bills, members, committees, sessions
- **Justia** (`law.justia.com/codes/georgia/`) — OCGA statute text, server-rendered HTML, no auth required

## Running the CLI

```
./ga-cli sessions
./ga-cli members --chamber house
./ga-cli members 754
./ga-cli committees --session 1033 --chamber house
./ga-cli committees 87
./ga-cli list --session 1033 --enacted
./ga-cli list --session 1032 --chamber house --type resolution --limit 20
./ga-cli show 69281
./ga-cli fetch --session 1032 --enacted --dry-run

./ga-cli code              # all 53 OCGA titles
./ga-cli code 31           # chapters in Title 31
./ga-cli code 31-36A       # sections in Chapter 36A (alphanumeric chapter IDs are supported)
./ga-cli code 31-36A-1     # text of § 31-36A-1
./ga-cli code 40-6-391     # auto-resolves article sub-level (title-40/chapter-6/article-15/)
./ga-cli code 1-1-1 --year 2020  # older version of a section
```

## Project structure

```
ga-cli          # Executable CLI — argparse, subcommands, output formatting, markdown serialization
legis/
  client.py     # Auth token generation + raw HTTP wrapper (GA legislature API)
  models.py     # Dataclasses: Session, Bill, Member, Committee, CommitteeMember, CodeTitle, etc.
  api/
    __init__.py     # Re-exports all public functions
    sessions.py
    members.py
    committees.py
    titles.py
    legislation.py
code/
  client.py     # Plain urllib fetcher for Justia; resolves article sub-levels on 404
  models.py     # Section dataclass
  parser.py     # HTMLParser subclass targeting div#codes-content; tree-based li extraction
  api.py        # get_section(), get_title_toc(), get_chapter_toc()
```

## GA legislature API authentication

The API at `https://www.legis.ga.gov/api/` uses an obfuscated but public token scheme found in the site's JS bundle:

```python
key = SHA512("QFpCwKfd7f" + obscure_key + "letvarconst" + str(timestamp_ms))
token = GET /api/authentication/token?key={key}&ms={timestamp_ms}
```

The token is a JWT valid for ~5 minutes. All subsequent requests use `Authorization: Bearer {token}`. Tokens are refreshed automatically in `legis/client.py`.

## Key GA legislature API endpoints

| Endpoint | Notes |
|---|---|
| `GET /api/sessions` | All sessions back to 2001 |
| `GET /api/members/list/{sessionId}` | Full member list with district, party, city |
| `GET /api/committees/list/{sessionId}` | Committee list for a session |
| `GET /api/committees/details/{id}/{sessionId}` | Committee detail with membership and subcommittees |
| `GET /api/georgia-code/titles` | All 53 OCGA titles (used by `code` with no arg) |
| `GET /api/legislation/detail/{id}` | Full bill detail |
| `POST /api/Legislation/Search/{pageSize}/{page}` | Bill search — body is JSON filter object |
| `GET /api/legislation/html/{library}/{versionId}` | Bill text as array of HTML pages (PDF-rendered) |

The `library` key is derived from the session (e.g. `"20252026"` for the 2025-2026 session).

## Justia URL structure

```
https://law.justia.com/codes/georgia/title-{N}/                         # title TOC
https://law.justia.com/codes/georgia/title-{N}/chapter-{M}/             # chapter TOC (may have articles)
https://law.justia.com/codes/georgia/title-{N}/chapter-{M}/article-{A}/ # article TOC
https://law.justia.com/codes/georgia/title-{N}/chapter-{M}/section-{ID}/ # section text
```

- Chapter and section IDs are **lowercased** in Justia URLs (e.g. `chapter-36a`, `section-31-36a-1`)
- Some chapters have an intermediate `article-{N}/` level; `code/client.py` resolves this automatically on 404

## Justia HTML parsing

Statute text lives in `<div id="codes-content">`. Content is `<ul class="list-no-styles"><li>` trees; parser uses a stack of `_LiNode` objects and pre-order traversal to produce parent-before-children output. History appears as `<p><em>...</em></p>` outside the list items.

## Key data model facts

- `Bill.id` (`legislationId`) is the global unique key across all sessions
- Natural key: `(session_id, chamber, document_type, number, suffix)` — e.g. "HB 1 of session 1033"
- `documentType`: 1 = Bill, 2 = Resolution; `chamberType`: 1 = House, 2 = Senate
- Bill statuses containing "Signed by Governor" or "Read and Adopted" indicate enacted legislation
- `party`: 0 = Democrat, 1 = Republican (on Member objects)
- Bill text HTML is PDF-rendered with absolute-positioned spans; `legis/api/legislation.py` strips line numbers and page headers

## Fetched bill markdown format

Bills written by `fetch` go to `bills/{session-description}/{type-abbr}/{TYPE}-{number:04d}.md` with YAML frontmatter (id, label, session, sponsors, committees, status, enacted) and a `## History` section.
