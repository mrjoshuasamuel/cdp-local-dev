## 2024-05-08 - Click confirmation prompts and Rich markup
**Learning:** Standard `click` prompts (like `click.confirmation_option`) do not natively parse `rich` markup tags in this project. Using tags like `[red]...[/red]` will result in the literal tags being rendered in the CLI output.
**Action:** Use plain text for `click` prompts to prevent literal markup tags from rendering, or investigate overriding the prompt mechanism to integrate with `rich` if stylized prompts are strictly required.
