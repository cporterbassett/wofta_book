#!/usr/bin/env python3
"""
Transcribe a scanned sheet music PNG to ABC notation using Claude (via the
claude CLI, so no API key is needed -- uses your Anthropic subscription).

Usage:
    python transcribe.py <image.png> [output.abc]

If output.abc is omitted, writes to <image-stem>.abc
"""
import base64
import json
import subprocess
import sys
from pathlib import Path

SYSTEM_PROMPT = (
    "You are an expert music transcriber specialising in traditional/folk fiddle tunes. "
    "You will be given a scanned or photocopied sheet music image and must output the "
    "complete tune as ABC notation.\n\n"
    "Rules:\n"
    "- Output ONLY the ABC notation -- no prose, no markdown fences, no explanations.\n"
    "- Include the full header: X, T, C (composer/source if visible), Z (transcriber if "
    "  visible), M, L, Q (if a tempo is marked), K.\n"
    "- Use L:1/8 unless the note values make another default more natural.\n"
    "- Preserve all chord symbols (e.g. \"A\", \"D\", \"E7\") exactly as written.\n"
    "- Preserve all repeats (|: :|), first/second endings ([1 :|[2 ), double bars (||), "
    "  and section double bars.\n"
    "- Preserve ties (A-A) but omit slurs for now (slurs will be added in a later pass).\n"
    "- Omit hand-written bowing marks (down-bow, up-bow) -- these are not part of the tune.\n"
    "- Match the original line breaks: at the end of each system (staff line), append a "
    "  backslash so abcm2ps forces a line break there.\n"
    "- Key signature: derive from the number/type of sharps or flats shown.\n"
    "- Time signature: read from the score; use C for common time (4/4) or C| for cut time.\n"
    "- If the tune has multiple sections (A part, B part, etc.), separate them with a "
    "  blank line in the ABC body.\n"
    "- Double-check: count beats per bar. Flag bars that don't add up with a % comment.\n"
)

USER_PROMPT = (
    "Please transcribe this sheet music image to ABC notation.\n\n"
    + SYSTEM_PROMPT
    + "\nOutput ONLY the ABC notation now."
)


def encode_image(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def transcribe(image_path: Path) -> str:
    b64 = encode_image(image_path)

    msg = {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": b64,
                    },
                },
                {"type": "text", "text": USER_PROMPT},
            ],
        },
    }

    proc = subprocess.Popen(
        [
            "claude", "-p", "--verbose",
            "--input-format", "stream-json",
            "--output-format", "stream-json",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    proc.stdin.write(json.dumps(msg))
    proc.stdin.close()

    # Read streaming output line by line to avoid pipe buffer deadlock
    result_text = None
    for line in proc.stdout:
        try:
            ev = json.loads(line)
            if ev.get("type") == "result":
                result_text = ev.get("result", "")
        except json.JSONDecodeError:
            pass

    proc.wait()
    if proc.returncode != 0 and result_text is None:
        raise RuntimeError(f"claude exited {proc.returncode} with no result")

    # Strip markdown code fences if the model wrapped the output
    lines = result_text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]

    # Remove blank lines immediately after K: header (they terminate the tune in ABC)
    cleaned = []
    last_was_k = False
    for line in lines:
        if last_was_k and line.strip() == "":
            last_was_k = False
            continue
        cleaned.append(line)
        last_was_k = line.startswith("K:")
    return "\n".join(cleaned)


def main():
    if len(sys.argv) < 2:
        print("Usage: transcribe.py <image.png> [output.abc]", file=sys.stderr)
        sys.exit(1)

    image_path = Path(sys.argv[1])
    if not image_path.exists():
        print(f"File not found: {image_path}", file=sys.stderr)
        sys.exit(1)

    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else image_path.with_suffix(".abc")

    print(f"Transcribing {image_path.name}...", flush=True)
    abc_text = transcribe(image_path)

    out_path.write_text(abc_text, encoding="utf-8")
    print(f"Written to {out_path}")


if __name__ == "__main__":
    main()
