## 2024-05-24 - Plain Text for Standard CLI Prompts
**Learning:** Standard `click` prompts (like `click.confirmation_option`) do not natively parse `rich` markup tags in this project, causing literal tags to be shown to the user, which clutters the UI.
**Action:** Always use plain text for `click` prompts to prevent literal markup tags from rendering in the CLI output.
