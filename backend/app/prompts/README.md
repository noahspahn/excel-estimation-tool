# Prompts

This folder contains editable prompt templates used by the backend to transform scraped RFP text into structured report inputs.

## Additional Assumptions

File: `additional_assumptions_prompt.txt`

Purpose: Generate the "Additional Assumptions" section from scraped RFP content.

### Placeholders
- `[PROJECT_NAME]`
- `[SITE_LOCATION]`
- `[GOV_POC]`
- `[FY]`
- `[SELECTED_MODULES]`
- `[SCRAPED_TEXT]`

### Usage (backend)

The API endpoint `POST /api/v1/assumptions/generate` loads the prompt file,
replaces placeholders, and sends the rendered prompt to ChatGPT.

### Notes
- Keep outputs short and assumptions-focused (no pricing or hours).
- If you change the prompt format (e.g., remove SYSTEM/USER blocks), update the parsing logic in `backend/app/services/ai_service.py`.
