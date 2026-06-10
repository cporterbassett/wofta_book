#!/usr/bin/env python3
"""Interactive tune cutter.

Usage:  tune_cutter.py <file.pdf> [output_dir]

Opens a browser showing every PDF page at full render resolution.
Click anywhere on a page to add a horizontal cut line.
Click the ✕ on an existing cut line to remove it.
Press "Save All Crops" when done.
"""

import http.server
import json
import sys
import tempfile
import threading
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

import subprocess
from PIL import Image

DPI = 200
MARGIN_PX = 15
PORT = 8765

# Globals set by main()
PAGE_FILES: dict[int, Path] = {}
OUTPUT_DIR: Path = Path(".")
PDF_NAME: str = ""
SKIP_PAGES: set[int] = set()

# ---------------------------------------------------------------------------
# HTML / JS
# ---------------------------------------------------------------------------

HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Tune Cutter</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: sans-serif; background: #1a1a2e; color: #eee; }

#toolbar {
  position: sticky; top: 0; z-index: 200;
  background: #0f3460; padding: 10px 16px;
  display: flex; align-items: center; gap: 14px;
  border-bottom: 3px solid #e94560; flex-wrap: wrap;
}
#toolbar h1 { font-size: 1em; color: #e94560; flex: 1; }
#save-btn {
  background: #e94560; color: white; border: none;
  padding: 8px 18px; border-radius: 4px; cursor: pointer; font-size: 0.9em;
}
#save-btn:hover { background: #c73652; }
#status { font-size: 0.82em; color: #aaa; }

#pages { padding: 16px; display: flex; flex-direction: column; gap: 20px; }

.page-wrapper { background: #16213e; border-radius: 8px; overflow: hidden; }
.page-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 6px 12px; background: #0f3460; font-size: 0.82em;
}
.page-header .skip-btn {
  background: #444; color: #ccc; border: none;
  padding: 3px 10px; border-radius: 3px; cursor: pointer; font-size: 0.8em;
}
.page-header .skip-btn.active { background: #e94560; color: white; }
.page-inner { padding: 8px; }

.page-container {
  position: relative; display: inline-block;
  cursor: crosshair; user-select: none;
  border: 1px solid #0f3460;
}
.page-container img { display: block; max-width: min(1200px, 100%); height: auto; }
.page-container.skipped img { opacity: 0.3; }
.page-container.skipped { cursor: default; }

.cut-line {
  position: absolute; left: 0; right: 0; height: 4px;
  background: rgba(233, 69, 96, 0.85); cursor: pointer;
  display: flex; align-items: center; justify-content: flex-end;
  padding-right: 4px;
}
.cut-line:hover { background: #e94560; }
.cut-x {
  background: #e94560; color: white; border-radius: 50%;
  width: 16px; height: 16px; font-size: 10px; line-height: 16px;
  text-align: center; flex-shrink: 0; pointer-events: none;
}

.tune-label {
  position: absolute; left: 6px;
  background: rgba(15, 52, 96, 0.85);
  color: #e0e0ff; font-size: 11px; padding: 2px 6px;
  border-radius: 3px; pointer-events: none;
}
</style>
</head>
<body>
<div id="toolbar">
  <h1 id="pdf-name">Tune Cutter</h1>
  <button id="save-btn" onclick="saveCrops()">Save All Crops</button>
  <span id="status">Loading…</span>
</div>
<div id="pages"></div>

<script>
// state: { pageNum: { cuts: [y_px, ...], skip: bool } }
const state = {};
let pageList = [];

async function init() {
  const resp = await fetch('/state');
  const data = await resp.json();
  document.getElementById('pdf-name').textContent = data.pdf_name;
  pageList = data.pages;

  data.pages.forEach(pn => {
    state[pn] = { cuts: (data.cuts[pn] || []).slice(), skip: false };
  });

  renderAll(data.pages);
  updateStatus();
}

function renderAll(pages) {
  const container = document.getElementById('pages');
  container.innerHTML = '';
  pages.forEach(pn => {
    const wrap = document.createElement('div');
    wrap.className = 'page-wrapper';
    wrap.id = 'wrap-' + pn;
    wrap.innerHTML = `
      <div class="page-header">
        <span>PDF page ${pn} &nbsp; <span id="cnt-${pn}" style="color:#e94560"></span></span>
        <button class="skip-btn" id="skip-${pn}" onclick="toggleSkip(${pn})">Skip page</button>
      </div>
      <div class="page-inner">
        <div class="page-container" id="pc-${pn}">
          <img src="/page/${pn}.png" draggable="false"
               onload="renderCuts(${pn})" alt="page ${pn}">
        </div>
      </div>`;
    container.appendChild(wrap);

    wrap.querySelector('.page-container').addEventListener('click', e => {
      if (state[pn].skip) return;
      if (e.target.closest('.cut-line')) return;
      const pc = document.getElementById('pc-' + pn);
      const img = pc.querySelector('img');
      const rect = pc.getBoundingClientRect();
      const displayY = e.clientY - rect.top;
      const pixelY = Math.round(displayY * img.naturalHeight / img.offsetHeight);
      state[pn].cuts.push(pixelY);
      state[pn].cuts.sort((a, b) => a - b);
      renderCuts(pn);
      updateStatus();
    });
  });
}

function toggleSkip(pn) {
  state[pn].skip = !state[pn].skip;
  const btn = document.getElementById('skip-' + pn);
  btn.classList.toggle('active', state[pn].skip);
  const pc = document.getElementById('pc-' + pn);
  pc.classList.toggle('skipped', state[pn].skip);
  renderCuts(pn);
  updateStatus();
}

function removeCut(pn, y) {
  state[pn].cuts = state[pn].cuts.filter(c => c !== y);
  renderCuts(pn);
  updateStatus();
}

function renderCuts(pn) {
  const pc = document.getElementById('pc-' + pn);
  if (!pc) return;
  const img = pc.querySelector('img');
  if (!img || !img.offsetHeight) return;

  pc.querySelectorAll('.cut-line, .tune-label').forEach(el => el.remove());
  if (state[pn].skip) {
    document.getElementById('cnt-' + pn).textContent = '(skipped)';
    return;
  }

  const scale = img.offsetHeight / img.naturalHeight;
  const cuts = state[pn].cuts;
  const boundaries = [0, ...cuts, img.naturalHeight];
  const tuneStart = tuneOffset(pn);

  // tune region labels
  for (let i = 0; i < boundaries.length - 1; i++) {
    const midY = (boundaries[i] + boundaries[i + 1]) / 2 * scale;
    const lbl = document.createElement('div');
    lbl.className = 'tune-label';
    lbl.textContent = '#' + (tuneStart + i);
    lbl.style.top = (midY - 10) + 'px';
    pc.appendChild(lbl);
  }

  // cut lines
  cuts.forEach(y => {
    const line = document.createElement('div');
    line.className = 'cut-line';
    line.style.top = (y * scale - 2) + 'px';
    const x = document.createElement('div');
    x.className = 'cut-x'; x.textContent = '✕';
    line.appendChild(x);
    line.addEventListener('click', e => { e.stopPropagation(); removeCut(pn, y); });
    pc.appendChild(line);
  });

  document.getElementById('cnt-' + pn).textContent =
    (cuts.length + 1) + ' tune(s)';
}

function tuneOffset(targetPage) {
  let n = 1;
  for (const pn of pageList) {
    if (pn === targetPage) return n;
    if (!state[pn].skip) n += state[pn].cuts.length + 1;
  }
  return n;
}

function updateStatus() {
  let total = 0;
  for (const pn of pageList) {
    if (!state[pn].skip) total += state[pn].cuts.length + 1;
  }
  document.getElementById('status').textContent = total + ' total tunes';
}

async function saveCrops() {
  document.getElementById('status').textContent = 'Generating…';
  document.getElementById('save-btn').disabled = true;
  const payload = {};
  pageList.forEach(pn => {
    payload[pn] = { cuts: state[pn].cuts, skip: state[pn].skip };
  });
  const resp = await fetch('/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const result = await resp.json();
  document.getElementById('status').textContent =
    '✓ Saved ' + result.count + ' crops to ' + result.output_dir;
  document.getElementById('save-btn').disabled = false;
}

init();
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silence request logging

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self._send(200, "text/html", HTML.encode())
        elif path == "/state":
            cuts: dict[int, list[int]] = {}
            self._send_json({
                "pdf_name": PDF_NAME,
                "pages": sorted(PAGE_FILES.keys()),
                "cuts": {str(pn): [] for pn in PAGE_FILES},
            })
        elif path.startswith("/page/") and path.endswith(".png"):
            try:
                pn = int(path.split("/")[-1].removesuffix(".png"))
            except ValueError:
                self._send(404, "text/plain", b"bad page"); return
            if pn in PAGE_FILES:
                self._send(200, "image/png", PAGE_FILES[pn].read_bytes())
            else:
                self._send(404, "text/plain", b"not found")
        else:
            self._send(404, "text/plain", b"not found")

    def do_POST(self):
        if urlparse(self.path).path == "/generate":
            n = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(n))
            count = _generate_crops(payload)
            self._send_json({"count": count, "output_dir": str(OUTPUT_DIR.resolve())})

    def _send(self, code, ctype, data: bytes):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, obj):
        self._send(200, "application/json", json.dumps(obj).encode())


def _generate_crops(payload: dict) -> int:
    """payload: {page_num_str: {cuts: [y,...], skip: bool}}"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    counter = 1
    for pn in sorted(PAGE_FILES.keys()):
        entry = payload.get(str(pn), {})
        if entry.get("skip"):
            continue
        cuts = sorted(entry.get("cuts", []))
        img = Image.open(PAGE_FILES[pn])
        w, h = img.size
        boundaries = [0] + cuts + [h]
        for i in range(len(boundaries) - 1):
            top = max(0, boundaries[i] - MARGIN_PX)
            bot = min(h, boundaries[i + 1] + MARGIN_PX)
            img.crop((0, top, w, bot)).save(OUTPUT_DIR / f"tune_{counter:03d}.png")
            counter += 1
    return counter - 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global PAGE_FILES, OUTPUT_DIR, PDF_NAME

    args = sys.argv[1:]
    if not args:
        print("Usage: tune_cutter.py <file.pdf> [output_dir]")
        sys.exit(1)

    pdf_path = Path(args[0])
    if not pdf_path.exists():
        print(f"Not found: {pdf_path}", file=sys.stderr); sys.exit(1)

    OUTPUT_DIR = Path(args[1]) if len(args) > 1 else pdf_path.parent / (pdf_path.stem + "_tunes")
    PDF_NAME = pdf_path.name

    print(f"Rendering pages from {pdf_path.name} …")
    tmpdir = tempfile.mkdtemp(prefix="tune_cutter_")
    prefix = str(Path(tmpdir) / "page")
    result = subprocess.run(
        ["pdftoppm", "-r", str(DPI), "-png", str(pdf_path), prefix],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("pdftoppm failed:", result.stderr, file=sys.stderr); sys.exit(1)

    for f in sorted(Path(tmpdir).glob("page-*.png")):
        pn = int(f.stem.split("-")[-1])
        PAGE_FILES[pn] = f

    print(f"  {len(PAGE_FILES)} pages rendered.")
    print(f"Crops will be saved to: {OUTPUT_DIR.resolve()}")

    http.server.HTTPServer.allow_reuse_address = True
    server = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    url = f"http://127.0.0.1:{PORT}/"
    print(f"Opening {url}  (Ctrl-C to quit when done)")
    webbrowser.open(url)

    try:
        t.join()
    except KeyboardInterrupt:
        print("\nDone.")
        server.shutdown()


if __name__ == "__main__":
    main()
