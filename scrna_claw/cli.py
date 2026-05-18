"""Package-level CLI entrypoint for ScrnaClaw."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path


def _iter_cli_path_candidates() -> list[Path]:
    """Return candidate paths for the top-level ``scrna_claw.py`` launcher."""
    candidates: list[Path] = []

    # 1) Standard source/editable layout: <repo>/scrna_claw/cli.py -> <repo>/scrna_claw.py
    candidates.append(Path(__file__).resolve().parent.parent / "scrna_claw.py")

    # 2) Optional explicit override.
    env_path = os.environ.get("SCRNA_CLAW_CLI_PATH", "").strip()
    if env_path:
        candidates.append(Path(env_path).expanduser().resolve())

    # 3) Search from current working directory upwards (non-editable install
    #    but user is running `oc` inside a cloned ScrnaClaw repo).
    cwd = Path.cwd().resolve()
    for base in (cwd, *cwd.parents):
        candidates.append(base / "scrna_claw.py")

    # Deduplicate while preserving order.
    uniq: list[Path] = []
    seen: set[str] = set()
    for p in candidates:
        key = str(p)
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    return uniq


def _discover_cli_path() -> Path:
    for p in _iter_cli_path_candidates():
        if p.exists() and p.is_file():
            return p

    tried = "\n".join(f"  - {p}" for p in _iter_cli_path_candidates())
    raise FileNotFoundError(
        "Could not locate 'scrna_claw.py' launcher.\n"
        "Tried:\n"
        f"{tried}\n\n"
        "If you are using a source checkout, run `oc` from inside the ScrnaClaw repo,\n"
        "or set SCRNA_CLAW_CLI_PATH to the absolute path of scrna_claw.py."
    )


def main() -> None:
    """Load and run the repository-root ``scrna_claw.py`` CLI."""
    cli_path = _discover_cli_path()
    spec = importlib.util.spec_from_file_location("scrna_claw_main", cli_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load CLI module from {cli_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main()
