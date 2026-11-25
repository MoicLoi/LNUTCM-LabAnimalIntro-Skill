---
name: photo-book-to-ebook
description: Use when someone has phone photos or scans of a printed book (a chapter, a textbook, a manual) and wants a clean, proofread ebook out of it — Markdown, single-file HTML, or EPUB. Covers batch vision transcription with page bookkeeping, automated structural QC (page continuity, table grids, duplicate paragraphs, tag balance), a re-shoot loop for unreadable pages, diff-marked corrections, and dependency-free EPUB assembly. Also use when an existing photo-based transcription needs auditing, repairing, or rebuilding into an ebook.
license: MIT
agent_created: true
metadata:
  version: "1.0"
  tags: [ocr-free, vision, transcription, epub, proofreading, tables, quality-control]
---

# Photo Book to Ebook

Turn page photos of a printed book into a structured, proofread ebook. The hard parts are not the transcription — they are **page bookkeeping, table structure, and resisting the urge to invent text on blurry pages**. This skill encodes a loop that survives 300-page books.

## When to use

- User hands over N photos/scans of book pages and asks to turn them into an ebook, document, or EPUB.
- User already has a partial transcription and wants it audited, fixed, or assembled.
- The book has dense tables (national standards, statistical appendices) that must keep merged cells.

Do **not** use for: reading a single page, PDF text-layer extraction (use a PDF tool), or handwriting-only material with no printed text.

## Non-negotiables

1. **Read every page with a vision model, one call per page.** Never run OCR (`tesseract`, `pdftotext`, OCR APIs) — layout, vertical text, punctuation and superscripts degrade badly, and OCR errors are hard to audit. If the harness has no vision, stop and tell the user.
2. **Never invent.** If a character or clause is unreadable, write `□` and add `【存疑：…】` with the best hypothesis. A plausible guess is worse than a hole, because nobody can find it later.
3. **Never summarise, paraphrase, or add meta-narrative.** No "本页主要讲述…", no "（此处省略）", no merging two paragraphs into one.
4. **Every page starts with a machine-readable marker.** All downstream QC depends on it:
   `<!-- page: 42 | file: IMG_0421.jpg -->`
   Unknown page number → `<!-- page: ? | file: … -->`.
5. **Reproduce tables as HTML `<table>`, not Markdown pipes**, whenever cells merge. Markdown tables cannot express `rowspan`/`colspan` and silently lose the structure that carries the meaning.
6. **Never "fix" the author.** If the book states a wrong year, a retired standard number, or a definitional swap, transcribe it faithfully, then record the correction as a diff (`<del>`/`<ins>`) or an annotation. "I misread" and "the book is wrong" are different products — the user needs both, but kept apart.

## Workflow

### 0. Scaffold

```bash
python scripts/init_project.py --photos /path/to/photos --out ./ebook_work --title "书名"
```

Creates `chunks/`, `transcript/`, `audit/`, `images/`, `dist/`, a `project.json`, `TRANSCRIBE_GUIDE.md` (the per-page instructions handed to each worker), and numbered chunk files listing photo paths. Default 24 photos per chunk — large enough to amortise overhead, small enough that an interrupted batch does not lose much.

### 1. Recon before mass work (do not skip)

Read **5–8 pages spread across the book** (first page, a table page, a landscape page, the last page) and record findings in `audit/recon.md`:

- Where the printed page number sits, and whether the book uses two numbering systems (Roman front matter + Arabic body). Do not confuse "目录 II–IV" with "正文 2–5".
- Whether some pages are printed landscape (rotated 90°) — they will need rotation before reading.
- Which chapters/sections the photos cover, and the highest table number seen.
- Whether some pages are genuinely blank. Blank pages are normal; a missing page is not.

This ten-minute step prevents the two most expensive mistakes: an off-by-N page numbering across the whole book, and a batch of 24 unreadable landscape pages.

### 2. Transcribe in parallel batches

Dispatch one worker per chunk (in a multi-agent harness) or loop sequentially. Give each worker the same prompt shape:

> Follow `ebook_work/TRANSCRIBE_GUIDE.md`. Read `chunks/chunk_03.txt` (24 image paths). For each image, call the vision tool once and transcribe the full page. Write all pages to `transcript/part_03.md`, each starting with its page marker. Do not OCR. Do not skip pages. Then re-read your own file and verify the page count is 24. Reply only with: page count, page range, pages containing tables/figures, pages that were illegible.

Rules that matter in practice:

- **Ask for the printed page number in every vision call** and cross-check it against the running counter. Page numbers are the cheapest integrity signal available.
- **Rotate before reading** when recon flagged landscape pages — see `scripts/prep_page.py`.
- **Expect table pages to be 2–4× slower.** That is dense reading, not a hang. If a batch stalls, check whether the worker wrote the file at all: an interrupted agent usually leaves nothing on disk, a slow one leaves a partial file.
- **Batch size 20–30.** Beyond that a single failure costs too much; below that overhead dominates.

### 3. QC gate — run before reading anything yourself

```bash
python scripts/qc_book.py transcript/ --json audit/qc.json
```

Reports, per the checks in `references/qc-checklist.md`:

- page count, page-number gaps / duplicates / unknowns
- abnormally short pages (<300 chars) and empty pages
- headings inventory, to compare against the table of contents
- duplicate paragraphs and cross-page duplicates (a classic sign a worker re-emitted the previous page)
- pages ending mid-sentence (legitimate at a page break; suspicious when the next page does not continue)
- tag balance (`<table>`, `<del>`, `<ins>`, `<mark>`) and **table grid integrity** — every row must fill the same column count after applying `rowspan`/`colspan`
- `□` count and `【存疑】` inventory
- banned phrases (本页 / 该页 / 转写 / 原文如此 / 综上所述 …)

Fix everything mechanical first (missing page, duplicated page, broken table). Only then start reading pages.

### 4. Visual audit of flagged pages

For each flagged page, re-open the photo and compare line by line. To read a rotated or low-contrast page, produce a corrected copy instead of squinting:

```bash
python scripts/prep_page.py photo.jpg --rotate 90 --gray --contrast 1.4 --out audit/p42.png
```

- Verify rotation direction once, on one page. A wrong direction yields upside-down text that a vision model will happily "read" into nonsense.
- Crop the single disputed line at 2× before asking about it. Whole-page reads lose the very character being argued about.
- When a page is genuinely illegible, stop guessing and put it on a re-shoot list with the specific reason.

### 5. Re-shoot loop

Produce `reshoot-list.md` with: page, current photo, what is unreadable, and what the new photo must resolve. Ask for flat, evenly lit, uncropped photos; table pages need the page pressed flat and a landscape shot. When new photos arrive, re-read only those pages, then regenerate the QC report.

### 6. Mark corrections, do not silently rewrite

Four distinct states, never mixed:

| Situation | Marking |
|---|---|
| Transcription error, confirmed against the photo | `<del>错文</del><ins>订正</ins>` |
| Transcription error, confirmed and finalised | plain corrected text, recorded in a change log |
| Book's own factual/terminology error | `<del>`/`<ins>` **plus** a row in the fact-check table |
| Cannot confirm | original text + `<mark>【存疑：…】</mark>` |

Copy `transcript/` to `transcript_clean_backup/` before annotating, so the user can diff or roll back.

### 7. Build the ebook

```bash
python scripts/build_book.py transcript/ --title "书名" --author "编者" --out ./dist
```

Produces `book.md`, `book.html`, and `<title>.epub` (EPUB 3: `mimetype` stored first, `container.xml`, `content.opf`, `nav.xhtml`, `toc.ncx` for older readers, XHTML chapters split at top-level headings, two-level navigation). It also:

- applies `<del>`/`<ins>` and converts `【存疑】` into a reader-visible annotation
- normalises heading depth by **numbering pattern** (章=1, 节=2, 一、=3, （一）=4, 1.=5), fixing the usual mess where one chapter emitted `####` and the next `#####` for the same level
- strips page markers from reader-facing output while leaving them in `transcript/`
- self-closes `<br>`/`<img>` and escapes stray `&` so the XHTML actually parses

Validate before delivering:

```bash
python scripts/qc_book.py dist/book.epub --epub
```

## Directory layout

```
ebook_work/
├── project.json          # title, photo root, page mapping, batch size
├── TRANSCRIBE_GUIDE.md   # handed to every transcription worker
├── chunks/               # chunk_01.txt … (one photo path per line)
├── transcript/           # part_00_front.md, part_01.md …
├── transcript_clean_backup/
├── audit/                # recon, rotated/enhanced pages, qc.json, reshoot list
├── images/               # figures or scanned table pages embedded in the ebook
└── dist/                 # book.md, book.html, *.epub
```

Details and rationale: `references/project-layout.md`.

## Quality gates

Ship only when all of these hold:

- Page count equals the number of photos, and the page-number sequence has no unexplained gaps.
- Zero `<table>` with mismatched column counts.
- Zero pages under 300 characters unless confirmed blank or a chapter-end page.
- Every `□` either resolved or listed as pending with a re-shoot request.
- No banned meta phrases.
- EPUB parses: every XHTML/OPF/NCX is well-formed XML, `mimetype` is first and stored, all `src` targets exist.

## Known failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Whole book shifted by N pages | Roman front matter counted as Arabic | Number by printed page, not by photo index |
| Confident nonsense on one page | Reflection, blur, 90° rotation | Re-shoot; never trust a page that failed twice |
| Invented numerals in a data paragraph | Dense numerals + glare | Re-read at 2× crop; sanity-check magnitudes against neighbouring text |
| Table renders shifted, one column short | Rows after a `rowspan` block miss a filler cell | Insert empty `<td>`/`colspan` filler; validate the grid |
| "Empty" table header only | The book really repeats the header on a continuation page | Keep it, annotate as a continuation header |
| Same paragraph on two pages | Worker re-emitted the previous page | Deduplicate; re-read the later page |
| Section 3 appears before Section 2 | Page order misread in a dense header area | Compare against the printed TOC |
| EPUB rejected by reader | `<br>` not self-closed, duplicate `alt`, unescaped `&` | Run the EPUB check in `qc_book.py --epub` |

## Resources

- `references/transcription-rules.md` — the per-page prompt, plus house style for markers, tables, units and 存疑.
- `references/qc-checklist.md` — every check, what it catches, how to triage it.
- `references/project-layout.md` — directory contract, batching, parallelism, naming.
- `scripts/init_project.py` — scaffold a project and generate worker instructions.
- `scripts/prep_page.py` — rotate / grayscale / crop / contrast a page before reading.
- `scripts/qc_book.py` — structural QC for Markdown transcriptions and built EPUBs.
- `scripts/build_book.py` — assemble Markdown, HTML and EPUB.
