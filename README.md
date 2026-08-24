# CVBoreout

A desktop app for writing a resume and cover letter for STEM jobs and exporting
them as PDF.

## Why

Word templates break as soon as a bullet point grows, online builders want an
account and keep the data, and LaTeX costs an evening before the first line is
written. CVBoreout keeps the content in one JSON file, renders the layout from
it, and shows the finished PDF page while typing — what you see is the file that
gets exported, not a preview of it.

An assistant drafts wording from the resume and a pasted job posting: profile
text, bullet points, skills, the cover letter, a review, or a match report. It
runs against local Ollama or the Anthropic, OpenAI and OpenRouter APIs.

## The design

Three templates: **Modern** (coloured side column across all pages), **Classic**
(single column, ATS-friendly), **Compact** (header band, narrow side column).
The cover letter follows DIN 5008 and picks up the same accent, font and header
style.

Sixteen accent presets — five blues, five greens, neutrals, three pastel pairs —
plus a free colour picker. Every preset holds an accent for headings and a band
colour for the side column; the lettering on that band flips between white and
near-black by luminance, so pastels stay readable. Font, size, line density and
the order, title, column and visibility of every section are adjustable.

## Install

Needs Python 3.11+, and the system GTK/WebKit bindings for the window
(`sudo apt install python3-gi gir1.2-webkit2-4.1` on Debian/Ubuntu; without them
the app falls back to the browser).

```bash
make setup     # virtual environment + dependencies
make run       # open the app
```

Other targets: `make web` (browser instead of a window), `make pdf DOC=resume|letter|both`,
`make html`, `make test`, `make sample`, `make clean`. `make help` lists them.

For the assistant: either `ollama serve` with a pulled model, or an API key
pasted into the assistant panel. Keys are stored in
`~/.config/cvboreout/settings.json` (mode 600), never in the resume file.

## Stack

| Part     | Choice                                                                           |
|----------|----------------------------------------------------------------------------------|
| Layout   | HTML + print CSS (`@page`, A4, page-break rules)                                 |
| PDF      | WeasyPrint                                                                       |
| Preview  | pypdfium2 rasterizes the exported PDF to images                                  |
| Window   | pywebview on GTK/WebKit                                                          |
| Backend  | Python standard library `http.server`, bound to `127.0.0.1` with a startup token |
| Frontend | plain HTML/CSS/JS, no frameworks                                                 |
| AI       | Ollama, Anthropic, OpenAI, OpenRouter over one streaming interface               |

```
cvboreout/
  app.py        entry point: window, web mode, CLI export
  server.py     HTTP server, JSON API, SSE stream
  model.py      document model, sample, migration of older files
  render.py     JSON -> HTML/CSS: templates and cover letter
  pdf.py        HTML -> PDF, PDF -> preview images
  providers.py  the four AI backends
  prompts.py    prompt building and answer parsing (German/English)
  settings.py   provider, model and API keys
  static/       interface
tests/smoke.py  self-test: templates, layout, migration, palette, prompts
```

A resume from the first release (`data/lebenslauf.json`, German field names) is
migrated on first start and saved as `data/resume.json`.
