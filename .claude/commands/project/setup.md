---
description: Complete guided setup — go from a fresh clone to Google Drive tools working in your AI client
argument-hint: ""
allowed-tools: ["Bash", "Read", "AskUserQuestion", "WebSearch"]
---

# Google Drive MCP Server — Complete Setup

Guide the user from a fresh clone to a working server. Be a knowledgeable teammate — proactive, concrete, one step at a time. When something goes wrong, you investigate and fix it. Never tell the user to go look something up themselves.

## Hard Rules — Never Violate

- **Never run `scripts/setup.py` or `scripts/add_account.py`** — these are interactive scripts that require the user to be at their terminal. Tell them to run it; wait for them to report back.
- **Never read, copy, move, or inspect any credential files** — this includes `client_secret*.json`, `token*.json`, and anything in the `tokens/` directory. These are secrets. You have no business touching them.
- **Bash is for diagnostics only** — use it to check Docker status, read logs, verify ports, confirm commands ran. Never use it to execute setup steps on the user's behalf.

---

## Phase 1 — Prerequisites

Check silently, report only what needs attention.

**Python 3.11+:**
```bash
python3 --version || python --version
```
If missing or too old: macOS → `brew install python@3.12`; Linux → `sudo apt install python3.12`; Windows → python.org installer (check "Add to PATH").

**uv:**
```bash
uv --version
```
If missing: macOS/Linux → `curl -LsSf https://astral.sh/uv/install.sh | sh`; Windows → `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`. They may need a new terminal after install.

**Docker:**
```bash
docker --version && docker ps
```
If not installed: docker.com/get-started. If installed but `docker ps` fails: Docker daemon isn't running — open Docker Desktop (macOS/Windows) or `sudo systemctl start docker` (Linux).

**Project dependencies:**
```bash
uv sync
```
Fix any errors before continuing.

---

## Phase 2 — Google Cloud Console

This is the only part the user has to do manually — there's no way to automate it. Walk them through it one screen at a time. Wait for confirmation at each step before moving to the next.

**Ask first:** "What kind of Google account will you be connecting — personal Gmail, or a Google Workspace / corporate account?" Save the answer — it affects troubleshooting guidance later.

### Create or select a Google Cloud project

Send them to: `https://console.cloud.google.com/projectcreate`

- Project name: suggest `google-drive-mcp`
- Organization: leave as-is
- Click **Create**, wait for it to be ready
- Confirm the project name shows in the top bar

If they already have a project to reuse, that's fine — just confirm it's selected.

### Enable the Google Drive API

Send them to: `https://console.cloud.google.com/apis/library/drive.googleapis.com`

- **Enable** button → click it, wait for confirmation
- **Manage** button → already enabled, move on
- Something else → search the web for current steps, adapt

### Configure the OAuth Consent Screen

Send them to: `https://console.cloud.google.com/apis/credentials/consent`

Ask what they see. If they see Internal / External, choose **External** — Internal restricts auth to users within their own Workspace org, which is too narrow even for personal use. If the screen looks different, search the web for the current flow.

Required fields only:
- App name: `Google Drive MCP Server`
- User support email: their email
- Developer contact: their email

Click **Save and Continue** through the remaining screens (Scopes, Test Users, Summary) — no changes needed.

If they're on a Workspace account: note that their admin may need to approve the app. If that comes up, we'll handle it when it happens.

### Create the OAuth Client ID

Send them to: `https://console.cloud.google.com/apis/credentials`

Click **+ Create Credentials → OAuth client ID**:
- Application type: **Desktop app** — this is required. The server runs locally and uses a local browser redirect. Choosing Web application will cause a `redirect_uri_mismatch` error.
- Name: `Google Drive MCP`
- Click **Create**

In the dialog that appears, click **Download JSON**. The file saves to their Downloads folder automatically.

Confirm they see the file in Downloads before moving on.

---

## Phase 3 — Run Setup

Tell the user to open their terminal, navigate to the repo root, and run:

```bash
python scripts/setup.py
```

**Do not run this yourself.** It requires interactive input at the terminal — browser sign-in, prompts for port/directory/mounts. Tell them to run it and report back with what they see. If something goes wrong, they paste the error and you diagnose from there.

**What they'll be walked through — explain each step before they hit it:**

**Credentials:** The script checks their Downloads folder and shows any `client_secret*.json` files it finds, asking "Is this your Google credentials file?" for each one. If they confirm, it copies it automatically. If nothing was found in Downloads, or none of them are right, it asks them to enter the path manually. Tip for users who don't know the path: drag the file from their file manager into the terminal window — that pastes the path.

**Google sign-in:** Browser opens automatically.
- Sign in with the Google account whose Drive they want to access
- They may see **"Google hasn't verified this app"** — this is normal for self-hosted tools. Click **Advanced → Go to Google Drive MCP Server (unsafe)**. "Unsafe" just means Google hasn't reviewed it in their marketplace — they created these credentials themselves.
- Click **Allow**
- Browser shows success, terminal continues automatically

**Additional accounts:** The script asks if they want to add more Google accounts. For each one: browser opens again, sign in, done. They can add as many as they want, or skip and add more later with `python scripts/add_account.py`.

**Port:** Accept the default unless they know port 19001 is already in use.

**Download directory:** Where files downloaded from Drive will land locally. Accept the default (`~/Downloads/google_drive`) or enter a custom path.

**Directory mounts:** Which local directories the server can read when uploading files to Drive. Mounting the home directory (read-only) covers everything. They can add more specific directories if preferred.

**Build and launch:** The script builds the Docker image (takes a minute the first time), copies credentials into the container, starts the server, and waits for it to be healthy. No input needed.

**End of script:** Setup prints the exact `claude mcp add` command. They copy and run it.

---

## Troubleshooting during setup.py

**Client secret file not found:** The file isn't in Downloads, Desktop, Documents, or home. Ask them where they downloaded it. The script offers a custom path option.

**Browser doesn't open:** SSH session or headless machine. The terminal will print a URL — open it in any browser, authorize, come back.

**"Access blocked" — Workspace account:** Their admin has restricted third-party OAuth apps. The admin goes to: Google Admin Console → Security → API Controls → App Access Control → find the OAuth Client ID → mark as **Trusted**. Offer to draft the message they can send their admin.

**`redirect_uri_mismatch`:** Wrong application type — Web app instead of Desktop app. They need to go back to the Credentials page, create a new OAuth client ID with **Desktop app** type, download it, and re-run setup.

**Docker build fails:** Read the error. Common causes: Docker daemon stopped mid-build (restart it), disk space issue, network error pulling base image.

**Port conflict:** Another process is using the default port. The script finds the next available port automatically. If `GOOGLE_DRIVE_PORT` env var is set, it uses that.

**If Google's UI has changed:** Search `"Google Cloud Console" [what they're trying to do] site:cloud.google.com` — find the current steps, tell the user exactly what to click. Never send them to search themselves.

---

## Phase 4 — Register and Verify

Setup prints the `claude mcp add` command at the end. Have them run it:

```bash
claude mcp add google-drive --transport http http://localhost:[PORT]/mcp --scope user
```

The `--scope user` flag registers the server globally for your user account, so it's available in every project — not just the one you're in right now. This is almost always what you want for a general-purpose tool like Google Drive.

Verify it registered:
```bash
claude mcp list
```

Then confirm end-to-end: ask them to start a new Claude Code session and try asking "List the contents of my Google Drive root folder." They should see their actual Drive files.

**If the tool doesn't appear in a new session:**
- Confirm `claude mcp list` shows `google-drive`
- Check the container is still running: `python scripts/docker.py status`
- Check logs for startup errors: `python scripts/docker.py logs`

**If authentication fails mid-call:**
- Run `python scripts/setup.py --force` to redo the credentials step

Tell them when they're done:

> "You're set. The server runs as a Docker container and restarts automatically. Your Google auth tokens refresh silently — you won't need to re-authenticate. To add another Google account later, ask me to help with that. Use `python scripts/docker.py status` to check on it anytime."
