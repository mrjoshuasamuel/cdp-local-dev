## 2024-05-07 - Fix Rich Markup in Click Prompts
**Learning:** Standard `click` prompts (like `click.confirmation_option`) do not natively parse `rich` markup tags, resulting in literal markup tags (e.g. `[red]`) being rendered in the CLI output.
**Action:** Use plain text for `click` prompts to prevent literal markup tags from rendering, ensuring a clean and professional CLI interface.
