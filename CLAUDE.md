# Arya project notes for Ruflo-enabled coding agents

## Project facts
- Arya is a Python + Gradio web assistant.
- Main entry point: `app.py`.
- Dependencies: `requirements.txt`.
- Render deployment config: `render.yaml`.
- The current model provider is OpenRouter, configured with environment variables.

## Safety and implementation rules
- Do not commit API keys, OAuth client secrets, access tokens, or `.env` files.
- Keep Google Drive OAuth tokens and all owner-only memory server-side. Never expose them to the browser.
- Preserve owner-only access. Do not remove authentication or make private memory public.
- Before editing, inspect the current files and avoid replacing unrelated project behavior.
- Keep Render's Python start command compatible with `python app.py` unless deployment is intentionally migrated.
- Test syntax and dependencies before proposing a change. If a test cannot be run, say so clearly.
- Make changes in a separate branch and use a pull request when possible; do not force-push to `main`.

## Important architecture boundary
Ruflo's MCP server is a developer/agent tool. This config connects an MCP-capable coding client to Ruflo; it does not embed Ruflo into the deployed Arya website. Runtime multi-agent behavior in Arya requires a separate backend design and explicit provider/API configuration.
