## 2026-04-27 - click.confirmation_option UI feedback
**Learning:** Standard click prompts (like `click.confirmation_option`) do not natively parse `rich` markup tags in this CLI application. If markup is included, it gets printed literally (e.g. "[red]Text[/red]"), making the UI look broken and unpolished.
**Action:** When working with click's built-in confirmation prompts or other click-specific input methods, ensure they use plain text to avoid literal rendering of markup tags.
