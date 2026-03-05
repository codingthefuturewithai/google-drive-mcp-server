---
description: Discover what this MCP server can do - tools, deployment options, and configuration
argument-hint: ""
allowed-tools: ["Read", "Grep", "Glob", "Bash", "AskUserQuestion"]
---

# Server Overview

Give the user a short, clear orientation to this MCP server — then let them guide the conversation.

## Instructions for AI Assistant

This is an **interactive overview**, not a report. Your job is to orient the user quickly, then have a conversation where they can explore what interests them. Do NOT dump everything you know upfront.

### Step 1: Quick Scan (do this silently before responding)

Read just enough to give an orientation:
- `pyproject.toml` — name, version, description
- `tools/__init__.py` or each `tools/*.py` file — count and names of tools
- `server/app.py` — transport options

### Step 2: Give a Brief Orientation

Write 3–5 sentences that answer: **What does this server do, and what can someone accomplish with it?**

Focus on outcomes, not implementation. Imagine explaining it to a developer who just cloned the repo and wants to know if this is the right tool for their job. Do NOT list every tool. Do NOT mention decorators, logging, or infrastructure unless directly relevant to what the server does.

Example tone (not template — synthesize from actual code):
> "This MCP server connects AI assistants to Google Drive. With it, an agent can search for files, browse folders, download documents to the local filesystem, upload new content, and manage files — moving, renaming, or deleting them. It handles all the OAuth and Google API complexity behind the scenes. Downloads and uploads go directly to the local filesystem so large files don't bottleneck the MCP protocol."

### Step 3: Ask What They Want to Explore

After the orientation, use `AskUserQuestion` to ask what the user wants to know more about. Keep the options short and meaningful — think about what someone actually wonders after hearing a brief overview.

Good options to offer (pick the ones that apply to this server):
- **The tools** — "Walk me through what each tool does"
- **How to set it up** — "How do I configure and run this?"
- **How to connect it** — "How do I wire this into my MCP client?"
- **How it handles files** — e.g., "How does the download/upload actually work?"
- **Something specific** — let them type their own question

### Step 4: Answer Their Question Conversationally

When the user picks an option or asks a question, **answer it like a knowledgeable teammate**, not like a reference doc. Be specific. Use concrete examples. If a concept might be unfamiliar (like "Drive API query syntax" or "export format"), briefly explain it — and invite follow-up questions at the end of your answer.

After each answer, ask: "Want to go deeper on any of this, or is there something else you'd like to know?"

### Rules

- **Never dump everything at once.** One topic per exchange.
- **Be concrete.** Instead of "you can search for files", say "you can search by filename, or use Drive query syntax like `mimeType='application/pdf' and modifiedTime > '2024-01-01'`".
- **Invite questions.** End each answer by opening the door for follow-up.
- **Read files on demand.** Don't pre-read infrastructure files you may never need. If the user asks about logging, read `log_system/` then. If they ask about Docker, read `scripts/docker.py` then.
- **Be honest about uncertainty.** If you're not sure how something works, say so and offer to look it up.
