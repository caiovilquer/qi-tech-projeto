#!/usr/bin/env python3
"""Generate docs/RFC-v8.pdf from docs/RFC-v8.md with headless Chrome or Edge.

No Python dependencies: Markdown and Mermaid render inside the browser, with
marked and mermaid pinned below and downloaded from jsDelivr (network needed).
Usage: python3 tools/rfc_pdf.py [--source docs/RFC-v8.md] [--output docs/RFC-v8.pdf]
Set CHROME=/path/to/browser when Chrome or Edge is not found automatically.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

MARKED = 'https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js'
MERMAID = 'https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js'
CANDIDATES = [
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
]

CSS = """
@page { size: A4; margin: 14mm 14mm 15mm;
  @bottom-center { content: "FOOTER · " counter(page) "/" counter(pages);
    font: 7.5pt "Segoe UI", "Helvetica Neue", Arial, sans-serif; color: #5f6f67; } }
body { margin: 0; font: 9pt/1.38 "Segoe UI", "Helvetica Neue", Arial, sans-serif; color: #1d2b25; }
h1 { font-size: 15pt; line-height: 1.2; margin: 0 0 5pt; color: #163d2e; }
h2 { font-size: 12pt; margin: 9pt 0 3pt; padding-bottom: 2pt; border-bottom: 1px solid #c9d8cf; color: #163d2e; }
h3 { font-size: 10.2pt; margin: 7pt 0 2pt; color: #1f4f3c; }
h2, h3 { break-after: avoid; }
.keep { break-inside: avoid; }
p, li { margin: 0 0 3pt; }
ol, ul { margin: 0 0 4pt 15pt; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 3pt 0 6pt; font-size: 7.8pt; line-height: 1.3; }
th, td { border: 1px solid #c9d8cf; padding: 2pt 3pt; vertical-align: top; text-align: left; }
th { background: #e5efe9; }
tr { break-inside: avoid; }
table.meta { width: auto; font-size: 8.6pt; }
table.meta td:first-child { padding-right: 10pt; }
table.routes th:nth-child(1) { width: 6%; } table.routes th:nth-child(2) { width: 17%; }
table.routes th:nth-child(3) { width: 23%; } table.routes th:nth-child(4) { width: 18%; }
table.wide4 th:nth-child(1) { width: 14%; } table.wide4 th:nth-child(2) { width: 28%; }
table.wide4 th:nth-child(3) { width: 37%; }
code { font-family: Consolas, "DejaVu Sans Mono", monospace; font-size: 0.9em; background: #f1f5f2; padding: 0 1.5pt; border-radius: 2px; }
td code { overflow-wrap: normal; word-break: keep-all; }
pre { margin: 3pt 0 6pt; padding: 5pt 7pt; background: #f1f5f2; border: 1px solid #c9d8cf; border-radius: 3px;
  white-space: pre-wrap; break-inside: avoid; font-size: 7.8pt; line-height: 1.35; }
pre code { background: none; padding: 0; font-size: 1em; }
blockquote { margin: 6pt 0 0; padding: 4pt 9pt; background: #eef5f0; border-left: 4px solid #2f6b50; break-inside: avoid; }
blockquote ul { margin-left: 12pt; }
img { display: block; width: 72%; margin: 3pt auto 5pt; }
.mermaid { display: flex; justify-content: center; margin: 2pt 0 4pt; break-inside: avoid; }
.mermaid svg { max-width: 100% !important; max-height: 150mm; height: auto; }
"""

SCRIPT = r"""
const escape = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const doc = document.getElementById('doc');
doc.innerHTML = marked.parse(SOURCE, { gfm: true });
for (const table of doc.querySelectorAll('table')) {
  const head = table.querySelector('thead');
  if (head && [...head.querySelectorAll('th')].every(th => !th.textContent.trim())) {
    head.remove(); table.classList.add('meta');
  } else if (head && head.querySelectorAll('th').length === 4) {
    table.classList.add('wide4');
  }
}
const routes = [...doc.querySelectorAll('h3')].find(h => h.textContent.trim() === 'Rotas');
let next = routes && routes.nextElementSibling;
while (next && next.tagName !== 'TABLE' && next.tagName !== 'H3') next = next.nextElementSibling;
if (next && next.tagName === 'TABLE') next.classList.add('routes');
for (const code of doc.querySelectorAll('td code')) {
  if (code.textContent.startsWith('/')) code.innerHTML = code.textContent.split('/').map(escape).join('/<wbr>');
}
mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: 'neutral',
  sequence: { mirrorActors: false, messageMargin: 22, height: 36, boxMargin: 6, noteMargin: 6 } });
(async () => {
  let index = 0;
  for (const block of [...doc.querySelectorAll('pre > code.language-mermaid')]) {
    const div = document.createElement('div');
    div.className = 'mermaid';
    try {
      div.innerHTML = (await mermaid.render('diagram' + index++, block.textContent)).svg;
    } catch (error) {
      div.textContent = 'MERMAID ERROR: ' + (error.message || error);
    }
    block.parentElement.replaceWith(div);
  }
  // A flow title (a paragraph that is only bold text) stays with what follows it.
  for (const title of [...doc.querySelectorAll('p')]) {
    const next = title.nextElementSibling;
    if (next && title.children.length === 1 && title.firstElementChild.tagName === 'STRONG'
        && title.textContent.trim() === title.firstElementChild.textContent.trim()) {
      const keep = document.createElement('div');
      keep.className = 'keep';
      title.before(keep);
      keep.append(title, next);
    }
  }
  document.body.dataset.ready = 'yes';
})();
"""


def find_browser():
    if os.environ.get('CHROME'):
        return os.environ['CHROME']
    for name in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'microsoft-edge', 'msedge'):
        if shutil.which(name):
            return shutil.which(name)
    for path in CANDIDATES:
        if Path(path).exists():
            return path
    raise SystemExit('Chrome or Edge not found; set CHROME=/path/to/browser')


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default=str(root / 'docs' / 'RFC-v8.md'))
    parser.add_argument('--output', default=str(root / 'docs' / 'RFC-v8.pdf'))
    args = parser.parse_args()
    source = Path(args.source).resolve()
    output = Path(args.output).resolve()
    markdown = source.read_text(encoding='utf-8')
    title = re.search(r'^# (.+)$', markdown, flags=re.M).group(1).strip()
    version = re.search(r'\*\*Versão\*\*\s*\|\s*([^|]+?)\s*\|', markdown).group(1)
    date = re.search(r'\*\*Data\*\*\s*\|\s*([^|]+?)\s*\|', markdown).group(1)
    css = CSS.replace('FOOTER', f'RFC v{version} · {date}')
    page = (f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>{title}</title>'
            f'<base href="{source.parent.as_uri()}/"><style>{css}</style>'
            f'<script src="{MARKED}"></script><script src="{MERMAID}"></script></head>'
            f'<body><main id="doc"></main><script>const SOURCE = {json.dumps(markdown)};{SCRIPT}</script>'
            '</body></html>')
    with tempfile.TemporaryDirectory() as work:
        html = Path(work) / 'rfc.html'
        html.write_text(page, encoding='utf-8')
        subprocess.run([find_browser(), '--headless=new', '--disable-gpu', '--no-first-run',
                        '--no-default-browser-check', f'--user-data-dir={Path(work) / "profile"}',
                        '--no-pdf-header-footer', '--print-to-pdf-no-header', '--virtual-time-budget=30000',
                        f'--print-to-pdf={output}', html.as_uri()],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
    print(f'{output} generated from {source.name}')


if __name__ == '__main__':
    main()
