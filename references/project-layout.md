# Project layout and batching

## Why a fixed layout

A 300-page book produces 15–20 worker transcripts, a handful of re-shot pages, a dozen enhanced images and three build outputs. Without a fixed contract, the second hour of the job is spent looking for files instead of checking text.

```
ebook_work/
├── project.json           # machine-readable job description
├── TRANSCRIBE_GUIDE.md    # what every worker is told (copy of references/transcription-rules.md + local notes)
├── chunks/
│   ├── chunk_01.txt       # one absolute photo path per line
│   └── …
├── transcript/
│   ├── part_00_front.md   # front matter (cover, TOC, preface)
│   ├── part_01.md         # 24 pages, sequential
│   └── …
├── transcript_clean_backup/   # copy taken before any <del>/<ins> annotation
├── audit/
│   ├── recon.md           # page-numbering scheme, landscape pages, chapter map
│   ├── qc.json            # latest machine report
│   ├── reshoot-list.md    # pages needing a new photo
│   └── p137_rot.png       # corrected copies used for reading
├── images/                # only images that go INTO the ebook
└── dist/
    ├── book.md
    ├── book.html
    └── <title>.epub
```

## Naming

- Photos keep their original names; never rename the user's files. The page marker records the basename, which is the link back to evidence.
- `part_NN.md` is ordered by filename; the build concatenates in lexical order. Front matter is `part_00_front.md` so it sorts first.
- Page markers carry the printed page, not the file index. The two diverge as soon as the book has front matter, inserted plates, or blank pages.

## Batching

- **24 pages per chunk** is the sweet spot: 15 workers for a 320-page book, each a manageable context, and a lost batch costs 24 pages rather than 60.
- Fixed-size chunks are simpler than chapter-aligned chunks, and chapter boundaries do not matter because the build concatenates.
- If the harness runs workers in parallel, cap concurrency at 4–6. Beyond that, vision calls queue and the wall-clock gain disappears while failure recovery gets harder.

## Parallelism and interruption

- An interrupted worker usually leaves **no file**. A slow worker leaves a **partial file**. Distinguish the two before re-dispatching: check for the file and its page count.
- Make each worker verify its own output (`re-read the file and count markers`) and report the count. A worker that cannot state its page count has not finished.
- Re-dispatch only the missing pages, into a `part_NN_fix.md`; the build sorts by page marker anyway, but keeping `part_` files page-monotonic makes manual review easier.

## Provenance

Keep three levels of traceability, because every one of them gets used:

1. **Page marker** — which page, which photo.
2. **Inline comment** — `<!-- recheck: E:/photos/1795.jpg 重拍页已逐字复核 -->` on pages re-read from a second photo. Costs nothing, answers "where did this text come from" months later.
3. **Change log** — a table of page / original / correction / evidence for every `<del>`/`<ins>` pair, exported from the transcript by grep.

## Backup discipline

Before the first `<del>` is written:

```bash
cp -r transcript transcript_clean_backup
```

This is the only copy of "what the transcription said before I edited it". Without it, a questionable correction cannot be audited, and the user cannot tell your edits from the original transcription's errors.

## Scaling notes

- 100 pages: one chunk pass, one QC run, one audit round. Skip the parallel machinery.
- 300 pages: 12–15 chunks, expect 5–10% of pages flagged, expect 10–15 re-shoots.
- 800+ pages: split by chapter, run the QC and audit per chapter, assemble at the end. Keep one `project.json` for the whole book so page numbering stays global.
