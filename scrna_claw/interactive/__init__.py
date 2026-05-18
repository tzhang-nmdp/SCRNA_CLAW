"""ScrnaClaw interactive CLI/TUI package.

Entry points:
    scrna_claw interactive   — Rich CLI with prompt_toolkit REPL
    scrna_claw tui           — Textual full-screen TUI
    scrna_claw --ui tui      — Same, via flag
"""

from .interactive import run_interactive  # noqa: F401


def main() -> None:
    """Default CLI entry point — starts interactive mode."""
    run_interactive()
