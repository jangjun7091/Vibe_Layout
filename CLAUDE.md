# Vibe_Layout Agent Contract

When a user request begins with `[Vibe_Layout]`, use Vibe Layout Viewer as the
canonical result surface.

Required flow:

1. Submit the prompt to the local Vibe Layout server with `POST /api/layouts`.
2. Read the JSON response.
3. Open `agent_action.url`, falling back to `viewer_url`, in the Claude Code
   browser preview.
4. Report the Viewer URL to the user.

If the browser is already at `/viewer#job_id=` or another Viewer URL without a
usable job id, call `GET /api/layouts/latest` and open the returned
`agent_action.url`.

Do not open `preview.png`, generated standalone `file://...viewer.html` files,
or raw artifacts as the primary result when a Viewer URL is available.
