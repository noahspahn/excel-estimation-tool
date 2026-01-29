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

## Additional Comments

File: `additional_comments_prompt.txt`

Purpose: Generate the "Additional Comments" field from scraped RFP content.

### Placeholders
- `[PROJECT_NAME]`
- `[SITE_LOCATION]`
- `[GOV_POC]`
- `[FY]`
- `[SELECTED_MODULES]`
- `[SCRAPED_TEXT]`

### Usage (backend)

The API endpoint `POST /api/v1/comments/generate` loads the prompt file,
replaces placeholders, and sends the rendered prompt to ChatGPT.

### Notes
- Keep outputs concise (2-4 short sentences).
- Avoid pricing or hours.

## Security Protocols

File: `security_protocols_prompt.txt`

Purpose: Generate the "Security Protocols" field from scraped RFP content.

### Placeholders
- `[PROJECT_NAME]`
- `[SITE_LOCATION]`
- `[GOV_POC]`
- `[FY]`
- `[SELECTED_MODULES]`
- `[SCRAPED_TEXT]`

### Usage (backend)

The API endpoint `POST /api/v1/security-protocols/generate` loads the prompt file,
replaces placeholders, and sends the rendered prompt to ChatGPT.

### Notes
- Output should be a short comma-separated list.

## Compliance Frameworks

File: `compliance_frameworks_prompt.txt`

Purpose: Generate the "Compliance Frameworks" field from scraped RFP content.

### Placeholders
- `[PROJECT_NAME]`
- `[SITE_LOCATION]`
- `[GOV_POC]`
- `[FY]`
- `[SELECTED_MODULES]`
- `[SCRAPED_TEXT]`

### Usage (backend)

The API endpoint `POST /api/v1/compliance-frameworks/generate` loads the prompt file,
replaces placeholders, and sends the rendered prompt to ChatGPT.

### Notes
- Output should be a short comma-separated list.

## Subtask Module Guidance Prompts

Folder: `subtasks/`

Purpose: Provide module-specific guidance to make subtask definitions distinct and aligned
to the contract context.

### Files
- `DT.txt`
- `ITM.txt`
- `SA.txt`
- `CM.txt`
- `DA.txt`

### Placeholders
- `[MODULE_NAME]`
- `[MODULE_ID]`
- `[FOCUS_AREA]`
- `[FOCUS_LABEL]`
- `[TASK_TITLES]`
- `[CONTRACT_HIGHLIGHTS]`

### Usage (backend)

The AI subtask generator loads the prompt file matching the module focus area and
injects the rendered guidance into the model prompt.
