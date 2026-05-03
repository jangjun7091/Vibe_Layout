# Vibe_Layout Agent Contract

When a user request begins with `[Vibe_Layout]`, agents must treat Vibe Layout
Viewer as the canonical result surface.

## Required Flow

1. Submit the prompt to the local Vibe Layout server:
   `POST /api/layouts`
2. Read the JSON response.
3. Open `agent_action.url` or `viewer_url` inside the active agent browser
   surface:
   - Codex: open it in the Codex in-app browser.
   - Claude Code: open it in the Claude Code browser preview.
4. Report the Viewer URL to the user.

If the browser is already at `/viewer#job_id=` or another Viewer URL without a
usable job id, open `/viewer` with the known token or call `GET
/api/layouts/latest` and open the returned `agent_action.url`.

## Do Not

- Do not open `preview.png` as the primary result.
- Do not open generated standalone `file://...viewer.html` files.
- Do not show only GDS, PNG, or local HTML artifacts when a `viewer_url` is
  available.

The generated artifacts remain useful for download/export, but the user's
review surface is always Vibe Layout Viewer.
