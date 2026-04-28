## 2024-05-18 - Click Prompt Rich Tag Limitation
**Learning:** Standard `click` prompts (like `click.confirmation_option`) do not natively parse `rich` markup tags in this project. They print the tags literally, creating a confusing UX for the user.
**Action:** Use plain text instead of rich tags inside `click.confirmation_option` and other `click` built-in prompt text.
