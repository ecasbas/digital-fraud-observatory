#!/usr/bin/env python3
"""Build a standalone static site. Python standard library; no application APIs."""
import argparse
from datetime import date
from html import escape
import json
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / 'site.json').read_text())
CASES = json.loads((ROOT / 'content/cases.json').read_text())
OUT = ROOT / 'dist'
E = lambda value: escape(str(value), quote=True)


def validate():
    ids, slugs = set(), set()
    assert CONFIG['name'] and CONFIG['contact_email']
    assert urlsplit(CONFIG['base_url']).scheme == 'https'
    if CONFIG['repository']:
        assert re.fullmatch(r'https://github.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', CONFIG['repository'])
    for c in CASES:
        assert re.fullmatch(r'SA-\d{3}', c['id']) and c['id'] not in ids
        assert re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', c['slug']) and c['slug'] not in slugs
        ids.add(c['id']); slugs.add(c['slug'])
        assert c['kind'] in ('capture', 'reconstruction', 'incident') and c['sources']
        assert c['audience']
        date.fromisoformat(c['checked_at'])
        if c['analysis_date']: date.fromisoformat(c['analysis_date'])
        for s in c['sources']:
            u = urlsplit(s['url'])
            assert u.scheme == 'https' and u.netloc and not u.username
            assert s['name'] and s['role']
        if c['kind'] == 'capture':
            assert Path(c['image']).name == c['image']
            assert (ROOT / 'assets/captures' / c['image']).is_file(), c['image']
        elif c['kind'] == 'reconstruction':
            assert c['message'] and 'invented' in c['limits'].lower()


def icon(name='arrow', size=17):
    paths = {
        'arrow': '<path d="M4 12h16m-6-6 6 6-6 6"/>',
        'external': '<path d="M14 4h6v6m0-6L10 14M20 14v6H4V4h6"/>',
        'search': '<circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/>',
        'evidence': '<path d="M7 3h10l4 4v14H3V3h4m5 5v8m-4-4h8"/>',
        'people': '<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3m2-16a3 3 0 0 1 0 6m2 10v-4a5 5 0 0 0-3-4"/>',
        'refresh': '<path d="M20 7v5h-5M4 17v-5h5m10-3a8 8 0 0 0-14-3m0 9a8 8 0 0 0 14 3"/>',
        'menu': '<path d="M4 6h16M4 12h16M4 18h16"/>',
        'copy': '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M4 16V4h12"/>'
    }
    return f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{paths[name]}</svg>'


def fmt(value):
    return date.fromisoformat(value).strftime('%d %b %Y').lstrip('0')


def page_url(route=''):
    return CONFIG['base_url'].rstrip('/') + '/' + route


def write(path, text):
    target = OUT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding='utf-8')


def frame(title, body, prefix='./', route='', active='', description=None):
    desc = description or CONFIG['description']
    canonical = page_url(route)
    brand = '<span class="brand-name">Digital Fraud<span>Observatory</span></span>' if CONFIG['name'] == 'Digital Fraud Observatory' else E(CONFIG['name'])
    nav = [('Library', '#library' if not route else prefix + '#library', 'library'), ('The AI era', prefix + 'ai-era/', 'ai'), ('Our approach', prefix + 'about/', 'about')]
    nav_html = ''.join(f'<a href="{E(link)}"'+(' aria-current="page"' if key == active else '')+f'>{E(label)}</a>' for label, link, key in nav)
    project_link = E(CONFIG['repository']) if CONFIG['repository'] else prefix + 'project-source.zip'
    project_label = 'GitHub' if CONFIG['repository'] else 'Project files'
    schema = {'@context': 'https://schema.org', '@type': 'WebSite' if not route else 'WebPage', 'name': title, 'url': canonical, 'description': desc}
    schema_text = json.dumps(schema).replace('<', '\\u003c')
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><meta name="theme-color" content="#102528"><meta name="referrer" content="strict-origin-when-cross-origin">
<title>{E(title)} · {E(CONFIG['name'])}</title><meta name="description" content="{E(desc)}"><meta name="robots" content="{'index,follow' if CONFIG['indexable'] else 'noindex,follow'}"><link rel="canonical" href="{E(canonical)}">
<meta property="og:type" content="website"><meta property="og:title" content="{E(title)} · {E(CONFIG['name'])}"><meta property="og:description" content="{E(desc)}"><meta property="og:url" content="{E(canonical)}"><meta property="og:image" content="{E(page_url('assets/social-card.png'))}"><meta property="og:site_name" content="{E(CONFIG['name'])}"><meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{prefix}assets/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="{prefix}assets/site.css?v=3"><script defer src="{prefix}assets/site.js?v=3"></script><script type="application/ld+json">{schema_text}</script></head>
<body><a class="skip-link" href="#main">Skip to content</a><header class="site-header"><div class="wrap header-inner"><a class="wordmark" href="{prefix}" aria-label="{E(CONFIG['name'])} home"><img src="{prefix}assets/favicon.svg" width="35" height="35" alt="">{brand}</a><nav class="desktop-nav" aria-label="Main">{nav_html}</nav><a class="btn header-action" href="{prefix}contribute/">Contribute {icon(size=15)}</a><button class="menu-toggle" aria-expanded="false" aria-controls="mobile-nav" aria-label="Open navigation">{icon('menu',20)}</button></div><nav class="wrap mobile-nav" id="mobile-nav" aria-label="Mobile" hidden>{nav_html}<a href="{prefix}contribute/">Contribute an example</a></nav></header>
<main id="main">{body}</main>
<footer class="site-footer"><div class="wrap"><div class="footer-main"><div class="footer-brand"><a class="wordmark" href="{prefix}"><img src="{prefix}assets/favicon.svg" alt="" width="31" height="31">{brand}</a><p>{E(CONFIG['tagline'])}<br>Initiated by <a href="{E(CONFIG['founder_url'])}">{E(CONFIG['founder_name'])}</a>. Built to welcome everyone.</p></div><nav class="footer-links" aria-label="Footer"><a href="{prefix}about/">About</a><a href="{prefix}contribute/">Contribute</a><a href="{project_link}">{project_label}</a><a href="{prefix}privacy/">Privacy & reuse</a></nav></div><div class="footer-bottom"><span>Evidence is attributed. Claims can be challenged.</span><span>Original code: MIT · Editorial text: CC BY 4.0 · Screenshots retain their original rights.</span></div></div></footer></body></html>'''


def card(c, prefix='./'):
    url = prefix + 'cases/' + c['slug'] + '/'
    labels = {'capture': 'Actual website capture', 'reconstruction': 'Educational reconstruction', 'incident': 'Documented incident'}
    label = labels[c['kind']]
    if c['kind'] == 'capture':
        image = f'<img class="case-image" src="{prefix}assets/captures/{E(c["image"])}" alt="{E(c["image_alt"])}" width="1366" height="768" loading="lazy" decoding="async">'
    elif c['kind'] == 'reconstruction':
        image = '<div class="message-thumb"><div class="mini-message"><span class="mini-label">SUPPOSED TASK SUPPORT</span>Your balance is <strong>€184.</strong><br>To withdraw, <mark>deposit €60 first.</mark></div></div>'
    else:
        image = f'<div class="incident-thumb"><div class="incident-node">REQUEST</div><div class="incident-line"></div><div class="incident-node incident-alert">VERIFY</div><div class="incident-line"></div><div class="incident-node">DISCLOSE</div><p>{E(c["claim"])} → {E(c["counterclaim"])}</p></div>'
    sources = ' + '.join(dict.fromkeys(s['short'] for s in c['sources']))
    search = ' '.join([c['title'], c['category'], c['technique'], c['audience'], c['summary'], sources]).lower()
    return f'''<article class="case-card" data-category="{E(c['category'])}" data-search="{E(search)}"><a class="case-image-link" href="{url}" tabindex="-1" aria-hidden="true">{image}<span class="image-label">{label}</span></a><div class="case-body"><div class="card-meta"><span class="category-label">{E(c['category'])} / {E(c['technique'])}</span><span class="case-number">{E(c['id'])}</span></div><h3><a href="{url}">{E(c['short_title'])}</a></h3><p>{E(c['summary'])}</p><p class="audience-line"><strong>Audience:</strong> {E(c['audience'])}</p><div class="card-bottom"><span class="source-credit">Source: {E(sources)}</span><a href="{url}" aria-label="Read {E(c['short_title'])}">Read case {icon(size=15)}</a></div></div></article>'''


def home():
    by_slug = {c['slug']: c for c in CASES}
    selections = [
        ('celebrity-casino', 'A famous face', 'A familiar face. An unverified endorsement.', 'The source flags celebrity impersonation and unverified partnership claims.'),
        ('logistics-company-facade', 'A global carrier', 'A cargo port. But who is the carrier?', 'A polished logistics page. The source reports an operator whose legal identity could not be verified.'),
        ('insurance-clone', 'Insurance clone', 'It says regulated. The regulator says clone.', 'The FCA identifies this insurance website as a clone of an authorised firm.')
    ]
    featured = by_slug[selections[0][0]]
    choices = ''
    for index, (slug, label, headline, summary) in enumerate(selections):
        c = by_slug[slug]
        choices += f'''<button class="showcase-choice" type="button" data-showcase data-image="assets/captures/{E(c['image'])}" data-alt="{E(c['image_alt'])}" data-link="cases/{slug}/" data-headline="{E(headline)}" data-summary="{E(summary)}" data-assessment="{E(c['assessment'])} · {E(c['assessment_source'])}" aria-pressed="{str(index == 0).lower()}" aria-controls="showcase-panel" aria-label="View {E(label.lower())} example"><span class="choice-image"><img src="assets/captures/{E(c['image'])}" width="1366" height="768" alt="" loading="eager"></span><span class="choice-label"><span class="choice-number">0{index+1}</span>{E(label)}</span></button>'''
    showcase = f'''<div class="evidence-showcase"><div class="showcase-topline"><span class="eyebrow"><span class="dot"></span>Captured websites</span><span>Follow the evidence ↓</span></div><div class="showcase-panel" id="showcase-panel"><a class="showcase-image-link" id="showcase-image-link" href="cases/{featured['slug']}/" aria-label="Read the featured evidence"><img id="showcase-image" src="assets/captures/{E(featured['image'])}" alt="{E(featured['image_alt'])}" width="1366" height="768" fetchpriority="high"><span class="showcase-image-hint">Explore this case {icon(size=14)}</span></a><div class="showcase-caption" aria-live="polite" aria-atomic="true"><div class="showcase-assessment" id="showcase-assessment">{E(featured['assessment'])} · {E(featured['assessment_source'])}</div><h2 id="showcase-headline">{E(selections[0][2])}</h2><p id="showcase-summary">{E(selections[0][3])}</p><a class="showcase-case-link" id="showcase-case-link" href="cases/{featured['slug']}/">Read the case {icon(size=14)}</a></div></div><div class="showcase-choices" hidden role="group" aria-label="Choose a real example">{choices}</div><p class="showcase-note">Archived captures. The claims shown belong to the captured websites.</p></div>'''
    filters = ''.join(f'<button class="filter" type="button" data-filter="{E(cat)}" aria-pressed="{str(cat == "All").lower()}">{E(cat)}</button>' for cat in ['All'] + list(dict.fromkeys(c['category'] for c in CASES)))
    body = f'''<section class="hero"><div class="wrap hero-grid"><div class="hero-copy"><div class="eyebrow"><span class="dot"></span>An open library for the AI era</div><h1>Fraud looks<br>convincing.<br><em>Look closer.</em></h1><p>Familiar faces. Impressive companies. Official-looking badges. Explore real examples and learn what to check.</p><div class="hero-actions"><a class="btn" href="#library">Explore the cases {icon()}</a><a class="btn btn-ghost" href="contribute/">Share an example {icon()}</a></div><div class="hero-note">Open to everyone. Built from credited evidence.</div></div>{showcase}</div></section>
<div class="source-strip"><div class="wrap source-row"><p class="source-label">Evidence in this collection comes from</p><div class="source-list"><span>desenmascara.me</span><span>FCA</span><span>FTC</span></div><span class="source-caption">Cited sources. Not sponsors or endorsements.</span></div></div>
<section class="section wrap" id="library"><div class="section-top"><div><div class="eyebrow">The open collection</div><h2>See the pattern.<br>Keep the lesson.</h2></div><p>Explore actual website captures, documented incidents and clearly labeled reconstructions. Every case links back to its evidence.</p></div><div class="library-toolbar"><div class="filters" role="group" aria-label="Filter by category">{filters}</div><label class="search-box">{icon('search',17)}<span class="sr-only">Search cases</span><input id="case-search" type="search" placeholder="Search cases, sources, patterns…" autocomplete="off"></label></div><div class="library-meta"><span id="result-count" role="status">{len(CASES)} cases in the collection</span><span>{sum(c['kind'] == 'capture' for c in CASES)} real captures · {sum(c['kind'] == 'reconstruction' for c in CASES)} reconstruction · {sum(c['kind'] == 'incident' for c in CASES)} incident</span></div><div class="case-grid" id="case-grid">{''.join(card(c) for c in CASES)}</div><div class="empty-state" id="no-results" hidden><h3>No cases match yet.</h3><p class="muted">Try another term, or help us document a new example.</p><button class="btn btn-outline" type="button" id="reset-search">Clear filters</button></div><noscript><p class="no-js-message">All cases are shown. Enable JavaScript to use search and filters.</p></noscript></section>
<section class="principles"><div class="wrap section"><div class="section-top"><div><div class="eyebrow">Built on evidence, open to correction</div><h2>Useful because<br>you can check it.</h2></div><p>AI can change the voice, the face and the message. The need for evidence stays the same.</p></div><div class="principle-grid"><div><div class="principle-icon">{icon('evidence',22)}</div><h3>Show the source.</h3><p>Follow the original report. See what was captured, what a source concluded and what remains uncertain.</p></div><div><div class="principle-icon">{icon('people',22)}</div><h3>Make room for everyone.</h3><p>Researchers, security vendors, educators and everyday people can contribute. Credit stays with the source.</p></div><div><div class="principle-icon">{icon('refresh',22)}</div><h3>Keep learning.</h3><p>Improve an explanation, add evidence or challenge a claim. AI involvement is stated only when the evidence supports it.</p></div></div><p style="margin-top:30px"><a href="ai-era/" class="text-button">What changes in the AI era {icon(size=15)}</a></p></div></section>
<section class="section wrap"><div class="contribute-callout"><div><div class="eyebrow"><span class="dot"></span>A small contribution. A shared defense.</div><h2>You found a pattern.<br>Help someone else see it.</h2><p>A public report and a few words are enough to start. No code, technical format or screenshot required.</p></div><div><div class="contribution-steps"><div class="contribution-step"><span class="step-num">01</span><div class="step-copy"><strong>Link to a public report.</strong><span>Any credible source. Any vendor.</span></div></div><div class="contribution-step"><span class="step-num">02</span><div class="step-copy"><strong>Explain the lesson.</strong><span>What should someone notice or verify?</span></div></div><div class="contribution-step"><span class="step-num">03</span><div class="step-copy"><strong>Send it for review.</strong><span>We check the evidence before adding a case.</span></div></div></div><a class="btn" href="contribute/">Contribute an example {icon()}</a></div></div></section>'''
    write('index.html', frame('Real examples. Learn to spot online fraud.', body, active='library'))


def case_page(c):
    prefix = '../../'
    kind = {'capture': 'Actual website capture', 'reconstruction': 'Educational reconstruction', 'incident': 'Documented incident'}[c['kind']]
    lead = f'''<div class="wrap page-header"><div class="breadcrumb"><a href="{prefix}#library">Collection</a><span>/</span><span>{E(c['category'])}</span><span>/</span><span>{E(c['id'])}</span></div><div class="tags"><span class="tag">{E(c['technique'])}</span><span class="tag">{kind}</span></div><h1>{E(c['title'])}</h1><p class="lede">{E(c['summary'])}</p></div>'''
    if c['kind'] == 'capture':
        figure = f'''<figure class="evidence-figure"><div class="evidence-frame"><button type="button" data-zoom aria-label="Enlarge the archived screenshot"><img src="{prefix}assets/captures/{E(c['image'])}" alt="{E(c['image_alt'])}" width="1366" height="768" fetchpriority="high"></button></div><figcaption class="figure-caption"><span>Unaltered historical capture. Website claims belong to the captured page.</span><a href="{prefix}assets/captures/{E(c['image'])}" target="_blank" rel="noopener">Full image {icon('external',12)}</a></figcaption></figure><dialog id="capture-dialog" aria-label="Archived website screenshot"><div class="dialog-top"><span>Original capture · {E(c['id'])}</span><button type="button" data-close-dialog>Close ✕</button></div><img class="zoom-image" src="{prefix}assets/captures/{E(c['image'])}" alt="{E(c['image_alt'])}" width="1366" height="768" loading="lazy"></dialog>'''
    elif c['kind'] == 'reconstruction':
        figure = f'''<figure class="evidence-figure"><div class="message-full"><div class="small">FICTIONAL RECONSTRUCTION / SUPPOSED TASK SUPPORT</div><blockquote>{E(c['message'])}</blockquote></div><figcaption class="figure-caption">Illustrative wording and amounts. No actual person or business is depicted.</figcaption></figure>'''
    else:
        figure = f'''<figure class="evidence-figure"><div class="incident-full"><div class="incident-heading"><div class="eyebrow">Incident pathway</div><h2>How a trusted request can become a data disclosure</h2><p>Each step can look routine. The control point is independent verification before sensitive records are released.</p></div><div class="incident-steps"><div class="incident-step"><span>1</span><div><small>REQUEST</small><strong>Official-looking request</strong><p>The request appears to come through a legitimate government channel.</p></div></div><div class="incident-step incident-warning"><span>2</span><div><small>VERIFY</small><strong>Verify the requester</strong><p>Confirm identity, legal authority and scope through an independent route.</p></div></div><div class="incident-step"><span>3</span><div><small>DISCLOSE</small><strong>Disclosure risk</strong><p>Sensitive customer records can leave through a normal compliance process.</p></div></div></div></div><figcaption class="figure-caption">Documented public incident. No live system or private customer record is embedded here.</figcaption></figure>'''
    observed = ''.join(f'<li>{E(t)}</li>' for t in c['observations'])
    sources = ''.join(f'''<div class="source-item"><strong>{E(s['name'])}</strong><p>{E(s['role'])}</p><a href="{E(s['url'])}" target="_blank" rel="noopener">Read original source {icon('external',13)}</a></div>''' for s in c['sources'])
    source_dates = f'<div><dt>Analysis date</dt><dd>{fmt(c["analysis_date"])}</dd></div>' if c['analysis_date'] else ''
    rail = f'''<aside class="source-panel" aria-label="Evidence and provenance"><h2>Follow the evidence.</h2>{sources}<dl class="record-info"><div><dt>Source assessment</dt><dd>{E(c['assessment'])}</dd><dd class="small muted">{E(c['assessment_source'])}</dd></div>{source_dates}<div><dt>Sources last checked</dt><dd>{fmt(c['checked_at'])}</dd></div><div><dt>Audience / at-risk group</dt><dd>{E(c['audience'])}</dd></div><div><dt>Subject</dt><dd>{E(c['subject'])}</dd></div></dl><a class="btn btn-dark" href="{prefix}contribute/?case={c['id']}">Improve this case {icon(size=14)}</a><a class="btn btn-outline" href="{prefix}downloads/{c['slug']}.md" download>Download case</a><p class="source-note">Source assessments stay attributed. Scores from different providers are not directly comparable.</p></aside>'''
    related = ''.join(card(other,prefix) for other in [x for x in CASES if x != c][:2])
    body = lead + f'''<div class="wrap detail-layout"><div>{figure}<div class="claim-comparison"><div><div class="eyebrow">What the example presents</div><strong>{E(c['claim'])}</strong></div><div><div class="eyebrow">What to examine</div><strong>{E(c['counterclaim'])}</strong></div></div><section class="editorial-section"><h2>Audience / at-risk group</h2><p>{E(c['audience'])}</p></section><section class="editorial-section"><h2>What you can notice</h2><ul>{observed}</ul></section><div class="takeaway"><h2>The takeaway</h2><p>{E(c['lesson'])}</p></div><section class="editorial-section"><h2>What the source reports</h2><p>{E(c['source_summary'])}</p></section><section class="editorial-section"><h2>What this evidence cannot tell us</h2><p>{E(c['limits'])}</p></section><div class="detail-actions"><button class="text-button" type="button" data-share>{icon('copy',15)} Copy case link</button><a class="text-button" href="{prefix}contribute/?case={c['id']}">Suggest a correction</a></div><p class="status" id="share-status" role="status"></p></div>{rail}</div><section class="wrap related"><div class="eyebrow" style="margin-bottom:12px">Keep exploring</div><h2>Different tactics. Useful lessons.</h2><div class="case-grid">{related}</div></section>'''
    write(f'cases/{c["slug"]}/index.html', frame(c['short_title'], body, prefix, f'cases/{c["slug"]}/', description=c['summary']))
    lines = [f'# {c["title"]}', '', f'ID: {c["id"]}', f'Type: {kind}', f'Audience / at-risk group: {c["audience"]}', f'Subject: {c["subject"]}', f'Sources checked: {c["checked_at"]}', '', '## Lesson', c['lesson'], '', '## Source findings', c['source_summary'], '', '## Limits', c['limits'], '', '## Sources']
    lines += [f'- [{s["name"]}]({s["url"]}) — {s["role"]}' for s in c['sources']]
    lines += ['', 'Original editorial text: CC BY 4.0. Third-party captures, source texts, names and logos retain their own rights.']
    write(f'downloads/{c["slug"]}.md', '\n'.join(lines) + '\n')


def contribute():
    repo = CONFIG['repository']
    github = f'<a class="btn btn-dark" id="github-submit" hidden>Continue on GitHub {icon("external",14)}</a>' if repo else ''
    body = f'''<div class="wrap page-header"><div class="breadcrumb"><a href="../">Home</a><span>/</span><span>Contribute</span></div><div class="eyebrow">Open to every source. Built one case at a time.</div><h1>One link.<br>One useful lesson.</h1><p class="lede">Help someone recognize a scam before it reaches them. Share a public report or improve an existing case.</p></div><div class="wrap form-layout"><div><form class="contribution-form" id="contribution-form" data-email="{E(CONFIG['contact_email'])}" data-repository="{E(repo)}" data-project="{E(CONFIG['name'])}"><p class="notice" id="correction-notice" hidden></p><div class="field"><label for="report-url">1. Public report link</label><input type="url" id="report-url" name="report" placeholder="https://your-source.org/research/report" required maxlength="1500" aria-describedby="report-help"><p class="field-help" id="report-help">Link to published evidence from any vendor, researcher or official source. Avoid live scam links.</p></div><div class="field"><label for="lesson">2. What should people learn?</label><textarea id="lesson" name="lesson" placeholder="What is the trick? What should someone notice or verify? A sentence or two is enough." required maxlength="1800" aria-describedby="lesson-help"></textarea><p class="field-help" id="lesson-help">For a correction, explain what is wrong and how your source supports the change.</p></div><details class="optional-fields"><summary>Add source and contributor credit (optional)</summary><div class="field"><label for="source-name">Source organization</label><input id="source-name" name="source_name" maxlength="100" placeholder="Defaults to the report’s website"></div><div class="field"><label for="credit">Your name or team</label><input id="credit" name="credit" maxlength="100" placeholder="Anonymous is fine"></div></details><button type="submit" class="btn btn-dark">Review contribution {icon()}</button><p class="field-help" style="margin-top:13px">Nothing is sent at this step. Leave out personal data, credentials and private messages.</p><p class="status" id="form-status" role="status"></p></form><section class="review-card" id="contribution-review" hidden aria-labelledby="review-title"><div class="eyebrow">Ready for your review</div><h2 id="review-title">Your contribution</h2><p id="review-lesson"></p><p class="review-source"><strong>Source:</strong> <a id="review-source" target="_blank" rel="noopener noreferrer"></a></p><p class="review-source" id="review-credit"></p><div class="review-actions">{github}<a class="btn btn-dark" id="email-submit">Open email to send {icon('external',14)}</a><button class="btn btn-outline" id="download-contribution" type="button">Download draft</button></div><p class="muted">Opening your email app does not send the message. Review it there, then send. Contributions are reviewed before appearing in the collection.</p><p class="muted">No email app? Download the draft and send it to <a href="mailto:{E(CONFIG['contact_email'])}">{E(CONFIG['contact_email'])}</a>.</p></section><noscript><p class="notice">Send a public report link and a short lesson to <a href="mailto:{E(CONFIG['contact_email'])}">{E(CONFIG['contact_email'])}</a>. The interactive form requires JavaScript.</p></noscript></div><aside class="form-aside"><div><div class="eyebrow">What makes a useful contribution?</div><h2>Evidence people<br>can follow.</h2><ul><li>A report with a clear source.</li><li>A specific, understandable lesson.</li><li>Context about what is still uncertain.</li></ul><p>Translations, corrections and legitimate counterexamples count too.</p><p>AI-assisted drafts are welcome when you check the source yourself. Do not present an invented example as a real incident.</p></div><div class="small-card"><h3>Bring your own source.</h3><p>Security vendors and independent researchers receive the same attribution. You do not need a Desenmascara report, account or API key.</p><p class="small">Publication follows evidence review, not a vote or a vendor’s reputation alone.</p><a class="text-button" href="../about/#review">How review works {icon(size=14)}</a></div></aside></div>'''
    write('contribute/index.html', frame('Contribute an example', body, '../', 'contribute/'))


def info_pages():
    name = E(CONFIG['name'])
    about = f'''<div class="wrap"><article class="article-shell"><div class="eyebrow">Our approach</div><h1>A public record<br>for the AI era.</h1><p>{name} is a public record of how deception appears online: the claims, patterns and evidence that help people recognize fraud before it reaches them.</p><section><h2>One project. Many sources.</h2><p>Initiated by <a href="{E(CONFIG['founder_url'])}">{E(CONFIG['founder_name'])}</a>, this project welcomes work from security vendors, researchers, regulators, educators and individuals. A source citation is not a partnership or endorsement. The collection contains {len(CASES)} documented examples, including public incidents and clearly labeled fictional reconstructions. It does not imply an established contributor network.</p></section><section><h2>What a case means</h2><p>Each case identifies its source, dates, evidence type and limitations. A provider’s risk assessment stays attributed to that provider. This site does not run live website scans, give a fresh safety verdict or certify a business.</p><p>A screenshot can show a claim. It cannot, on its own, prove stolen funds, a coordinated campaign or AI generation. We keep those distinctions visible.</p></section><section id="review"><h2>How review works</h2><ol><li>Check the public report and the origin of its evidence.</li><li>Separate visible facts, source assessments and editorial explanations.</li><li>Check for duplicate cases, private information and unsupported accusations.</li><li>Credit the source and contributor, then publish the approved case.</li></ol><p>These are editorial checks, not a promise of independent incident investigation. Reports from all vendors follow the same process. The project does not publish an accusation simply because it was submitted.</p></section><section><h2>Corrections belong in the record.</h2><p>Use “Improve this case” to supply a correction and supporting source. When a correction changes the meaning of a case, its evidence, status and checked date should be updated together. Withdrawn cases should explain the withdrawal instead of quietly losing their history.</p></section><section><h2>Built to be reused.</h2><p>The original site code is MIT licensed. Original editorial explanations are available under CC BY 4.0. Third-party screenshots, report text, names and logos keep their existing rights. Download a case or the project files to inspect the structure.</p><p><a href="../project-source.zip">Download the standalone project</a> · <a href="../data/cases.json">Download case metadata</a> · <a href="../assets/logo-ascii.txt">ASCII logo</a></p></section><div class="faq"><h2>A few practical questions</h2><details><summary>Can my company contribute its own research?</summary><p>Yes. Link to a public report and explain the lesson. Your company is credited as the source. Disclose your connection and include evidence rather than promotional copy.</p></details><details><summary>Does an AI-generated site mean it is a scam?</summary><p>No. AI can be used legitimately. We document deceptive behavior and state AI involvement only when the evidence supports it.</p></details><details><summary>Do I need to write code or use GitHub?</summary><p>No. The contribution page prepares an email draft from a report link and a short explanation. GitHub issue templates are also included in the project files.</p></details></div></article></div>'''
    write('about/index.html', frame('Our approach', about, '../', 'about/', active='about'))
    ai = '''<div class="wrap"><article class="article-shell"><div class="eyebrow">The AI era</div><h1>The voice can change.<br>Ask for evidence.</h1><p>AI can make a scam’s presentation more convincing. Familiar voices, fluent writing and polished imagery deserve the same independent checks as any other claim.</p><section><h2>Familiar voices, unfamiliar requests</h2><p>The FTC describes family-emergency scams using cloned voices. A recognizable voice is not enough to authenticate an urgent request. Reconnect with the person through a number you already trust.</p><p><a href="https://consumer.ftc.gov/articles/scammers-use-fake-emergencies-steal-your-money">Read the FTC’s guidance on fake emergencies ↗</a></p></section><section><h2>Manufactured authority</h2><p>The FBI describes criminals using generated images, documents and audio to support impersonation. Look for corroboration outside the message or website making the claim.</p></section><section><h2>More convincing messages, at greater scale</h2><p>The FBI also documents AI-assisted text, translations and fraudulent profiles. Good grammar and personal detail no longer make useful guarantees of legitimacy.</p><p><a href="https://www.ic3.gov/PSA/2024/PSA241203">Read the FBI’s advisory on generative AI and fraud ↗</a></p></section><div class="takeaway"><h2>Our focus</h2><p>Document the deception. Trace the evidence. Keep the lesson useful as the tools change.</p></div><section><h2>Be precise about AI.</h2><p>The cases currently in this collection do not establish AI generation. Their lessons about impersonation, payment requests and unverified authority remain relevant. A contribution about an AI-enabled incident should link to evidence of the AI involvement, not infer it from a polished design.</p></section><p><a class="btn btn-dark" href="../contribute/">Share a documented AI-related case →</a></p><p class="small muted" style="margin-top:25px">Source guidance checked 14 September 2026. This page describes documented patterns, not a prediction of every future attack.</p></article></div>'''
    write('ai-era/index.html', frame('Scams in the AI era', ai, '../', 'ai-era/', active='ai'))
    privacy = f'''<div class="wrap"><article class="article-shell"><div class="eyebrow">Privacy & reuse</div><h1>A small site.<br>A clear data boundary.</h1><p>This site is a public learning resource. You can browse its cases without registering.</p><section><h2>Browsing</h2><p>The site adds no analytics scripts, advertising trackers, cookies or browser storage. GitHub Pages and its network providers may process request metadata, including IP addresses, for delivery and security.</p></section><section><h2>Contributing</h2><p>The form prepares a draft in your browser. It does not upload your entry to a server. Choosing the email action opens your configured email application with the draft; you decide whether to send it. Email submissions go to <a href="mailto:{E(CONFIG['contact_email'])}">{E(CONFIG['contact_email'])}</a> for editorial review.</p><p>If you choose GitHub after a repository is connected, the draft opens on GitHub and an issue becomes public only when you submit it there. The recipient or platform may retain your submission and contact details. Do not include credentials, personal financial information or private victim messages.</p><p>Ask about a submission or request removal of personal information at the same contact address.</p></section><section><h2>Source links and screenshots</h2><p>Source links take you to other organizations’ websites, which have their own privacy practices. Captures included here are historical images. They are not live embeds of the suspected sites, and their buttons cannot be used to register or pay.</p></section><section><h2>Reuse and attribution</h2><p>Original code is MIT licensed. Original editorial text is licensed under <a href="https://creativecommons.org/licenses/by/4.0/">Creative Commons Attribution 4.0</a>. Credit the project and original sources and identify changes. Third-party screenshots, quoted claims, trademarks and underlying source content are excluded from these grants; their respective rights remain with their owners.</p><p>The project does not claim affiliation with or endorsement by the organizations it cites.</p></section><section><h2>Limits of the resource</h2><p>Case pages describe dated evidence and attributed assessments. They are not real-time guarantees, professional advice, or promises that an unlisted site is safe. Use original sources to check developments and corrections.</p></section><p class="small muted">Updated 14 September 2026.</p></article></div>'''
    write('privacy/index.html', frame('Privacy and reuse', privacy, '../', 'privacy/'))


def source_archive():
    allowed = ['site.json', 'content', 'assets', 'scripts', '.github', 'README.md', 'CONTRIBUTING.md', 'CODE_OF_CONDUCT.md', 'SECURITY.md', 'LICENSE', 'CONTENT-LICENSE.md', 'NOTICE.md', '.gitignore']
    with zipfile.ZipFile(OUT / 'project-source.zip', 'w', zipfile.ZIP_DEFLATED) as z:
        for item in allowed:
            p = ROOT / item
            if not p.exists(): continue
            files = [p] if p.is_file() else sorted(x for x in p.rglob('*') if x.is_file() and '__pycache__' not in x.parts)
            for f in files: z.write(f, str(Path('digital-fraud-observatory') / f.relative_to(ROOT)))


def build():
    validate()
    OUT.mkdir(exist_ok=True)
    shutil.copytree(ROOT / 'assets', OUT / 'assets', dirs_exist_ok=True)
    home()
    for c in CASES: case_page(c)
    contribute(); info_pages()
    write('data/cases.json', json.dumps(CASES, indent=2, ensure_ascii=False) + '\n')
    write('.nojekyll', '')
    routes = ['', 'contribute/', 'about/', 'ai-era/', 'privacy/'] + [f'cases/{c["slug"]}/' for c in CASES]
    write('sitemap.xml', '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join(f'<url><loc>{E(page_url(r))}</loc></url>' for r in routes) + '</urlset>\n')
    write('robots.txt', 'User-agent: *\n' + ('Allow: /\n' if CONFIG['indexable'] else 'Disallow: /\n') + 'Sitemap: ' + page_url('sitemap.xml') + '\n')
    write('404.html', frame('Page not found', '<div class="wrap error-page"><div class="eyebrow" style="justify-content:center">404 / No case here</div><h1>Let’s get you back<br>to the evidence.</h1><p>This page may have moved, or the link is incomplete.</p><a class="btn btn-dark" href="' + E(CONFIG['base_url']) + '">Explore the collection →</a></div>', prefix=CONFIG['base_url'], route='404.html'))
    source_archive()
    print(f'Built {len(routes)} pages and {len(CASES)} cases in {OUT}')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--base-url', help='Override the canonical deployment URL')
    p.add_argument('--repository', help='Public GitHub repository URL')
    p.add_argument('--indexable', action='store_true', help='Enable indexing for the confirmed launch URL')
    args = p.parse_args()
    if args.base_url: CONFIG['base_url'] = args.base_url.rstrip('/') + '/'
    if args.repository: CONFIG['repository'] = args.repository
    if args.indexable: CONFIG['indexable'] = True
    build()

