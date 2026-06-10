#!/usr/bin/env python3
"""
For each PNG in the current directory, search thesession.org for a matching
ABC tune and save the best match to abc/<stem>.abc.

Usage:
    python fetch_abc.py [tune name ...]   # specific tunes
    python fetch_abc.py                   # all PNGs not yet in abc/

Output:
    abc/<stem>.abc          if a match is found
    abc/<stem>.nomatch      if nothing found on thesession.org

Review the .abc files before rendering — verify key sig and structure match
the scan, and add chord symbols by hand if needed.
"""
import json
import re
import sys
import time
from pathlib import Path
import urllib.request
import urllib.parse
import urllib.error

ABC_DIR = Path("abc")
ABC_DIR.mkdir(exist_ok=True)

SESSION_SEARCH = "https://thesession.org/tunes/search?q={q}&format=json&perpage=5"
SESSION_TUNE   = "https://thesession.org/tunes/{id}?format=json"


def search(name: str) -> list[dict]:
    q = urllib.parse.quote(name)
    url = SESSION_SEARCH.format(q=q)
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.load(r).get("tunes", [])
    except Exception as e:
        print(f"    search error: {e}")
        return []


def get_abc(tune_id: int) -> str | None:
    url = SESSION_TUNE.format(id=tune_id)
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.load(r)
        settings = data.get("settings", [])
        if not settings:
            return None
        # Return the ABC from the most-popular setting (first result)
        return settings[0].get("abc", None)
    except Exception as e:
        print(f"    fetch error: {e}")
        return None


def best_match(name: str, results: list[dict]) -> dict | None:
    """Pick the result whose name is closest to our tune name."""
    name_clean = re.sub(r"[^a-z0-9 ]", "", name.lower())
    for r in results:
        r_clean = re.sub(r"[^a-z0-9 ]", "", r.get("name", "").lower())
        if r_clean == name_clean:
            return r
    # Fuzzy: the result whose name contains all words of our name
    words = set(name_clean.split())
    for r in results:
        r_words = set(re.sub(r"[^a-z0-9 ]", "", r.get("name", "").lower()).split())
        if words <= r_words or r_words <= words:
            return r
    # Fall back to first result if there's only one
    if len(results) == 1:
        return results[0]
    return None


def make_header(stem: str, abc_body: str, tune_meta: dict) -> str:
    """Wrap raw ABC body in a proper header."""
    # abcm2ps/abc2ps expect header fields before the music
    # The session API returns just the music lines (no X/T/M/L/K header)
    # Sometimes the ABC already contains a full tune; detect that.
    if abc_body.strip().startswith("X:"):
        return abc_body  # already has header

    # Build a minimal header from metadata
    name     = tune_meta.get("name", stem)
    meter    = tune_meta.get("meter", "4/4")
    key      = tune_meta.get("key", "")
    mode     = tune_meta.get("mode", "")
    if mode and mode.lower() not in ("major", ""):
        key_str = f"{key}{mode[:3]}"
    else:
        key_str = key or "C"

    lines = [
        "X:1",
        f"T:{name}",
        f"M:{meter}",
        "L:1/8",
        f"K:{key_str}",
        abc_body,
    ]
    return "\n".join(lines)


def fetch_one(stem: str) -> bool:
    """Returns True if an ABC file was written."""
    out_abc   = ABC_DIR / f"{stem}.abc"
    out_nomatch = ABC_DIR / f"{stem}.nomatch"

    if out_abc.exists():
        print(f"  [skip] {stem} — already have .abc")
        return True
    if out_nomatch.exists():
        print(f"  [skip] {stem} — previously no match")
        return False

    print(f"  Searching: {stem!r}")
    results = search(stem)
    if not results:
        print(f"    → no results")
        out_nomatch.write_text("")
        return False

    match = best_match(stem, results)
    if not match:
        names = [r.get("name") for r in results]
        print(f"    → {len(results)} results but no close match: {names}")
        out_nomatch.write_text("\n".join(json.dumps(r) for r in results))
        return False

    print(f"    → matched: {match.get('name')!r}  (id={match.get('id')})")
    abc_body = get_abc(match["id"])
    if not abc_body:
        print(f"    → no ABC in settings")
        out_nomatch.write_text(json.dumps(match))
        return False

    full_abc = make_header(stem, abc_body, match)
    out_abc.write_text(full_abc, encoding="utf-8")
    print(f"    → saved {out_abc}")
    return True


def main():
    if len(sys.argv) > 1:
        stems = [a.removesuffix(".png") for a in sys.argv[1:]]
    else:
        stems = sorted(
            p.stem for p in Path(".").glob("*.png")
            if not (ABC_DIR / f"{p.stem}.abc").exists()
            and not (ABC_DIR / f"{p.stem}.nomatch").exists()
        )

    print(f"Processing {len(stems)} tunes...")
    found = skipped = missed = 0
    for stem in stems:
        result = fetch_one(stem)
        if result is True:
            found += 1
        else:
            missed += 1
        time.sleep(0.5)   # be polite to thesession.org

    print(f"\nDone. Found: {found}  Not found: {missed}")
    if missed:
        print(f"Check abc/*.nomatch files for near-misses to fix manually.")


if __name__ == "__main__":
    main()
