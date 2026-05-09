## 2026-05-09 - Remove Rich formatting from standard Click prompts
**Learning:** Standard `click` prompts (like `click.confirmation_option`) do not natively parse `rich` markup tags in this CLI application, resulting in literal tags like `[red]` being displayed to the user.
**Action:** Use plain text for standard `click` prompts, or use `rich.prompt` if styled prompts are necessary.
