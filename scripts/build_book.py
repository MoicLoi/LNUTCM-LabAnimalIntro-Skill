#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assemble a transcript folder into book.md, book.html and an EPUB 3.

    python build_book.py transcript/ --title "书名" --author "编者" --out ./dist

- applies <del>/<ins> (delete original, keep correction)
- turns 【存疑：…】 into a reader-visible annotation
- normalises heading depth by numbering pattern
- strips page markers from reader-facing output
- splits EPUB chapters at top-level headings, two-level navigation
- uses the `markdown` package when available, otherwise a built-in converter
Stdlib only (markdown optional).
"""
import argparse, html, os, re, sys, uuid, zipfile, datetime

CN = '一二三四五六七八九十'
TERMINAL = '。！？；：”』）】…—.!?;:'

CSS = """body{font-family:"Songti SC","SimSun",Georgia,serif;line-height:1.85;margin:0 auto;
max-width:42em;padding:2em 1.2em;color:#1a1a1a;background:#fff}
h1{font-size:1.7em;text-align:center;margin:2.2em 0 1.2em;border-bottom:2px solid #333;padding-bottom:.4em}
h2{font-size:1.3em;margin:1.8em 0 .8em}h3{font-size:1.12em;margin:1.5em 0 .6em}
h4,h5,h6{font-size:1.02em;margin:1.2em 0 .5em}
p{text-indent:2em;margin:.55em 0;text-align:justify}
table{border-collapse:collapse;width:100%;margin:1em 0;font-size:.86em}
th,td{border:1px solid #666;padding:.3em .4em;text-align:center}
th{background:#f2f2f2}
blockquote{margin:1em 0;padding:.4em 1em;border-left:3px solid #bbb;color:#555;text-indent:0}
img{max-width:100%;display:block;margin:1em auto}
sup{font-size:.75em}
.cover{text-align:center;margin-top:28%}
.booktitle{font-size:2.2em;letter-spacing:.2em;border:none}
.booksub{margin-top:3em;color:#444}
"""

# --------------------------------------------------------------------------- #
def clean(text):
    text = re.sub(r'<!--\s*page:\s*[^>]*?-->', '', text)
    text = re.sub(r'<!--\s*recheck:[^>]*?-->', '', text)
    text = re.sub(r'<!--\s*表格[^>]*?-->', '<!-- 续表 -->', text)
    text = re.sub(r'<!--\s*diff[^>]*?-->', '', text)
    text = re.sub(r'<!--\s*(?!续表)[^>]*?-->', '', text)
    text = re.sub(r'<del>.*?</del>', '', text, flags=re.S)
    text = re.sub(r'<ins>(.*?)</ins>', r'\1', text, flags=re.S)
    text = re.sub(r'<mark>\s*【存疑[：:](.*?)】\s*</mark>', r'〔整理者注：\1〕', text, flags=re.S)
    text = re.sub(r'<mark>(.*?)</mark>', r'\1', text, flags=re.S)
    return re.sub(r'\n{3,}', '\n\n', text).strip('\n')


def normalise_headings(body):
    ctx = {'appendix_reg': False, 'appendix_term': False}

    def level_for(title):
        if title.startswith('附录'):
            return 1
        if re.match(rf'^第[{CN}]+章', title):
            return 3 if ctx['appendix_reg'] else 1
        if re.match(rf'^第[{CN}]+节', title):
            return 2
        if re.match(rf'^[{CN}]+、', title):
            return 3
        if re.match(rf'^（[{CN}]+）', title):
            return 4
        if re.match(r'^\d+\.', title):
            return 5
        if re.match(r'^（\d+）', title):
            return 6
        if re.match(r'^\d+\s', title) and ctx['appendix_term']:
            return 3
        return None

    out = []
    for line in body.split('\n'):
        m = re.match(r'^(#{1,6})\s+(.*)$', line)
        if m:
            title = m.group(2).strip()
            if title.startswith('附录一'):
                ctx.update(appendix_term=True, appendix_reg=False)
            elif re.match(r'^附录[二三四五]', title):
                ctx.update(appendix_reg=True, appendix_term=False)
            elif title.startswith('附录六'):
                ctx.update(appendix_reg=False, appendix_term=False)
            lvl = level_for(title) or len(m.group(1))
            line = '#' * lvl + ' ' + title
        out.append(line)
    return '\n'.join(out)


# --------------------------------------------------------------------------- #
# minimal markdown -> html (used only when `markdown` is unavailable)
# --------------------------------------------------------------------------- #
def _inline(s):
    s = re.sub(r'&(?![a-zA-Z]+;|#\d+;)', '&amp;', s)
    s = re.sub(r'<(?=[\d\s])', '&lt;', s)
    s = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'<img src="\2" alt="\1"/>', s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', s)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    s = re.sub(r'<(br|hr|img)([^>]*?)\s*/?>', r'<\1\2/>', s)
    return s


def _pipe_table(lines, i):
    """Convert a GFM pipe table starting at lines[i] into HTML. Returns (html, next_i)."""
    def cells(row):
        return [c.strip() for c in row.strip().strip('|').split('|')]
    header = cells(lines[i])
    i += 2                                     # skip header + separator
    body = []
    while i < len(lines) and lines[i].strip().startswith('|'):
        body.append(cells(lines[i]))
        i += 1
    out = ['<table>', '<thead>', '<tr>' + ''.join(f'<th>{_inline(c)}</th>' for c in header) + '</tr>',
           '</thead>', '<tbody>']
    for row in body:
        out.append('<tr>' + ''.join(f'<td>{_inline(c)}</td>' for c in row) + '</tr>')
    out += ['</tbody>', '</table>']
    return '\n'.join(out), i


def md_to_html(text):
    try:
        import markdown
        return markdown.markdown(text, extensions=['tables', 'sane_lists'])
    except ImportError:
        pass

    lines = text.split('\n')
    out, para, raw = [], [], []
    list_tag = None
    i = 0

    def flush_para():
        if para:
            out.append('<p>' + _inline(' '.join(para).strip()) + '</p>')
            para.clear()

    def flush_raw():
        if raw:
            out.append('\n'.join(raw))
            raw.clear()

    def close_list():
        nonlocal list_tag
        if list_tag:
            out.append(f'</{list_tag}>')
            list_tag = None

    while i < len(lines):
        s = lines[i].rstrip()
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ''

        if raw:
            if not s.strip():
                flush_raw()
            else:
                raw.append(s)
            i += 1
            continue

        if not s.strip():
            flush_para(); close_list(); i += 1; continue

        # pipe table: header row + separator row
        if s.strip().startswith('|') and re.match(r'^\|[\s:|-]+\|$', nxt):
            flush_para(); close_list()
            html_tbl, i = _pipe_table(lines, i)
            out.append(html_tbl)
            continue

        m = re.match(r'^(#{1,6})\s+(.*)$', s)
        if m:
            flush_para(); close_list()
            n = len(m.group(1))
            out.append(f'<h{n}>{_inline(m.group(2).strip())}</h{n}>')
            i += 1
            continue

        if s.startswith('<'):
            flush_para(); close_list(); raw.append(s); i += 1; continue

        if s.startswith('>'):
            flush_para(); close_list()
            out.append('<blockquote><p>' + _inline(s.lstrip('> ').strip()) + '</p></blockquote>')
            i += 1
            continue

        if re.match(r'^-{3,}\s*$', s):
            flush_para(); close_list(); out.append('<hr/>'); i += 1; continue

        m = re.match(r'^[-*]\s+(.*)$', s)
        if m:
            flush_para()
            if list_tag != 'ul':
                close_list(); out.append('<ul>'); list_tag = 'ul'
            out.append('<li>' + _inline(m.group(1)) + '</li>')
            i += 1
            continue

        m = re.match(r'^\d+\.\s+(.*)$', s)
        if m:
            flush_para()
            if list_tag != 'ol':
                close_list(); out.append('<ol>'); list_tag = 'ol'
            out.append('<li>' + _inline(m.group(1)) + '</li>')
            i += 1
            continue

        para.append(s)
        i += 1

    flush_para(); close_list(); flush_raw()
    return '\n'.join(out)


def to_xhtml(title, inner):
    inner = re.sub(r'<(br|hr|img)([^>]*?)\s*/?>', r'<\1\2/>', inner)
    inner = re.sub(r'<img((?:(?!alt=)[^>])*?)/>', r'<img\1 alt="图"/>', inner)
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh-CN" lang="zh-CN">\n'
            f'<head><meta charset="utf-8"/><title>{html.escape(title)}</title>'
            '<link rel="stylesheet" type="text/css" href="../style.css"/></head>\n'
            f'<body>{inner}</body></html>')


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('transcript', help='folder with part_*.md (sorted by name)')
    ap.add_argument('--title', required=True)
    ap.add_argument('--author', default='')
    ap.add_argument('--out', default='./dist')
    ap.add_argument('--subtitle', default='')
    ap.add_argument('--no-epub', action='store_true')
    ap.add_argument('--no-toc-page', action='store_true')
    args = ap.parse_args()

    files = sorted(f for f in os.listdir(args.transcript) if f.endswith('.md'))
    if not files:
        sys.exit(f'no .md files in {args.transcript}')
    body = clean('\n\n'.join(open(os.path.join(args.transcript, f), encoding='utf-8').read()
                             for f in files))
    body = normalise_headings(body)
    os.makedirs(args.out, exist_ok=True)

    # ---- markdown ----
    toc = [(len(m.group(1)), m.group(2).strip())
           for m in re.finditer(r'^(#{1,2})\s+(.*)$', body, re.M)]
    head = [f'**{args.title}**', '']
    if args.subtitle:
        head += [args.subtitle, '']
    if args.author:
        head += [args.author, '']
    toc_md = []
    if not args.no_toc_page:
        toc_md = ['# 目 录', ''] + [('' if l == 1 else '　　') + t for l, t in toc] + ['']
    book_md = '\n'.join(head) + '\n' + '\n'.join(toc_md) + ('\n---\n\n' if toc_md else '') + body + '\n'
    md_path = os.path.join(args.out, 'book.md')
    open(md_path, 'w', encoding='utf-8').write(book_md)

    # ---- html ----
    html_body = md_to_html(body)
    html_doc = ('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
                f'<title>{html.escape(args.title)}</title><style>{CSS}</style></head>'
                f'<body>{html_body}</body></html>')
    open(os.path.join(args.out, 'book.html'), 'w', encoding='utf-8').write(html_doc)

    stats = {'chars': len(re.sub(r'\s', '', body)),
             'tables': body.count('<table>'),
             'headings': len(toc)}
    print(f"book.md  {stats['chars']} chars, {stats['tables']} tables, {stats['headings']} top-level headings")

    if args.no_epub:
        return 0

    # ---- epub ----
    sections, cur_title, cur = [], '封面', []
    for line in body.split('\n'):
        if re.match(r'^#\s', line):
            if cur:
                sections.append((cur_title, '\n'.join(cur)))
            cur_title, cur = re.sub(r'^#\s+', '', line).strip(), [line]
        else:
            cur.append(line)
    if cur:
        sections.append((cur_title, '\n'.join(cur)))

    esc = lambda s: html.escape(s, quote=False)
    files_out, nav = [], []
    files_out.append(('text/cover.xhtml', to_xhtml(
        '书名页', f'<div class="cover"><h1 class="booktitle">{esc(args.title)}</h1>'
                  f'<p class="booksub">{esc(args.author)}</p></div>')))
    nav.append(('text/cover.xhtml', '书名页', []))

    for i, (title, mdtext) in enumerate(sections, 1):
        inner = md_to_html(mdtext)
        subs = []

        def add_id(m, i=i, subs=subs):
            subs.append((f'h{i:02d}_{len(subs) + 1:02d}', re.sub(r'<[^>]+>', '', m.group(1)).strip()))
            return f'<h2 id="{subs[-1][0]}">{m.group(1)}</h2>'

        inner = re.sub(r'<h2>(.*?)</h2>', add_id, inner, flags=re.S)
        inner = inner.replace('src="images/', 'src="../images/').replace('src="./images/', 'src="../images/')
        name = f'text/s{i:02d}.xhtml'
        files_out.append((name, to_xhtml(title, inner)))
        nav.append((name, title, subs))

    uid = 'urn:uuid:' + str(uuid.uuid5(uuid.NAMESPACE_URL, args.title + args.author))
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    nav_li = []
    for name, t, subs in nav:
        if subs:
            kids = ''.join(f'<li><a href="{name}#{hid}">{esc(st)}</a></li>' for hid, st in subs)
            nav_li.append(f'<li><a href="{name}">{esc(t)}</a><ol>{kids}</ol></li>')
        else:
            nav_li.append(f'<li><a href="{name}">{esc(t)}</a></li>')
    nav_xhtml = ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
                 '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"'
                 ' xml:lang="zh-CN" lang="zh-CN"><head><meta charset="utf-8"/><title>目录</title>'
                 '<link rel="stylesheet" type="text/css" href="style.css"/></head>'
                 '<body><nav epub:type="toc" id="toc"><h1>目录</h1><ol>'
                 + ''.join(nav_li) + '</ol></nav></body></html>')

    img_dir = os.path.join(os.path.dirname(os.path.abspath(args.transcript)), 'images')
    images = sorted(f for f in os.listdir(img_dir)
                    if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))
                    and '_test' not in f.lower()) if os.path.isdir(img_dir) else []

    manifest = '\n'.join(f'<item id="s{i}" href="{n}" media-type="application/xhtml+xml"/>'
                         for i, (n, _) in enumerate(files_out, 1))
    if images:
        manifest += '\n' + '\n'.join(f'<item id="img{i}" href="images/{f}" media-type="image/jpeg"/>'
                                     for i, f in enumerate(images, 1))
    spine = '\n'.join(f'<itemref idref="s{i}"/>' for i in range(1, len(files_out) + 1))

    po, ncx_items = 1, []
    for i, (name, t, subs) in enumerate(nav, 1):
        po += 1
        if subs:
            kids = ''.join(f'<navPoint id="np{i}_{k}" playOrder="{po + k}"><navLabel><text>{esc(st)}</text>'
                           f'</navLabel><content src="{name}#{hid}"/></navPoint>'
                           for k, (hid, st) in enumerate(subs, 1))
            ncx_items.append(f'<navPoint id="np{i}" playOrder="{po}"><navLabel><text>{esc(t)}</text></navLabel>'
                             f'<content src="{name}"/>{kids}</navPoint>')
            po += len(subs)
        else:
            ncx_items.append(f'<navPoint id="np{i}" playOrder="{po}"><navLabel><text>{esc(t)}</text></navLabel>'
                             f'<content src="{name}"/></navPoint>')

    ncx = ('<?xml version="1.0" encoding="utf-8"?>\n'
           '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
           f'<head><meta name="dtb:uid" content="{uid}"/><meta name="dtb:depth" content="2"/>'
           '<meta name="dtb:totalPageCount" content="0"/><meta name="dtb:maxPageNumber" content="0"/></head>'
           f'<docTitle><text>{esc(args.title)}</text></docTitle><navMap>'
           + ''.join(ncx_items) + '</navMap></ncx>')

    opf = f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="bookid">{uid}</dc:identifier>
<dc:title>{esc(args.title)}</dc:title>
<dc:creator>{esc(args.author or '佚名')}</dc:creator>
<dc:language>zh-CN</dc:language>
<meta property="dcterms:modified">{now}</meta>
</metadata>
<manifest>
<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
<item id="css" href="style.css" media-type="text/css"/>
<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
{manifest}
</manifest>
<spine toc="ncx">
{spine}
</spine>
</package>'''

    container = ('<?xml version="1.0" encoding="utf-8"?>\n'
                 '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                 '<rootfiles><rootfile full-path="OEBPS/content.opf" '
                 'media-type="application/oebps-package+xml"/></rootfiles></container>')

    safe = re.sub(r'[\\/:*?"<>|]', '_', args.title) or 'book'
    epub_path = os.path.join(args.out, f'{safe}.epub')
    with zipfile.ZipFile(epub_path, 'w') as z:
        z.writestr(zipfile.ZipInfo('mimetype'), 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        z.writestr('META-INF/container.xml', container, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr('OEBPS/content.opf', opf, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr('OEBPS/nav.xhtml', nav_xhtml, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr('OEBPS/toc.ncx', ncx, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr('OEBPS/style.css', CSS, compress_type=zipfile.ZIP_DEFLATED)
        for name, content in files_out:
            z.writestr('OEBPS/' + name, content, compress_type=zipfile.ZIP_DEFLATED)
        for f in images:
            z.write(os.path.join(img_dir, f), 'OEBPS/images/' + f, compress_type=zipfile.ZIP_DEFLATED)

    print(f'epub     {epub_path}  {os.path.getsize(epub_path) / 1024:.1f} KB, '
          f'{len(files_out)} sections, {len(images)} images')
    print('verify   python qc_book.py "%s" --epub' % epub_path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
