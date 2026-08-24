# CVBoreout

A small desktop workbench for professional resumes and cover letters in STEM
fields. You edit on the left and the **actual PDF page** appears on the right —
not an approximation of it, but the very file the export writes.

A local or hosted language model helps with the wording: write the profile,
sharpen bullet points, derive a skills overview, draft the cover letter, review
the resume, or match it against a job posting. With Ollama nothing ever leaves
the machine.

## Quick start

```bash
make setup     # virtual environment + dependencies
make run       # open the app in a window (1360 × 860)
```

The first start loads a sample resume so there is something to look at.
**⋯ → Clear everything** turns it into an empty form.

## How it works

```
data/resume.json ──► render.py ──► HTML+CSS ──► WeasyPrint ──► PDF
   resume + letter                                     │
                                             pypdfium2 └─► PNG ──► preview
```

The resume *and* the cover letter live in one JSON file. `render.py` turns them
into HTML with print CSS
(`@page`, A4, page-break rules), WeasyPrint renders the PDF, and the preview
rasterizes that PDF's pages into images. Because preview and export take the
same path, the export never surprises you. One round trip takes about 0.25 s;
the preview refreshes 0.4 s after the last keystroke.

The interface is a small web app served by a local Python server (standard
library only) and displayed by pywebview in a GTK/WebKit window. The server
listens on `127.0.0.1` only and requires a random token, generated at startup,
for every API call.

## Templates and styling

| Template    | Layout                                             | Suited for                          |
|-------------|----------------------------------------------------|-------------------------------------|
| **Modern**  | coloured side column across all pages, two columns | speculative and direct applications |
| **Classic** | single column, quiet rules                         | large companies, public sector, ATS |
| **Compact** | coloured header band, narrow side column           | a lot of content on little space    |

Adjustable: sixteen accent presets plus a free colour picker, font and size,
line density, proficiency dots on/off, and the order, title, column and
visibility of every section.

The presets run through five blues and five greens from deep to soft, three
neutral and warm tones, and three pastel pairs. Each swatch shows two halves:
the accent that carries headings and rules, and the band colour behind the
modern template's side column. Lettering on that band is chosen from its
luminance — white on the dark presets, near-black on the pastel ones — which
also applies to a colour you pick yourself. Every preset clears 4.5:1 contrast
for headings on white and at least 8:1 for the side column, and the self-test
checks it.

Dates are entered through month/year dropdowns; the *to* field offers a
`present` option that is printed in the document language. Technologies,
interests and bullet points are edited one row at a time, and bullet boxes grow
with their text.

## Cover letter

The switch above the preview chooses what is rendered and exported: **Resume**,
**Cover letter**, or **Both** — the latter writes one PDF with the letter first
and the resume behind it, which is what most applications ask for.

The letter is edited in its own section: recipient, reference number, subject,
date line, salutation, body and enclosures. Salutation, sign-off and date have
sensible defaults for the document language and only need filling in when you
want something else; the date defaults to today. Blank lines separate
paragraphs.

Its layout follows DIN 5008 proportions and picks up the resume's accent
colour, font and header style, so the two documents read as a set. "Write cover
letter" in the assistant drafts the body from the resume and the stored job
posting; "Proofread text" next to it corrects what is already there.

## Language

The switch in the top bar toggles German and English for the interface, the
default section titles, the date wording in the document, and the AI prompts.
Section titles you renamed yourself are left untouched.

## AI assistance

Pick a provider in the assistant panel:

| Provider       | Requirement                                                                  |
|----------------|------------------------------------------------------------------------------|
| **Ollama**     | `ollama serve` running, at least one model pulled (`ollama pull qwen3.5:4b`) |
| **Anthropic**  | API key from console.anthropic.com                                           |
| **OpenAI**     | API key from platform.openai.com                                             |
| **OpenRouter** | API key from openrouter.ai (the model list shows prices per 1M tokens)       |

The model dropdown is filled from the selected provider, the answer is streamed
token by token, and it can be edited in place before you apply it.

| Action             | Result                                                      |
|--------------------|-------------------------------------------------------------|
| Write profile      | 3–4 sentences, applies straight to the profile field        |
| Sharpen bullets    | 3–5 bullets for one position, action verbs and metrics      |
| Derive skills      | categories with entries taken from experience and projects  |
| Write cover letter | four paragraphs drafted from the resume and the job posting |
| Review resume      | five weaknesses, each with a concrete fix                   |
| Match job posting  | match estimate, strengths, gaps, missing keywords           |
| Free instruction   | your own prompt with the resume as context                  |

A job posting stored in the collapsible field feeds into every action. The
prompts forbid invented facts and metrics — check every applied line anyway.

### API keys

Keys are stored in `~/.config/cvboreout/settings.json` (mode 600), never in the
resume file, and are never sent back to the frontend — the interface only learns
whether a key exists. `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` and
`OPENROUTER_API_KEY` are used as a fallback when no key is stored. Requests go
to the selected provider only, and without a key none is made at all.

## Other targets

```bash
make web        # open in the default browser instead of a window
make pdf        # render a PDF headlessly   (TARGET=… FILE=… DOC=resume|letter|both)
make html       # write the intermediate HTML, e.g. to tweak a template
make test       # render every template and check it; artifacts in export/test/
make sample     # write the sample resume to data/resume.json
make clean      # remove build output   (distclean: also .venv)
```

Keyboard: `Ctrl+S` saves, `Ctrl+E` exports, `Ctrl`+wheel zooms the preview.

## Layout

```
cvboreout/
  app.py        entry point: window, web mode, CLI export
  server.py     local HTTP server, JSON API, SSE stream for the assistant
  model.py      document model, defaults, sample, migration of older files
  render.py     JSON -> HTML/CSS, the three templates and the cover letter
  pdf.py        HTML -> PDF (resume, letter or both), PDF -> preview images
  providers.py  Ollama, Anthropic, OpenAI, OpenRouter behind one interface
  prompts.py    prompt building and answer parsing, German and English
  settings.py   provider, model and API keys outside the resume file
  static/       interface (index.html, app.css, app.js, i18n.js – no frameworks)
tests/smoke.py  self-test across all templates, the migration and the prompts
```

## Notes

* The virtual environment is created with `--system-site-packages` because
  pywebview needs the system GTK/WebKit bindings. On Debian/Ubuntu:
  `sudo apt install python3-gi gir1.2-webkit2-4.1` (Qt works as well).
  Without pywebview the app falls back to browser mode.
* A resume written by the first release (`data/lebenslauf.json`, German field
  names) is migrated on first start and saved as `data/resume.json`. Field
  names, template ids, `heute` → `present`, free-text periods and language
  proficiencies are converted; the original file is left untouched.
* A photo is optional and is scaled down to 620 px on import. For many
  employers a resume without a photo is the better choice.
* The footer with name and page number only appears from the second page on;
  the cover letter never carries one.
