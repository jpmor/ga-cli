# GA Legis

A command-line tool for accessing Georgia General Assembly legislative data — bills, members, committees, and sessions — in a usable, scriptable format.

## Why this exists

Georgia's laws are public record, but accessing them is needlessly difficult. The official legislative website points citizens to LexisNexis, a private company, as the de facto source of truth for both the code and the legislature's ongoing work. There is no bulk download, no public API, and no easy way to answer basic questions like:

- What bills did my senator sponsor this session?
- Which committees reviewed a bill before it passed?
- What legislation was signed into law this year?

This project makes the General Assembly's own data accessible to anyone — researchers, journalists, constituents, and legislators themselves.

## What it does

`ga-cli` is a command-line interface that queries the Georgia General Assembly's data and returns clean, readable output. No login required.

| Command | Description |
|---|---|
| `./ga-cli sessions` | All legislative sessions on record, back to 2001 |
| `./ga-cli members [id] [--chamber] [--session]` | List all members with district and party, or show detail for one |
| `./ga-cli committees [id] [--chamber] [--session]` | List committees, or show membership and subcommittees for one |
| `./ga-cli titles` | All 53 Georgia Code titles |
| `./ga-cli list [--session] [--chamber] [--type] [--enacted] [--limit]` | Search and list bills |
| `./ga-cli show <id>` | Full detail for a bill — sponsors, committees, status history |
| `./ga-cli fetch [--session] [--enacted] [--dry-run]` | Fetch bills and write as markdown files |

### Example output

```
$ ./ga-cli members --chamber senate | head -10
  784  Senate  1st    R  Savannah              Ben Watson
 5007  Senate  2nd    D  Savannah              Derek Mallow
 5013  Senate  3rd    R  Brunswick             Mike Hodges
 4924  Senate  5th    D  Lawrenceville         Sheikh Rahman
 4907  Senate  6th    R  Newnan                Matt Brass
```

```
$ ./ga-cli show 63488
HB 11 — Mitchell County; Board of Education; modify compensation of members; provisions
Session:   2023-2024 Regular Session
Status:    House Date Signed by Governor  (enacted=true)

History:
  2023-01-10 — House Hopper
  2023-01-11 — House First Readers
  2023-01-12 — House Second Readers
  2023-01-30 — House Committee Favorably Reported
  ...
  2023-04-18 — House Date Signed by Governor
```

## Sessions available

The tool has access to all sessions back to 2001, including special sessions:

| Session | Type |
|---|---|
| 2025-2026 | Regular (current) |
| 2023-2024 | Regular |
| 2023 | Special |
| 2021-2022 | Regular |
| 2021 | Special |
| 2020 | Special |
| … back to 2001 | |

## What's next

The longer-term goal is to connect this legislative record to the actual text of Georgia law. Each bill that passes contains explicit instructions for how the Official Code of Georgia should be updated — and currently that process happens inside a private company (LexisNexis) with no public audit trail.

The aim is to build a version of the OCGA maintained directly from the bills that pass, with a commit for each enacted law, so that anyone can see exactly what changed and why.

## Requirements

Python 3.11+. No external dependencies.

## Usage

```
git clone https://github.com/jpmor/ga-legis
cd ga-legis
./ga-cli --help
```

## Contributing

Issues and pull requests welcome. If you work in or around the General Assembly and have thoughts on how this could be more useful, I'd especially like to hear from you.
