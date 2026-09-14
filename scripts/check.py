#!/usr/bin/env python3
"""Check built pages for broken local references and required metadata."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote
import zipfile
import json

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'

class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.links = []
        self.canonical = ''
        self.title = False
        self.description = False
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            assert a['id'] not in self.ids, 'Duplicate ID: ' + a['id']
            self.ids.add(a['id'])
        if tag == 'title': self.title = True
        if tag == 'meta' and a.get('name') == 'description': self.description = bool(a.get('content'))
        if tag == 'link' and a.get('rel') == 'canonical': self.canonical = a['href']
        for key in ('href', 'src'):
            if key in a: self.links.append(a[key])

pages = {}
for path in DIST.rglob('*.html'):
    page = Page()
    page.feed(path.read_text())
    if path.name == 'social-card.html': continue
    assert page.title and page.description and page.canonical, path
    pages[path.resolve()] = page
expected_pages = 6 + len(json.loads((ROOT/'content/cases.json').read_text()))
assert len(pages) == expected_pages, f'Expected {expected_pages} pages, got {len(pages)}'
homepage = pages[(DIST/'index.html').resolve()]
base = homepage.canonical
for path, page in pages.items():
    for link in page.links:
        if link.startswith(base): link = './' + link[len(base):]; target_base = DIST
        else: target_base = path.parent
        u = urlsplit(link)
        if u.scheme or u.netloc: continue
        target = (target_base / unquote(u.path)).resolve() if u.path else path
        assert target.is_relative_to(DIST.resolve()), (path, link)
        if target.is_dir(): target /= 'index.html'
        assert target.is_file(), (path, link, target)
        if u.fragment and target in pages:
            assert unquote(u.fragment) in pages[target].ids, (path, link)
assert (DIST/'assets/social-card.png').is_file()
with zipfile.ZipFile(DIST/'project-source.zip') as z:
    names=z.namelist()
    assert any(n.endswith('/LICENSE') for n in names)
    assert any(n.endswith('/.github/workflows/pages.yml') for n in names)
    assert all('/.env' not in n and '/.git/' not in n and '/dist/' not in n for n in names)
print(f'Checked {len(pages)} pages, local links, anchors, metadata and source archive.')

