## 2025-03-01 - Fix literal rich tags in click prompts
**Learning:** Standard `click` prompts (like `click.confirmation_option`) do not natively parse `rich` markup tags in this project. Using tags like `[red]` results in the literal text being displayed to the user.
**Action:** When creating CLI prompts, use plain text in the prompt string to prevent literal markup tags from rendering in the output, ensuring a clean and professional UX.
