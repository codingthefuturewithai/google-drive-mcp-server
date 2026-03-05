---
description: Complete guided setup — go from a fresh clone to Google Drive tools working in your AI client
argument-hint: ""
allowed-tools: ["Bash", "Read", "AskUserQuestion", "WebSearch"]
---

# Google Drive MCP Server — Complete Setup

Guide the user from a fresh clone to a working server. Be a knowledgeable teammate — proactive, concrete, one step at a time. When something goes wrong, you investigate and fix it. Never tell the user to go look something up themselves.

---

## What setup.py does (know this cold)

`python scripts/setup.py` handles everything after the Google Console steps:

1. Checks Docker is running
2. Searches the user's Downloads, Desktop, Documents, and home folder for a `client_secret*.json` file and presents a numbered list — user picks one, no path typing required
3. Copies it to the correct platform-specific config directory automatically
4. Opens the browser for Google sign-in — automatically, no separate command
5. Asks about port, download directory, and which local directories to mount
6. Builds the Docker image, copies credentials into the container volume, starts the container, and waits for healthy
7. Prints the exact `claude mcp add` command to run

The user runs one script. The only thing left after it finishes is running the printed `claude mcp add` command.

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

In the dialog that appears, click **Download JSON**. The file will be named something like `client_secret_XXXXXXXX.apps.googleusercontent.com.json`.

Confirm they have the file in their Downloads folder before moving on.

---

## Phase 3 — Run Setup

Tell the user:

> "From here, one script handles everything — it will find your downloaded file automatically, open your browser for Google sign-in, configure Docker, build the image, and start the server. You just answer a few questions."

```bash
python scripts/setup.py
```

Walk them through what to expect at each prompt:

**Step 1 — Docker check:** Confirms Docker is running. If it fails, Docker Desktop isn't open.

**Step 2 — Google Credentials:** The script will find the `client_secret*.json` file in Downloads and show a numbered list. They press `1` and Enter. Then their browser opens automatically for Google sign-in:
- Sign in with the Google account whose Drive they want to access
- They may see **"Google hasn't verified this app"** — this is normal for self-hosted tools. Click **Advanced → Go to Google Drive MCP Server (unsafe)**. "Unsafe" just means Google hasn't reviewed it in their marketplace — they created these credentials themselves.
- Click **Allow**
- Browser shows success, terminal continues automatically

**Steps 3–5 — Port, download directory, directory mounts:** Accept the defaults or adjust as needed. Mounting the home directory (read-only) is recommended if they'll be uploading files from anywhere on their machine.

**Step 6 — Build and launch:** The script builds the Docker image (takes a minute the first time), copies credentials into the container, starts the server, and waits for it to be healthy. No input needed.

**End of script:** Setup prints the exact `claude mcp add` command with the correct port. They copy and run that one command.

---

## Troubleshooting during setup.py

**Client secret file not found in the numbered list:** The file isn't in Downloads, Desktop, Documents, or home. Ask them where they downloaded it. They can enter a custom path when the script offers that option.

**Browser doesn't open:** SSH session or headless machine. The terminal will print a URL — open it in any browser, authorize, come back.

**"Access blocked" — Workspace account:** Their admin has restricted third-party OAuth apps. The admin goes to: Google Admin Console → Security → API Controls → App Access Control → find the OAuth Client ID → mark as **Trusted**. Offer to draft the message they can send their admin.

**`redirect_uri_mismatch`:** Wrong application type was chosen — Web app instead of Desktop app. They need to go back to the Credentials page, create a new OAuth client ID with **Desktop app** type, download it, and re-run setup.

**Docker build fails:** Read the error. Common causes: Docker daemon stopped mid-build (restart it), disk space issue, network error pulling base image.

**Port conflict:** Another process is using the default port. The script will find the next available port automatically. If `GOOGLE_DRIVE_PORT` env var is set, it uses that.

**If Google's UI has changed:** Search `"Google Cloud Console" [what they're trying to do] site:cloud.google.com` — find the current steps, tell the user exactly what to click. Never send them to search themselves.

---

## Phase 4 — Register and Verify

Setup prints the `claude mcp add` command at the end. Have them run it:

```bash
claude mcp add google-drive --transport http http://localhost:[PORT]/mcp
```

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

> "You're set. The server runs as a Docker container and restarts automatically. Your Google auth token refreshes silently — you won't need to re-authenticate. Use `python scripts/docker.py status` to check on it anytime."
