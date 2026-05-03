## 2024-05-03 - Click Prompts and Rich Markup Compatibility
**Learning:** `click`'s native prompt options (like `confirmation_option`) do not process `rich` console markup tags, causing them to render literally as `[red]text[/red]` in the terminal.
**Action:** Use plain text for `click` native prompts to prevent literal markup display.
