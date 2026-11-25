# Transcription rules

Hand these to every transcription worker. They are deliberately mechanical — the whole point is that 14 workers produce one consistent book.

## Page marker

Every page begins with exactly one marker line, nothing before it:

```
<!-- page: 137 | file: IMG_20261125_154715.jpg -->
```

- `page` is the **printed** page number. If the page has no printed number but the sequence is unambiguous, use the inferred number and note it in `audit/recon.md`. If it is genuinely ambiguous, write `?`.
- `file` is the basename of the photo, so any claim can be re-checked against a specific image.
- Never put the marker inside a paragraph, and never omit it because "the page is nearly blank". A blank page still gets a marker and one line saying so.

## Per-page prompt

The worker sends one vision call per page. Ask for the page number first, then the content, then the structure:

> This is a page from a printed book. First state the printed page number visible on the page. Then transcribe **all** text on the page exactly as printed — headings, body, captions, table titles, table cells, footnotes — preserving paragraph breaks and heading hierarchy. Do not summarise, do not correct, do not add anything that is not printed. For tables, list the title, the header row, every row, the units, and any table notes; say explicitly if a cell is empty. Note whether the page is rotated (landscape) or has figures.

For a page that returns obviously wrong content (numbers that do not match the neighbouring sentences, a paragraph that reappears on the next page), treat it as a failed read and photograph again — do not try to repair it from context.

## Text fidelity

- Keep the book's own punctuation style: full-width `，。；：""（）` in Chinese text, half-width inside Latin/units as printed.
- Keep original spacing around units and numbers: `9.7×10⁷ 碱基对`, `15 次/h`, `2n=38`. Do not normalise to your own habit.
- Preserve superscripts and subscripts: `10⁷`, `mm³`, `CO₂`. Use Unicode characters rather than `<sup>` in running text; use `<sup>` only where the book uses footnote letters (`<sup>a</sup>`).
- Latin binomials keep italics as printed where the source marks them; otherwise plain.
- Symbol glyphs in detection tables are content, not decoration: `●` required, `○` optional, `◎` immunodeficient-only, `▲` required-but-immunisable, `—` not applicable. Transcribe the glyph; never convert it to "yes/no".
- List numbering is content: `一、`, `（一）`, `1.`, `（1）`, `①` are five different levels. Keep them.

## Headings

- Emit a heading for a heading, with `#` depth matching the numbering level: 章 = `#`, 节 = `##`, `一、` = `###`, `（一）` = `####`, `1.` = `#####`, `（1）` = `######`.
- If the page continues a paragraph from the previous page, do **not** start a new heading; continue the paragraph.
- If a heading's number and its content disagree with the table of contents, transcribe as printed and flag it in the reply. Do not silently reorder.

## Tables

- Always HTML `<table>`, with `<thead>` and `<tbody>`, when any cell spans rows or columns.
- Model the merge structure honestly:

```html
<tr><td rowspan="6">无菌动物</td><td rowspan="6">无特定病原体动物</td>
    <td rowspan="2">普通动物</td><td>体外寄生虫 Ectoparasites</td><td>●</td><td>●</td><td>●</td></tr>
<tr><td>弓形虫 Toxoplasma gondii</td><td>●</td><td>●</td><td>●</td></tr>
<tr><td></td><td>鞭毛虫 Flagellates</td><td>●</td><td>●</td><td>●</td></tr>
```

Note the empty `<td></td>` on the third row: after the inner `rowspan` block ends, later rows still need a placeholder for that column, otherwise every cell shifts one place to the left and the table looks plausible but says something false.

- A repeated header with no data rows is a real continuation header, not an error: keep it and add `<!-- 续表头 -->`.
- Transcribe table notes (`注1：…`) and footnote markers (`*`, `a`) immediately after the table, in order.
- Wide statistical tables (means and ranges in every cell) are transcription traps. Either transcribe every cell with a second verification pass, or transcribe title/header/row labels and attach a prepared image of the page — and say which choice was made.

## Page breaks

- A sentence split across pages is one sentence in the output only if the bytes continue. Otherwise keep the two halves on their own pages; the build step joins nothing.
- Never write "承接上页", "接上页", "（下页续）". The marker already encodes the relationship.

## Uncertainty

- Unreadable glyph → `□`, one per missing character. Then, if the context makes a word likely, append `<mark>【存疑：疑为“X”，原图模糊】</mark>`.
- Never fill `□` with a guess and drop the mark. Never delete the `□` and leave a gap.
- Add `【存疑】` for factual oddities you cannot resolve from the page (a date that contradicts the surrounding text). Keep it factual: what is printed, what looks wrong, what would settle it.

## What a worker reports back

Keep it to five lines — the orchestrator does not need prose:

```
pages: 24 (137–160)
tables: 138, 141–143
figures: 139
illegible: 141 (16× □, grey print), 152 (reflection)
anomalies: 148 heading order vs TOC
```
