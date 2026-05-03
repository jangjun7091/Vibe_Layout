# Vibe_Layout Agent Contract

When a user request begins with `[Vibe_Layout]`, use Vibe Layout Viewer as the
canonical result surface.

Required flow:

1. Submit the prompt to the local Vibe Layout server with `POST /api/layouts`.
2. Read the JSON response.
3. Open `agent_action.url`, falling back to `viewer_url`, in the Claude Code
   browser preview.
4. Report the Viewer URL to the user.

Do not open `preview.png`, generated standalone `file://...viewer.html` files,
or raw artifacts as the primary result when a Viewer URL is available.
