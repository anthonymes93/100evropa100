#!/usr/bin/env python3
"""One-shot self-host fonts and remove the Google Maps runtime embed.
Stops without modifying tracked pages if any font asset cannot be retrieved."""
import hashlib
import html
import json
import pathlib
import re
import urllib.request
import urllib.parse
ROOT = pathlib.Path.cwd()
PAGES = ['index.html','services/index.html','contact-us/index.html','projects/index.html','projects/index2822.html','projects/index43dd.html','projects/indexb728.html','projects/indexb76e.html']
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
def get(url):
    req = urllib.request.Request(url, headers={'User-Agent':UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        if r.status!=200: raise RuntimeError(f'HTTP {r.status}: {url}')
        return r.read()
downloaded = {}
rewritten = {}
sha_records = []
for path in PAGES:
    content = (ROOT/path).read_text(encoding='utf-8')
    prefix = '' if path=='index.html' else '../'
    pattern = r'<link\\b(?=[^>]*href=[\\x22\\x27]https://fonts\\.googleapis\\.com/css[^\\x22\\x27]*[\\x22\\x27])[^>]*>'
    def replace_link(match):
        tag=match.group(0)
        url=html.unescape(re.search(r'href=[\\x22\\x27]([^\\x22\\x27]+)',tag).group(1))
        if url not in downloaded:
            stylesheet=get(url).decode('utf-8')
            def replace_font(m):
                remote=m.group(1)
                if not remote.startswith('https://fonts.gstatic.com/'):
                    raise RuntimeError(f'Unexpected font URL: {remote}')
                if remote not in downloaded:
                    data=get(remote)
                    extension=urllib.parse.urlsplit(remote).path.rsplit('.',1)[-1].lower()
                    if extension not in {'woff','woff2','ttf','otf'}:raise RuntimeError(f'Unexpected font extension: {remote}')
                    digest=hashlib.sha256(data).hexdigest()
                    destination=f'assets/fonts/{digest[:20]}.{extension}'
                    downloaded[remote]=(destination,data)
                    sha_records.append({'source':remote,'file':destination,'sha256':digest})
                return 'url(./'+downloaded[remote][0].split('assets/',1)[1]+')'
            stylesheet=re.sub(r'url\\(\\s*[\\x22\\x27]?(https://fonts\\.gstatic\\.com/[^)\\x22\\x27]+)[\\x22\\x27]?\\s*\\)',replace_font,stylesheet)
            digest=hashlib.sha256(url.encode()).hexdigest()
            destination=f'assets/fonts/google-{digest[:20]}.css'
            downloaded[url]=(destination,stylesheet.encode('utf-8'))
        destination=downloaded[url][0]
        return re.sub(r'href=[\\x22\\x27][^\\x22\\x27]+[\\x22\\x27]','href="'+prefix+destination+'"',tag)
    content=re.sub(pattern,replace_link,content,flags=re.I)
    content=re.sub(r'<link\\b(?=[^>]*href=[\\x22\\x27](?:https?:)?//fonts\\.(?:googleapis|gstatic)\\.com/)[^>]*>\\s*','',content,flags=re.I)
    if path=='contact-us/index.html':
        iframe=re.search(r'<iframe\\b[^>]*src=[\\x22\\x27]https://maps\\.google\\.com/[^>]*>\\s*</iframe>',content,flags=re.I|re.S)
        if not iframe:raise RuntimeError('Expected contact map iframe not found')
        content=content[:iframe.start()]+'''<div class="ev-local-map" role="group" aria-label="Hamilton Ontario location">
          <div class="ev-local-map-title">Serving Hamilton, Ontario</div>
          <p>View our service area and directions on Google Maps.</p>
          <a href="https://www.google.com/maps/search/?api=1&amp;query=Hamilton%2C%20Ontario" target="_blank" rel="noopener noreferrer">Open in Google Maps</a>
        </div>'''+content[iframe.end():]
        if '</head>' not in content:raise RuntimeError('Missing contact head')
        content=content.replace('</head>','<style>.ev-local-map{min-height:280px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;background:#eee;color:#222;padding:35px 18px;border:1px solid #ddd;box-sizing:border-box}.ev-local-map-title{font-size:24px;font-weight:700}.ev-local-map p{margin:14px 0}.ev-local-map a{padding:12px 22px;background:#ffbf3b;color:#111;text-decoration:none;font-weight:700;border-radius:3px}</style>\n</head>',1)
    if 'fonts.googleapis.com/css' in content or 'maps.google.com/maps?q=' in content:raise RuntimeError('Residual remote render dependency in '+path)
    rewritten[path]=content
if not any(k.startswith('https://fonts.googleapis.com/') for k in downloaded):raise RuntimeError('No font stylesheets matched; refusing empty install')
for _,(dest,data) in downloaded.items():
    target=ROOT/dest
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(data)
for path,content in rewritten.items():(ROOT/path).write_text(content,encoding='utf-8')
manifest={'sources':len(downloaded),'font_files':len(sha_records),'sha256':sha_records}
(ROOT/'assets/fonts/manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('SUCCESS',json.dumps({'pages':len(rewritten),'font_assets':len(sha_records),'stylesheets':len(downloaded)-len(sha_records)}))
