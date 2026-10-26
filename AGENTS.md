# AGENTS.md — working notes for AI agents

Guidance for agents (and humans) modifying this repository. Read before changing
`core.py`, `gui.py`, the test suite or the CI workflow.

## What this project is

**entroPy** — a forensic entropy & randomness analyzer (Python 3.10+).
Memory-mapped statistical engine + PySide6 GUI that classifies files into
`Encrypted/Random`, `Compressed`, `Corrupted` or `Structured` using Shannon
entropy, Cramér's V, lag-1/lag-2 serial correlation and trend heuristics.

## Architecture map

| File | Role |
|---|---|
| `core.py` | Pure-NumPy engine: file metadata + hashes, global stats, windowed analysis, heuristic classifier, `report_to_dict()` JSON export, CLI (`python core.py <file> --json`). |
| `gui.py` | PySide6 front-end: multi-file queue in a `QThread` worker, pyqtgraph views, JSON export button. |
| `magic_signatures.json` | External file-signature table (~62 formats, `(offset, hex)` pairs, longer magics win). Loaded at runtime; a 15-format embedded fallback in `core.py` is used if it is missing/corrupt. |
| `tests/` | `test_core.py` (engine, heuristics, signatures, export, CLI) + `test_gui.py` (headless smoke; auto-skips when Qt cannot init). |
| `pyproject.toml` | Package metadata, `entroPy` console script, `[dev]` extra (pytest). |
| `.github/workflows/ci.yml` | Matrix: Linux/macOS/Windows × Python 3.10/3.13. |

## Invariants — do not regress

1. **Performance**: windowed histograms use a *single* `np.bincount` with a
   per-block offset (no 256-pass equality loops); serial/pair correlations use
   streaming two-pass reductions over 4 MiB chunks (O(1) peak memory). Keep it
   that way — these were deliberate ~35× fixes.
2. **`.gitignore` must NOT ignore `tests/`** — a stale rule did this once and
   silently broke CI (pytest collected zero tests).
3. **Format-name strings are a test contract**: tests assert exact names
   returned by `identify_file_format()`. Change a name in
   `magic_signatures.json` and update `tests/test_core.py` in the same commit.
   `magic_signatures.json` must stay valid JSON; entries must be safe when
   malformed (parser drops bad entries, never raises).
4. **No new hard dependencies**: runtime is `numpy`, `PySide6`, `pyqtgraph`
   only. GUI tests must skip gracefully (not fail) where Qt cannot initialize.
5. **Thread hygiene**: `gui.py` rejects overlapping analysis requests via
   `_is_idle()`; the worker isolates per-file errors in a queue.

## Testing & CI

```bash
pip install -e ".[dev]"
QT_QPA_PLATFORM=offscreen python -m pytest -q   # 54 tests
```

GUI tests need system EGL/GL libs on bare Linux (`libegl1 libgl1 libxkbcommon0
libdbus-1-3 libfontconfig1 libglib2.0-0`); the workflow installs them, and
`tests/test_gui.py` module-level-skips when PySide6 can't init.

## Publishing (GitHub)

Remote: `https://github.com/cuarentaysiete/entroPy.git` (branch `main`).
No credentials are stored in this repo or in `.git/config`. To push, ask the
user for a **fresh PAT with `repo` + `workflow` scopes** (the `workflow`
scope is mandatory — GitHub rejects PAT pushes that add/modify
`.github/workflows/`), use it inline in the push URL only, and ask the user
to revoke it afterwards.

## Current state

- Suite: 54 tests, all passing; CI matrix 6/6 green.
- Engine: lag-1 *and* lag-2 serial correlation (the lag-2 pair metric exposes
  alternating two-byte periodicity).
- GUI: multi-file queue with per-file progress, per-file error isolation and
  one-click JSON report export.
