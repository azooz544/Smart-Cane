Prompt system — extend and localize

This repository includes a small prompt management system (`prompt_system.py`) that
centralizes the natural-language templates used by `gemini.py` (the Smart Cane app).

Files
- `prompt_system.py`: `PromptManager` class, template defaults, GUI editor, save/load API.
- `prompts.json`: persisted templates (created automatically on first run).

How to extend prompts
1. Edit the `prompts.json` file directly (safe and immediate). Each key contains language variants.
   Example:
   {
     "obstacle_detected": {
       "en": "You are... Ultrasonic distance={distance}.",
       "tr": "...",
       "ar": "..."
     }
   }
2. Or use the CLI API to edit programmatically:
   ```python
   from prompt_system import get_prompt_manager
   pm = get_prompt_manager()
   pm.edit_prompt('obstacle_detected', 'en', 'New template {distance}', save=True)
   ```
3. Or run the GUI editor (requires `tkinter`):
   ```python
   from prompt_system import get_prompt_manager
   pm = get_prompt_manager()
   pm.open_gui_editor()
   ```

Template variables
- `{distance}` — the ultrasonic distance in cm (or `unknown`)
- `{last_summary}` — a short string describing the last thing said
- `{question}` — when user asked a custom question

Localization tips
- Provide translations under the same key using the language code as subkeys, e.g., `"tr"` or `"ar"`.
- If a requested language is missing, the system falls back to English (`en`).

Previewing
- The GUI editor has a `Preview` button that attempts to speak a sample sentence using `pyttsx3`.
  If `pyttsx3` is not available it falls back to `gTTS`.

Notes
- `prompts.json` is written in UTF-8 so you can include non-Latin scripts.
- Keep templates short and concrete (the Smart Cane expects concise spoken guidance).
