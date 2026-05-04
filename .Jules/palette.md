## 2026-05-04 - Fix click confirmation prompt markup

**Learning:** `click` prompts (like `click.confirmation_option`) do not natively parse `rich` markup tags in this project; they render as literal text (e.g., `[red]...[/red]`), resulting in a poor user experience.

**Action:** Use plain text for `click` prompts to prevent literal markup tags from rendering in the CLI output.
