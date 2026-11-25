#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Structural QC for a photo-book transcription, or for the EPUB built from it.

    python qc_book.py transcript/                 # audit the markdown transcript
    python qc_book.py transcript/ --json qc.json  # + machine report
    python qc_book.py dist/book.epub --epub       # audit the built ebook

Exit code is 0 when no blocking issue is found, 1 otherwise, so it can gate a pipeline.
Stdlib only.
"""
import argparse, json, os, re, sys, zipfile
from html.parser import HTMLParser
import xml.etree.ElementTree as ET

TERMINAL = '。！？；：”』）】…—·.!?;:)]}'

BANNED = ['本页', '该页', '本段', '转写', '原文如此', '以上为', '下一页', '承接上页',
          '综上所', '（注：', '备注：', '以下是', '我将', '根据图片']

PAGE_RE = re.compile(r'<!--\s*page:\s*([0-9?]+)\s*\|\s*file:\s*([^\s>]+)\s*-->')


# --------------------------------------------------------------------------- #
# markdown transcript
# --------------------------------------------------------------------------- #
class TableGrid(HTMLParser):
    """Collect rows/cells so rowspan/colspan can be simulated."""

    def __init__(self):
        super().__init__()
        self.tables, self.cur = [], None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'table':
            self.cur = []
            self.tables.append(self.cur)
        elif tag == 'tr' and self.cur is not None:
            self.cur.append([])
        elif tag in ('td', 'th') and self.cur is not None and self.cur:
            self.cur[-1].append((int(a.get('colspan', 1)), int(a.get('rowspan', 1))))

    def handle_endtag(self, tag):
        if tag == 'table':
            self.cur = None


def grid_fill(rows):
    occ = {}
    for r, row in enumerate(rows):
        c = 0
        for cs, rs in row:
            while (r, c) in occ:
                c += 1
            for dr in range(rs):
                for dc in range(cs):
                    occ[(r + dr, c + dc)] = 1
            c += cs
    if not occ:
        return [], 0
    width = max(cc for _, cc in occ) + 1
    return [sum(1 for c in range(width) if (r, c) in occ) for r in range(len(rows))], width


def parse_pages(files):
    pages = []
    for fp in files:
        text = open(fp, encoding='utf-8').read()
        parts = list(PAGE_RE.finditer(text))
        for i, m in enumerate(parts):
            end = parts[i + 1].start() if i + 1 < len(parts) else len(text)
            pages.append({
                'page': m.group(1),
                'file': m.group(2),
                'body': text[m.end():end].strip(),
                'source': os.path.basename(fp),
            })
    return pages


def plain(text):
    text = re.sub(r'<[^>]+>', '', text)
    return re.sub(r'\s', '', text)


def qc_transcript(path, photos_dir=None, skip=None):
    skip = set(skip or [])
    files = sorted(os.path.join(path, f) for f in os.listdir(path) if f.endswith('.md'))
    if not files:
        return {'error': f'no .md files in {path}'}, 1
    pages = parse_pages(files)

    report = {'files': len(files), 'pages': len(pages)}
    problems, warnings = [], []

    # --- page numbering ------------------------------------------------------
    nums = [(p['page'], p['source']) for p in pages]
    unknowns = [s for n, s in nums if n == '?']
    seq = [(int(n), s) for n, s in nums if n.isdigit()]
    dups, gaps, order = [], [], []
    seen = {}
    for n, s in seq:
        if n in seen:
            dups.append({'page': n, 'files': [seen[n], s]})
        seen[n] = s
    for (a, _), (b, _) in zip(seq, seq[1:]):
        if b == a:
            continue
        if b < a:
            order.append([a, b])
    present = {n for n, _ in seq}
    if present:
        lo, hi = min(present), max(present)
        gaps = [n for n in range(lo, hi + 1)
                if n not in present and n not in skip]
        report['page_range'] = [lo, hi]
    report['unknown_page_numbers'] = unknowns
    report['duplicate_pages'] = dups
    report['gaps'] = gaps
    report['out_of_order'] = order
    if dups:
        problems.append(f'{len(dups)} duplicate page number(s)')
    if gaps:
        problems.append(f'{len(gaps)} missing page number(s): {gaps[:12]}')
    if order:
        problems.append(f'{len(order)} out-of-order page(s)')
    if unknowns:
        warnings.append(f'{len(unknowns)} page(s) with unknown number')

    # --- length --------------------------------------------------------------
    chars = [(len(plain(p['body'])), p) for p in pages]
    report['total_chars'] = sum(c for c, _ in chars)
    report['empty_pages'] = [p['page'] for c, p in chars if c == 0]
    report['short_pages'] = [{'page': p['page'], 'chars': c,
                              'head': plain(p['body'])[:40]}
                             for c, p in chars if 0 < c < 300]
    if report['empty_pages']:
        problems.append(f"{len(report['empty_pages'])} empty page(s)")
    if report['short_pages']:
        warnings.append(f"{len(report['short_pages'])} page(s) under 300 chars")

    # --- headings ------------------------------------------------------------
    heads = []
    for p in pages:
        for line in p['body'].split('\n'):
            m = re.match(r'^(#{1,6})\s+(.*)$', line)
            if m:
                heads.append({'page': p['page'], 'level': len(m.group(1)),
                              'title': m.group(2).strip()[:60]})
    report['headings'] = heads
    jumps = []
    prev = None
    for h in heads:
        if prev and h['level'] - prev['level'] >= 2:
            jumps.append({'page': h['page'], 'from': prev['level'], 'to': h['level'],
                          'title': h['title']})
        prev = h
    report['heading_jumps'] = jumps

    # --- duplicates ----------------------------------------------------------
    seen_paras, dups_para = {}, []
    for p in pages:
        for para in re.split(r'\n\s*\n', p['body']):
            t = para.strip()
            if len(plain(t)) >= 40 and not t.startswith(('<', '#')):
                if t in seen_paras:
                    dups_para.append({'pages': [seen_paras[t], p['page']], 'text': plain(t)[:50]})
                else:
                    seen_paras[t] = p['page']
    report['duplicate_paragraphs'] = dups_para[:20]
    if dups_para:
        warnings.append(f'{len(dups_para)} duplicated paragraph(s)')

    cross = []
    for a, b in zip(pages, pages[1:]):
        tail = a['body'].strip().split('\n\n')[-1].strip()
        head = b['body'].strip().split('\n\n')[0].strip()
        if len(plain(tail)) > 25 and tail == head:
            cross.append([a['page'], b['page']])
    report['cross_page_duplicates'] = cross
    if cross:
        problems.append(f'{len(cross)} page(s) repeat the previous page')

    # --- truncated pages -----------------------------------------------------
    trunc = []
    for i, p in enumerate(pages):
        t = p['body'].rstrip()
        if not t:
            continue
        # 去掉尾部 HTML 标签后再取最后一个字符；整页以表格/图片结尾的不算截断
        t2 = re.sub(r'(?:<[^>]+>\s*)+$', '', t).rstrip()
        if not t2 or t2.endswith('|'):
            continue
        last_line = t2.split('\n')[-1].strip()
        if last_line.startswith(('#', '<', '>', '-', '![')):
            continue
        if t2[-1] not in TERMINAL:
            # 书页本来就会在句中截断：只有下一页另起标题/表格时才算可疑
            nxt = pages[i + 1]['body'].lstrip() if i + 1 < len(pages) else ''
            suspicious = (not nxt) or bool(re.match(r'^(#{1,6}\s|<table|!\[|>\s*图)', nxt))
            if suspicious:
                trunc.append({'page': p['page'], 'tail': plain(t2)[-30:],
                              'next_starts': nxt[:24].replace('\n', ' ')})
    report['unterminated_pages'] = trunc
    if trunc:
        problems.append(f'{len(trunc)} page(s) end mid-sentence but next page starts a new block')

    # --- tags ----------------------------------------------------------------
    all_text = '\n'.join(p['body'] for p in pages)
    tags = {}
    for tag in ('table', 'tbody', 'tr', 'td', 'th', 'del', 'ins', 'mark', 'sup'):
        o = len(re.findall(rf'<{tag}[\s>]', all_text))
        c = all_text.count(f'</{tag}>')
        if tag in ('tr', 'td', 'th') and o == c:
            continue
        if o != c:
            tags[tag] = [o, c]
    report['unbalanced_tags'] = tags
    if tags:
        problems.append(f'{len(tags)} unbalanced tag type(s)')

    # --- tables --------------------------------------------------------------
    parser = TableGrid()
    parser.feed(all_text)
    bad = []
    for i, rows in enumerate(parser.tables, 1):
        fill, width = grid_fill(rows)
        if width and any(f != width for f in fill):
            bad.append({'table': i, 'columns': width, 'rows': len(rows), 'fill': fill})
    report['tables'] = len(parser.tables)
    report['table_grid_errors'] = bad
    if bad:
        problems.append(f'{len(bad)} table(s) with grid mismatch')

    # --- placeholders --------------------------------------------------------
    boxes = [{'page': p['page'], 'count': p['body'].count('□')}
             for p in pages if '□' in p['body']]
    doubts = []
    for p in pages:
        for m in re.finditer(r'【存疑[：:]([^】]*)】', p['body']):
            doubts.append({'page': p['page'], 'note': m.group(1)[:60]})
    report['box_placeholders'] = boxes
    report['doubts'] = doubts
    if boxes:
        warnings.append(f'{sum(b["count"] for b in boxes)} □ on {len(boxes)} page(s)')

    # --- banned phrases ------------------------------------------------------
    hits = []
    for p in pages:
        body = re.sub(r'<!--.*?-->', '', p['body'], flags=re.S)
        for line in body.split('\n'):
            if len(line) > 200 or line.lstrip().startswith('>'):
                continue
            for w in BANNED:
                if w in line:
                    hits.append({'page': p['page'], 'phrase': w, 'line': line.strip()[:60]})
    report['banned_phrases'] = hits[:20]
    if hits:
        warnings.append(f'{len(hits)} banned meta phrase(s)')

    # --- photo existence -----------------------------------------------------
    if photos_dir and os.path.isdir(photos_dir):
        missing = [p['file'] for p in pages
                   if not os.path.exists(os.path.join(photos_dir, p['file']))]
        report['missing_photos'] = missing[:20]
        if missing:
            problems.append(f'{len(missing)} marker(s) point at non-existent photos')

    report['problems'] = problems
    report['warnings'] = warnings
    return report, (0 if not problems else 1)


# --------------------------------------------------------------------------- #
# epub
# --------------------------------------------------------------------------- #
def qc_epub(path):
    problems, report = [], {}
    if not zipfile.is_zipfile(path):
        return {'error': 'not a zip file'}, 1
    z = zipfile.ZipFile(path)
    names = z.namelist()
    report['files'] = len(names)
    report['mimetype_first'] = names[:1] == ['mimetype']
    info = z.infolist()[0]
    report['mimetype_stored'] = info.filename == 'mimetype' and info.compress_type == zipfile.ZIP_STORED
    report['mimetype_value'] = z.read('mimetype').decode('ascii', 'replace') if 'mimetype' in names else None
    if not report['mimetype_first']:
        problems.append('mimetype is not the first archive entry')
    if not report['mimetype_stored']:
        problems.append('mimetype is compressed (must be stored)')
    if report['mimetype_value'] != 'application/epub+zip':
        problems.append('mimetype content is wrong')

    # container -> opf
    opf = None
    if 'META-INF/container.xml' in names:
        try:
            root = ET.fromstring(z.read('META-INF/container.xml'))
            for el in root.iter():
                if el.tag.endswith('rootfile'):
                    opf = el.attrib.get('full-path')
                    break
        except ET.ParseError as e:
            problems.append(f'container.xml not well-formed: {e}')
    report['opf'] = opf
    if opf and opf not in names:
        problems.append(f'OPF referenced but missing: {opf}')

    # xml well-formedness
    bad_xml = []
    for n in names:
        if n.lower().endswith(('.xhtml', '.html', '.opf', '.ncx', '.xml')):
            try:
                ET.fromstring(z.read(n))
            except ET.ParseError as e:
                bad_xml.append({'file': n, 'error': str(e)})
    report['xml_errors'] = bad_xml
    if bad_xml:
        problems.append(f'{len(bad_xml)} file(s) not well-formed XML')

    # link targets
    base = os.path.dirname(opf) + '/' if opf else ''
    dangling = []
    for n in names:
        if not n.lower().endswith(('.xhtml', '.html', '.ncx', '.opf')):
            continue
        data = z.read(n).decode('utf-8', 'replace')
        for attr in ('src', 'href'):
            for m in re.finditer(rf'{attr}="([^"]+)"', data):
                t = m.group(1)
                if t.startswith(('http://', 'https://', 'data:', 'mailto:', '#')):
                    continue
                target = os.path.normpath(os.path.join(os.path.dirname(n), t.split('#')[0])).replace('\\', '/')
                if target not in names:
                    dangling.append({'from': n, 'target': t})
    report['dangling_links'] = dangling[:20]
    if dangling:
        problems.append(f'{len(dangling)} broken internal link(s)')

    # spine vs manifest
    if opf and opf in names:
        o = z.read(opf).decode('utf-8', 'replace')
        items = re.findall(r'<item\b[^>]*>', o)
        refs = re.findall(r'<itemref\b[^>]*idref="([^"]+)"', o)
        report['manifest_items'] = len(items)
        report['spine_items'] = len(refs)
        ids = {re.search(r'id="([^"]+)"', i).group(1)
               for i in items if re.search(r'id="([^"]+)"', i)}
        missing = [r for r in refs if r not in ids]
        report['spine_missing_manifest'] = missing
        if missing:
            problems.append(f'{len(missing)} spine idref(s) not in manifest')

    report['problems'] = problems
    report['warnings'] = []
    return report, (0 if not problems else 1)


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('target', help='transcript directory, or .epub with --epub')
    ap.add_argument('--epub', action='store_true')
    ap.add_argument('--json', help='write full report to this path')
    ap.add_argument('--photos', help='photo folder, to verify page markers')
    ap.add_argument('--skip-pages', default='',
                    help='page numbers legitimately absent, e.g. "2-5,43"')
    args = ap.parse_args()

    skip = set()
    for part in filter(None, args.skip_pages.split(',')):
        if '-' in part:
            a, b = part.split('-', 1)
            skip.update(range(int(a), int(b) + 1))
        else:
            skip.add(int(part))
    report, code = (qc_epub(args.target) if args.epub
                    else qc_transcript(args.target, args.photos, skip))

    if args.json:
        with open(args.json, 'w', encoding='utf-8') as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)

    if 'error' in report:
        print('ERROR:', report['error'])
        return code

    if args.epub:
        print(f"files      : {report.get('files')}")
        print(f"mimetype   : first={report.get('mimetype_first')} stored={report.get('mimetype_stored')} "
              f"value={report.get('mimetype_value')}")
        print(f"opf        : {report.get('opf')}")
        print(f"manifest   : {report.get('manifest_items')} items, spine {report.get('spine_items')}")
        print(f"xml errors : {len(report.get('xml_errors', []))}   "
              f"broken links: {len(report.get('dangling_links', []))}")
    else:
        print(f"pages      : {report.get('pages')}  chars: {report.get('total_chars')}")
        print(f"range      : {report.get('page_range')}   files: {report.get('files')}")
    if not args.epub:
        print(f"tables     : {report['tables']}  headings: {len(report['headings'])}")
        print(f"short<300  : {len(report['short_pages'])}   empty: {len(report['empty_pages'])}")
        print(f"duplicates : {len(report['duplicate_paragraphs'])} para, {len(report['cross_page_duplicates'])} cross-page")
        print(f"□ / 存疑    : {sum(b['count'] for b in report['box_placeholders'])} / {len(report['doubts'])}")
    print()
    if report['problems']:
        print('BLOCKING (must fix):')
        for p in report['problems']:
            print('  -', p)
    else:
        print('blocking: none')
    if report.get('warnings'):
        print('WARNINGS (review):')
        for w in report['warnings']:
            print('  -', w)
    return code


if __name__ == '__main__':
    sys.exit(main())
