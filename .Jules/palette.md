## 2024-06-25 - Standard Click Prompts vs Rich Markup
**Learning:** Standard `click` prompts like `click.confirmation_option` do not natively parse `rich` markup tags in this project; they render them as literal strings, resulting in a poor user experience.
**Action:** Use plain text for standard `click` prompts, or implement custom prompt logic that integrates with `rich.prompt.Confirm` if rich markup is strictly necessary.
