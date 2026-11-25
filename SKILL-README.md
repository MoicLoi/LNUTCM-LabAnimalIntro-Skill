# photo-book-to-ebook

A portable agent skill (Anthropic-style `SKILL.md` package) for turning phone photos of a printed book into a proofread ebook — Markdown, HTML, or EPUB.

It was extracted from a real job: 320 phone photos of a Chinese textbook, 321 pages transcribed by 14 parallel workers, audited twice, 10 pages re-shot, and assembled into a 26.9万字 EPUB. Everything that went wrong there is encoded as a rule, a check, or a script.

## What it gives an agent

| | |
|---|---|
| **A workflow** that survives interruption | scaffold → recon → batch transcription → QC gate → visual audit → re-shoot loop → diff marking → build |
| **Three scripts** | project scaffold, page image prep, structural QC (transcript **and** EPUB) |
| **One builder** | dependency-free Markdown/HTML/EPUB assembly, heading-level normalisation included |
| **Six non-negotiables** | the rules whose violation silently ruins a 300-page job (see `SKILL.md`) |

## Install

The package is a directory with `SKILL.md` at its root — that is the de-facto format for agent skills. Any harness that can read one file plus a directory of references can use it.

| Harness | Where to put it |
|---|---|
| WorkBuddy | `~/.workbuddy/skills/photo-book-to-ebook/` |
| Claude Code / Agent Skills | `~/.claude/skills/photo-book-to-ebook/` (or `.claude/skills/` per project) |
| Cursor / Windsurf / Cline | project `.agent/skills/photo-book-to-ebook/` and reference it from the rules file |
| DeepSeek harness, OpenAI-style agents, any custom loop | load `SKILL.md` as the system/tool instruction; expose `scripts/*.py` as callable tools, or let the agent shell out |
| No file access at all | paste `SKILL.md` into the system prompt; the scripts are optional but the rules are not |

## Quick start

```bash
# 1. scaffold
python scripts/init_project.py --photos ./photos --out ./ebook_work --title "书名"

# 2. read 5-8 spread pages, write audit/recon.md   (agent step — see SKILL.md §1)

# 3. transcribe chunk by chunk (agent step — one vision call per page)

# 4. check
python scripts/qc_book.py ebook_work/transcript --json ebook_work/audit/qc.json

# 5. fix / re-shoot flagged pages, then rebuild
python scripts/build_book.py ebook_work/transcript --title "书名" --author "编者" --out ebook_work/dist

# 6. verify the ebook
python scripts/qc_book.py ebook_work/dist/书名.epub --epub
```

## Requirements

- Python 3.8+, standard library only — **except** `scripts/prep_page.py`, which needs Pillow (`pip install pillow`).
- `scripts/build_book.py` uses the `markdown` package when present and falls back to a built-in converter, so it also runs with no third-party packages.
- A vision-capable model for transcription. There is no OCR fallback by design.

## Layout

```
SKILL.md                          # workflow, rules, failure modes  (load this first)
references/transcription-rules.md  # the per-page prompt + house style for tables, units, 存疑
references/qc-checklist.md         # every check, what it catches, how to triage
references/project-layout.md       # directory contract, batching, parallelism, provenance
scripts/init_project.py            # scaffold + chunking + worker guide
scripts/prep_page.py               # rotate / crop / grayscale / contrast before reading
scripts/qc_book.py                 # QC for transcripts and EPUBs, exit code gates a pipeline
scripts/build_book.py              # md + html + epub3
```

## Design notes

- **No OCR, ever.** OCR on book photos produces errors that are invisible to review: right-shaped, wrong-meaning characters. A vision read plus a page-number cross-check catches far more.
- **`□` beats a guess.** An unreadable character is recorded as `□` plus a `【存疑】` note, because a plausible fabrication is unfindable later and a hole is not.
- **Page markers are the spine of the whole pipeline.** QC, deduplication, re-shoots and provenance all key off `<!-- page: N | file: X -->`.
- **Tables are HTML.** Markdown pipe tables cannot express `rowspan`, and the merged-cell structure is usually the meaning (which animal grade requires which test).
- **Two kinds of error stay separate.** "I misread the photo" gets `<del>`/`<ins>`; "the book is wrong" gets a row in a fact-check table. Merging them makes both unauditable.
- **Scripts return exit codes.** `qc_book.py` exits 1 on a blocking issue, so it can gate the build instead of relying on the agent to read the output.

## License

MIT — use, modify, and re-package freely.
