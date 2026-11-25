#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scaffold an ebook project from a folder of page photos.

    python init_project.py --photos ./photos --out ./ebook_work --title "My Book"

Creates the directory contract described in references/project-layout.md,
plus per-batch chunk files and the worker guide.
"""
import argparse, json, os, re, shutil, sys

IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff', '.heic'}

GUIDE = """# Transcription guide — {title}

Read this before touching any page. Violating rule 1 or 2 invalidates the work.

## Non-negotiables

1. Read each page with the vision capability, **one call per page**. Never OCR.
2. Never invent text. Unreadable character -> `□` plus `<mark>【存疑：…】</mark>`.
3. Never summarise, paraphrase, or add "本页主要讲述…".
4. Every page starts with exactly one marker:
   `<!-- page: 137 | file: IMG_0001.jpg -->`
   (`page` = printed page number; unknown -> `?`)
5. Merged cells -> HTML `<table>`, never Markdown pipes.
6. Reproduce the book's errors; do not fix them. Corrections go in `<del>`/`<ins>`
   only when the user has approved a correction pass.

## Per-page prompt

> This is a page from a printed book. First state the printed page number visible
> on the page. Then transcribe all text exactly as printed — headings, body,
> captions, table titles, table cells, footnotes — preserving paragraph breaks and
> heading hierarchy. Do not summarise, do not correct, do not add anything that is
> not printed. For tables, give the title, header row, every row, units and table
> notes; say explicitly if a cell is empty. Note if the page is rotated or has figures.

## Heading depth

章 = `#`, 节 = `##`, 一、 = `###`, （一） = `####`, 1. = `#####`, （1） = `######`.

## Tables

Use `<thead>`/`<tbody>`. When an inner `rowspan` block ends, later rows still need an
empty `<td></td>` placeholder for that column, or every cell shifts left.
A repeated header with no rows is a real continuation header: keep it with `<!-- 续表头 -->`.

## Report back (5 lines, nothing else)

```
pages: 24 (137-160)
tables: 138, 141-143
figures: 139
illegible: 141, 152
anomalies: 148 heading order vs TOC
```
"""

def natural_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s)]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--photos', required=True, help='folder containing page photos')
    ap.add_argument('--out', default='./ebook_work')
    ap.add_argument('--title', default='Untitled')
    ap.add_argument('--start-page', type=int, default=1,
                    help='printed page number of the first photo')
    ap.add_argument('--batch', type=int, default=24, help='photos per chunk')
    ap.add_argument('--front-matter', type=int, default=0,
                    help='number of leading photos treated as front matter (part_00_front.md)')
    args = ap.parse_args()

    photos = sorted(
        (os.path.join(os.path.abspath(args.photos), f) for f in os.listdir(args.photos)
         if os.path.splitext(f)[1].lower() in IMAGE_EXT),
        key=lambda p: natural_key(os.path.basename(p)))
    if not photos:
        sys.exit(f'no images found in {args.photos}')

    for sub in ('chunks', 'transcript', 'audit', 'images', 'dist'):
        os.makedirs(os.path.join(args.out, sub), exist_ok=True)

    chunks = []
    for i in range(0, len(photos), args.batch):
        name = f'chunk_{len(chunks) + 1:02d}.txt'
        with open(os.path.join(args.out, 'chunks', name), 'w', encoding='utf-8') as fh:
            fh.write('\n'.join(photos[i:i + args.batch]) + '\n')
        chunks.append({'file': name, 'count': len(photos[i:i + args.batch]),
                       'first': os.path.basename(photos[i]),
                       'last': os.path.basename(photos[min(i + args.batch, len(photos)) - 1])})

    project = {
        'title': args.title,
        'photo_root': os.path.abspath(args.photos),
        'photo_count': len(photos),
        'start_page': args.start_page,
        'batch_size': args.batch,
        'front_matter': args.front_matter,
        'chunks': chunks,
        'page_marker': '<!-- page: {page} | file: {file} -->',
    }
    with open(os.path.join(args.out, 'project.json'), 'w', encoding='utf-8') as fh:
        json.dump(project, fh, ensure_ascii=False, indent=2)

    with open(os.path.join(args.out, 'TRANSCRIBE_GUIDE.md'), 'w', encoding='utf-8') as fh:
        fh.write(GUIDE.format(title=args.title))

    print(f'photos   : {len(photos)}')
    print(f'chunks   : {len(chunks)} x {args.batch}')
    print(f'out      : {os.path.abspath(args.out)}')
    if args.front_matter:
        print(f'front    : first {args.front_matter} photo(s) -> transcript/part_00_front.md')
    print('\nnext: read 5-8 spread pages, record audit/recon.md, then dispatch chunks/*.txt')

if __name__ == '__main__':
    main()
