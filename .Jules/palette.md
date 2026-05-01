## 2026-05-01 - Click Prompts Markup
**Learning:** Standard `click` prompts (like `click.confirmation_option`) do not natively parse `rich` markup tags. Using `[red]...[/red]` results in the literal tags being printed to the user.
**Action:** Use plain text for `click` prompts to prevent literal markup tags from rendering in the CLI output.