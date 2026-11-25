# QC checklist

Run `scripts/qc_book.py` first — it performs the mechanical checks and prints counts plus a JSON file. This document explains what each check is for and how to triage what it finds.

## What the script checks

| Check | Catches | Triage |
|---|---|---|
| page count vs photos | dropped pages, duplicate batches | Missing page → re-read that photo. Duplicate → delete the second copy |
| page-number sequence | gaps, duplicates, `?`, out-of-order | Gap at a chapter boundary is often a blank page; gap mid-chapter is a real miss |
| pages < 300 chars | truncated transcription, worker gave up | Open the photo: blank / chapter-end / genuinely short? |
| empty pages | worker wrote a marker and nothing else | Same |
| heading inventory | wrong levels, missing chapter opening | Compare against the printed TOC |
| duplicate paragraphs (≥40 chars) | copy-paste across pages | Keep the page where it belongs; re-read the other |
| cross-page duplicate (tail of page N = head of N+1) | worker re-emitted a page | Re-read the later page |
| page ends without terminal punctuation | truncated sentence | Legitimate at a page break; if the next page does not continue it, the page was cut short |
| tag balance | half-written `<table>`/`<del>` | Repair by hand |
| table grid (rowspan/colspan simulation) | shifted or short rows | Add filler `<td>`/`colspan`; then re-run |
| `□` and `【存疑】` inventory | unreadable regions | Resolve or put on the re-shoot list |
| banned phrases | model meta-narrative | Delete the sentence |

## Checks that need a human eye

The script cannot tell a **correctly short** page from a **truncated** one, and cannot tell a **book error** from a **transcription error**. Both need the photo.

When reading a flagged page:

1. Open the photo next to the transcription, same scale.
2. Read the first and last line of the page in the photo, then compare with the transcription. Truncation almost always loses the bottom third.
3. Check any number in the flagged region against its neighbours (a genome size of `3×10⁷` next to a claim of "30 times the human genome" is self-contradictory — one of them was misread).
4. Check heading order against the printed TOC before changing anything.

## Table grid triage

A table is only correct when every row occupies the same number of columns **after** simulating `rowspan`/`colspan`. The script prints the per-row fill; a row short by *k* columns means *k* cells are missing.

Where to put the filler matters:

- Shortage in the **grade/label band** (the merged cells at the left) → insert the filler at the **start** of the row, with `colspan="k"`.
- Shortage in the **data band** (an empty cell for "not tested") → insert the filler at the **end** of the row.
- Get this wrong and the table still renders — with the data shifted one column. Compare the rendered row against the photo before accepting.

## Sign-off before building

- [ ] page count == number of photos
- [ ] no unexplained page-number gaps
- [ ] no table with a grid mismatch
- [ ] no page under 300 chars without a reason
- [ ] every `□` resolved or on the re-shoot list
- [ ] no banned phrases
- [ ] heading levels consistent across chapters
- [ ] corrections recorded as diffs, with a backup of the unannotated text

## After building the EPUB

`python scripts/qc_book.py dist/book.epub --epub` checks:

- `mimetype` is the first entry and stored uncompressed
- `META-INF/container.xml` points at an existing OPF
- every XHTML/OPF/NCX parses as XML (this is where unclosed `<br>`, duplicate `alt`, and bare `&` surface)
- every `src`/`href` target exists inside the archive
- spine and manifest agree in count
- navigation entries resolve to existing files and anchors
