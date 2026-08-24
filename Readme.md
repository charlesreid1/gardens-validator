# The Gardens

A static site that hosts [The Gardens](https://charlesreid1.com/wiki/The_Gardens) — a
collection of steganographic CTF challenges — along with a client-side flag
verifier.

The page lives at `output/index.html` and is fully self-contained: no build
step is required to serve it, and no server-side state is involved. Flags are
verified in the browser using PBKDF2-SHA256 (400,000 iterations) against
per-garden salts.

## Layout

The page has two tabs:

- **season01** — renders every discovered challenge (`s01c01`, `s01c02`, …)
  inline. The raw challenge text is embedded verbatim so zero-width /
  tag-character stego payloads survive.
- **verification** — the original flag checker: pick a garden from the
  dropdown, paste your `garden{...}` flag, and get pass/fail locally.

## Scripts

- `build_season1.py` — auto-discovers `s01cNN/challenge.txt` (or legacy
  `cNN/challenge.txt`) under `../gardens-ctf/` and injects the rendered blocks
  between the `<!-- SEASON1:BEGIN -->` / `<!-- SEASON1:END -->` markers in
  `output/index.html`. Idempotent; re-run when challenges are regenerated or
  added.

  ```
  python3 build_season1.py [--ctf /path/to/gardens-ctf] [--index /path/to/index.html]
  ```

- `add_garden_flag.py` — appends a new garden entry (name, salt, PBKDF2 hash)
  to the `GARDENS` list in `output/index.html`.

## Local preview

```
python3 -m http.server 8765 --directory output
```

Then open http://localhost:8765/ — `#season01` and `#verification` in the URL
select the tab.
