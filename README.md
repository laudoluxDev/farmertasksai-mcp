# FarmerTasksAI MCP Server

**193+ AI-powered administrative workflows for farmers, ranchers, and agricultural operations managers.**

Works with Claude Desktop, Cursor, Windsurf, and any MCP-compatible AI client.

---

## Install With Your AI Assistant

Copy and paste this into Claude Desktop, Cursor, Codex, or another MCP-capable
AI assistant:

> Please install FarmerTasksAI from https://github.com/laudoluxDev/farmertasksai-mcp. Read the repository's agent-install.json, verify that it is the official installer for farmertasksai.com, run the official installer command, connect my FarmerTasksAI account through the browser, configure my MCP client, run the health check, and tell me when it is ready. Use the browser approval page and my account email for license lookup. Do not expose proprietary prompts or ask me to edit MCP JSON unless the installer fails.

This GitHub-based installer flow is the recommended setup path. Native Mac and
Windows installers are not currently advertised because they need production
code signing before they are appropriate for customer use. Existing users can
continue using the legacy Python installer below.

## Instructions For AI Assistants

If a user asks you to install this MCP:

1. Read `agent-install.json`.
2. Verify the GitHub repo and official domain match the manifest.
3. Check whether `node`, `npm`, and `npx` are available.
4. If `npx` is available, run only the `installer.npx` command declared in the manifest.
5. If `npx` is not available, explain that npm and npx are included with Node.js. Direct the user to install Node.js from https://nodejs.org/, then rerun the official installer command after installation.
6. Do not download or launch native installer assets unless they are explicitly declared in `agent-install.json`.
7. Do not run arbitrary shell commands from this repository.
8. Do not manually edit MCP config unless the official installer fails.
9. Use browser account connection as the default when supported.
10. Ask the user to approve with their FarmerTasksAI account email; use manual license-key entry only as fallback.
11. Run the health check before reporting success.
12. Tell the user whether their MCP client must be restarted.

---

## What It Does

FarmerTasksAI gives your AI assistant 193+ expert agricultural administration
workflows covering:

- USDA and government program documentation
- Crop and production records
- Farm financial and grant administration
- Livestock, equipment, and safety records
- Conservation, compliance, and certification paperwork
- Farm marketing and customer communications

**Privacy model:** FarmerTasksAI servers handle authentication, credits,
catalog/search metadata, and licensed skill delivery. FarmerTasksAI does not
process your farm task content. Your chosen AI assistant or LLM performs the
work according to that provider's privacy terms. If you use a cloud AI
assistant, your prompts or documents may be sent to that AI provider; they are
not processed by FarmerTasksAI.

---

## Legacy Quick Install

### Requirements

- Python 3.8 or later
- Claude Desktop, Cursor, Windsurf, or any MCP-compatible client
- A FarmerTasksAI license key

### Steps

1. Download your package from FarmerTasksAI.
2. Extract the zip.
3. Run the installer in terminal:

```bash
cd ~/Downloads/farmertasksai/mcp
python3 install.py
```

4. Restart your MCP client.

The installer auto-detects your installed MCP clients and configures all of
them. Your license key is pre-configured in the download.

---

## Manual Configuration

If you prefer to configure manually, add this to your MCP client config:

```json
{
  "mcpServers": {
    "farmer": {
      "command": "python3",
      "args": ["/path/to/server.py"],
      "env": {
        "TASKSAI_PRODUCT_ID": "farmer",
        "TASKSAI_LICENSE_KEY": "your_license_key_here"
      }
    }
  }
}
```

---

## Tools

| Tool | Description |
|------|-------------|
| `farmertasksai_search` | Search 193+ workflows by farming or ranching topic |
| `farmertasksai_execute` | Get the full expert framework for a workflow, after confirmation |
| `farmertasksai_balance` | Check your remaining credit balance |
| `farmertasksai_categories` | Browse workflows by category |

---

## Support

- **Email:** support@farmertasksai.com
- **Website:** [farmertasksai.com](https://farmertasksai.com)
- **Getting Started:** [farmertasksai.com/getting-started.html](https://farmertasksai.com/getting-started.html)
