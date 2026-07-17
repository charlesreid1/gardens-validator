#!/usr/bin/env python3
"""
Add a garden flag to the validator's index.html GARDENS list.

If the garden name already exists, the existing salt is reused and the
new flag hash is appended. Otherwise a new garden entry is created with
a fresh random salt.

Usage:
    python3 add_garden_flag.py \
        --garden-name "Garden of XYZ" \
        --garden-flag "garden{xyz}" \
        [--index /path/to/index.html]
"""

import argparse
import hashlib
import json
import os
import re
import secrets
import sys

DEFAULT_INDEX = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "gh-pages-gardens-validator",
        "index.html",
    )
)

ITERATIONS = 400_000
HASH_BYTES = 32
FLAG_RE = re.compile(r"^garden\{(.*)\}$", re.IGNORECASE)


def normalize_flag(raw: str) -> str:
    trimmed = raw.strip()
    m = FLAG_RE.match(trimmed)
    return m.group(1) if m else trimmed


def pbkdf2(password: str, salt_hex: str) -> str:
    salt = bytes.fromhex(salt_hex)
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, ITERATIONS, dklen=HASH_BYTES
    )
    return derived.hex()


def find_gardens_block(html: str) -> tuple[int, int]:
    """Return (start, end) char offsets of the array literal after `const GARDENS =`.

    start points at the opening `[`, end points just past the matching `]`.
    """
    m = re.search(r"const\s+GARDENS\s*=\s*\[", html)
    if not m:
        raise RuntimeError("could not locate `const GARDENS = [` in index.html")
    start = m.end() - 1  # index of `[`
    depth = 0
    i = start
    in_str = None  # None | '"' | "'" | '`'
    escape = False
    while i < len(html):
        ch = html[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_str:
                in_str = None
        else:
            if ch in ('"', "'", "`"):
                in_str = ch
            elif ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    return start, i + 1
        i += 1
    raise RuntimeError("unterminated GARDENS array")


def parse_gardens(block_src: str) -> list[dict]:
    """Parse the JS array-of-objects literal into Python dicts.

    The literal uses unquoted keys and trailing commas, so JSON.loads
    won't work directly. Convert it with a couple of regex passes first.
    Only the shapes actually present in the file are supported:
      { name: "...", salt: "...", flags: [ "...", ... ] }
    """
    src = block_src

    # Strip line comments.
    src = re.sub(r"//[^\n]*", "", src)
    # Strip block comments.
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    # Quote bare keys (name/salt/flags).
    src = re.sub(r"([{,]\s*)(name|salt|flags)(\s*:)", r'\1"\2"\3', src)
    # Remove trailing commas before } or ].
    src = re.sub(r",(\s*[}\]])", r"\1", src)

    return json.loads(src)


def render_gardens(gardens: list[dict]) -> str:
    """Render the array back with the file's existing 2-space indent style."""
    lines = ["["]
    for i, g in enumerate(gardens):
        lines.append("  {")
        lines.append(f'    name: {json.dumps(g["name"])},')
        lines.append(f'    salt: {json.dumps(g["salt"])},')
        lines.append("    flags: [")
        for j, f in enumerate(g["flags"]):
            comma = "," if j < len(g["flags"]) - 1 else ""
            lines.append(f"      {json.dumps(f)}{comma}")
        lines.append("    ]")
        comma = "," if i < len(gardens) - 1 else ""
        lines.append("  }" + comma)
    lines.append("]")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--garden-name", required=True)
    ap.add_argument("--garden-flag", required=True)
    ap.add_argument(
        "--index",
        default=DEFAULT_INDEX,
        help=f"path to index.html (default: {DEFAULT_INDEX})",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="print the updated GARDENS block without writing the file",
    )
    args = ap.parse_args()

    with open(args.index, "r", encoding="utf-8") as fh:
        html = fh.read()

    start, end = find_gardens_block(html)
    gardens = parse_gardens(html[start:end])

    normalized = normalize_flag(args.garden_flag)

    existing = next(
        (g for g in gardens if g["name"] == args.garden_name), None
    )
    if existing is not None:
        salt_hex = existing["salt"]
        hash_hex = pbkdf2(normalized, salt_hex)
        if hash_hex in existing["flags"]:
            print(
                f"[skip] flag already present in '{args.garden_name}' "
                f"(hash {hash_hex})",
                file=sys.stderr,
            )
            return 0
        existing["flags"].append(hash_hex)
        action = "appended to existing garden (reused salt)"
    else:
        salt_hex = secrets.token_hex(16)
        hash_hex = pbkdf2(normalized, salt_hex)
        gardens.append(
            {"name": args.garden_name, "salt": salt_hex, "flags": [hash_hex]}
        )
        action = "created new garden"

    new_block = render_gardens(gardens)
    new_html = html[:start] + new_block + html[end:]

    print(f"[ok] {action}", file=sys.stderr)
    print(f"     garden: {args.garden_name}", file=sys.stderr)
    print(f"     salt:   {salt_hex}", file=sys.stderr)
    print(f"     hash:   {hash_hex}", file=sys.stderr)

    if args.dry_run:
        print(new_block)
        return 0

    with open(args.index, "w", encoding="utf-8") as fh:
        fh.write(new_html)
    print(f"[ok] wrote {args.index}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
