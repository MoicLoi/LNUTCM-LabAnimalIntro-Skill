#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prepare a page photo for reading: rotate, grayscale, contrast, crop, split.

Requires Pillow (`pip install pillow`). Everything else in this skill is stdlib-only.

Examples
--------
    # a landscape page photographed sideways
    python prep_page.py p42.jpg --rotate 90 --out audit/p42.png

    # low-contrast grey print
    python prep_page.py p42.jpg --rotate 90 --gray --contrast 1.5 --sharpen 1.4 --out audit/p42.png

    # zoom one disputed line (fractions or pixels)
    python prep_page.py p42.jpg --crop 0.10,0.34,0.72,0.40 --scale 2.4 --out audit/p42_line.png

    # try both rotations and keep the one that reads correctly
    python prep_page.py p42.jpg --rotate both --outdir audit/
"""
import argparse, os, sys

try:
    from PIL import Image, ImageEnhance
except ImportError:
    sys.exit('Pillow is required: pip install pillow')


def parse_box(text, w, h):
    parts = [float(x) for x in text.replace(' ', '').split(',')]
    if len(parts) != 4:
        raise ValueError('--crop needs 4 values: left,top,right,bottom')
    if max(parts) <= 1.0:                       # fractions
        l, t, r, b = (parts[0] * w, parts[1] * h, parts[2] * w, parts[3] * h)
    else:                                        # pixels
        l, t, r, b = parts
    return int(l), int(t), int(r), int(b)


def process(src, angle, args, suffix=''):
    im = Image.open(src)
    if angle:
        im = im.rotate(angle, expand=True)
    if args.crop:
        im = im.crop(parse_box(args.crop, *im.size))
    if args.gray:
        im = im.convert('L')
    if args.contrast != 1.0:
        im = ImageEnhance.Contrast(im).enhance(args.contrast)
    if args.sharpen != 1.0:
        im = ImageEnhance.Sharpness(im).enhance(args.sharpen)
    if args.scale != 1.0:
        im = im.resize((int(im.width * args.scale), int(im.height * args.scale)), Image.LANCZOS)
    if args.max_width and im.width > args.max_width:
        im = im.resize((args.max_width, int(im.height * args.max_width / im.width)), Image.LANCZOS)

    stem = os.path.splitext(os.path.basename(src))[0]
    if args.outdir:
        os.makedirs(args.outdir, exist_ok=True)
        ext = os.path.splitext(args.out)[1] or '.png' if args.out else '.png'
        out = os.path.join(args.outdir, f'{stem}{suffix}{ext}')
    else:
        out = args.out or f'{stem}{suffix}_prep.png'
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    if out.lower().endswith(('.jpg', '.jpeg')):
        if im.mode not in ('RGB', 'L'):
            im = im.convert('RGB')
        im.save(out, quality=92, optimize=True)
    else:
        im.save(out)
    return out, im.size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('--rotate', default='0',
                    help='degrees counter-clockwise: 90, -90, 180, or "both"')
    ap.add_argument('--crop', help='left,top,right,bottom (fractions <=1 or pixels)')
    ap.add_argument('--gray', action='store_true')
    ap.add_argument('--contrast', type=float, default=1.0)
    ap.add_argument('--sharpen', type=float, default=1.0)
    ap.add_argument('--scale', type=float, default=1.0)
    ap.add_argument('--max-width', type=int, default=0)
    ap.add_argument('--out')
    ap.add_argument('--outdir')
    args = ap.parse_args()

    if args.rotate == 'both':
        if not args.outdir:
            sys.exit('--rotate both needs --outdir')
        for ang, suffix in ((90, '_ccw'), (-90, '_cw')):
            out, size = process(args.src, ang, args, suffix)
            print(f'{out}  {size[0]}x{size[1]}')
        print('read both, keep the upright one, delete the other')
    else:
        out, size = process(args.src, int(args.rotate), args)
        print(f'{out}  {size[0]}x{size[1]}')


if __name__ == '__main__':
    main()
