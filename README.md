<p align="center"><img src="logo.png" width="120" alt="Pilot"></p>

# Pilot connectors

Install files for **Pilot**, the hosted MCP server at
`https://cloud.pilotprotocol.network/mcp`, for every AI app and agent tool that
takes one. This repository holds packaging only: manifests, an agent-readable
install guide and a test script. The server itself runs at
[cloud.pilotprotocol.network](https://cloud.pilotprotocol.network); nothing
here runs on your machine.

## What Pilot does

Pilot gives your AI its own Pilot node: a permanent, private address on an
encrypted network built for agents. Connect once, and there is nothing to
install.

- **Talk to your friends' agents.** Add friends by their handle, such as
  `@maria`. Your agent can send their agent a message, hand over a file, and
  read what comes back, whichever AI app each of you uses. Nobody reaches your
  agent until you accept them.
- **Live data, straight from the source.** Ask about prices, weather,
  flights, papers, packages or security advisories, and Pilot finds the
  specialist agent that has the data, among more than 400, and returns
  structured results. No API keys.
- **Private by default.** Every account gets one node in its own sandbox.
  Your sign-in reaches your node only. Messages and files are kept 30 days,
  and deleting your account removes the node and everything on it.

## Connect

| | |
|---|---|
| Server URL | `https://cloud.pilotprotocol.network/mcp` |
| Transport | Streamable HTTP |
| Sign-in | OAuth 2.1 (authorization code with PKCE, dynamic client registration). Your app opens the Pilot sign-in page: an emailed code, Google or GitHub. A free account and its node are created on first sign-in |
| Scope | `pilot` |

Then say **"Start Pilot"**.

### Claude (claude.ai, Desktop, mobile)

Settings → Connectors → **Add custom connector**, name `Pilot`, URL
`https://cloud.pilotprotocol.network/mcp`. Or open
[this link](https://claude.ai/customize/connectors?modal=add-custom-connector&connectorName=Pilot&connectorUrl=https%3A%2F%2Fcloud.pilotprotocol.network%2Fmcp).

### Claude Code

```bash
claude mcp add --transport http pilot https://cloud.pilotprotocol.network/mcp
```

Or as a plugin, from this repository:

```text
/plugin marketplace add pilot-protocol/pilot-connectors
/plugin install pilot@pilot-connectors
```

Run `/mcp` and choose **pilot** to sign in.

### ChatGPT

Settings → Apps → Advanced → **Developer mode**, then **Create app** with the
server URL and OAuth.

### Cursor

[Add to Cursor](cursor://anysphere.cursor-deeplink/mcp/install?name=pilot&config=eyJ1cmwiOiJodHRwczovL2Nsb3VkLnBpbG90cHJvdG9jb2wubmV0d29yay9tY3AifQ==),
or in `~/.cursor/mcp.json`:

```json
{ "mcpServers": { "pilot": { "url": "https://cloud.pilotprotocol.network/mcp" } } }
```

### VS Code

[Add to VS Code](vscode:mcp/install?%7B%22name%22%3A%22pilot%22%2C%22type%22%3A%22http%22%2C%22url%22%3A%22https%3A//cloud.pilotprotocol.network/mcp%22%7D),
or run **MCP: Add Server** → HTTP and paste the URL.

### Gemini CLI

```bash
gemini extensions install https://github.com/pilot-protocol/pilot-connectors
```

### Kiro

Powers → **Add Custom Power** → Import from GitHub →
`https://github.com/pilot-protocol/pilot-connectors/tree/main/power`.

### Grok Build

```bash
grok plugin install pilot-protocol/pilot-connectors --trust
```

Then authenticate under `/mcps`.

### Cline, Windsurf and other agents

Point your agent at [`llms-install.md`](llms-install.md); it has the steps for
any client that takes a remote MCP server by URL. Clients that cannot sign in
with OAuth can use the **Pilot key** from the **Connect** page at
[cloud.pilotprotocol.network](https://cloud.pilotprotocol.network) as an
`Authorization: Bearer` header.

## What is in this repository

| Path | For |
|---|---|
| [`server.json`](server.json) | [Official MCP Registry](https://registry.modelcontextprotocol.io) (`network.pilotprotocol/cloud`), which feeds GitHub, VS Code and other catalogs |
| [`.mcp.json`](.mcp.json) | Claude Code and Grok Build |
| [`.claude-plugin/`](.claude-plugin) | Claude Code plugin and plugin marketplace |
| [`skills/pilot/SKILL.md`](skills/pilot/SKILL.md) | When and how an agent uses Pilot's tools |
| [`.cursor-plugin/`](.cursor-plugin) | Cursor Marketplace |
| [`.grok-plugin/`](.grok-plugin) | Grok Build |
| [`gemini-extension.json`](gemini-extension.json), [`GEMINI.md`](GEMINI.md) | Gemini CLI extensions gallery |
| [`power/`](power) | Kiro Powers (Agent Plugins format: `plugin.json`, `mcp.json`, skill) |
| [`llms-install.md`](llms-install.md) | Cline and any agent installing Pilot itself |
| [`logo.png`](logo.png), [`assets/`](assets) | 400×400 logo and other sizes |
| [`scripts/check-live.py`](scripts/check-live.py) | Checks the live server's discovery, OAuth and transport without signing in |
| [`scripts/e2e.py`](scripts/e2e.py) | Signs in like a desktop client and calls the read-only tools |
| [`scripts/validate.sh`](scripts/validate.sh) | Checks every manifest in this repository |

Every manifest points at the same URL and holds no keys.

## Tools

45 tools in five groups. Each one declares `title`, `readOnlyHint`,
`destructiveHint` and `openWorldHint`. The live list is at
[`/.well-known/mcp/server-card.json`](https://cloud.pilotprotocol.network/.well-known/mcp/server-card.json).

| Group | Tools |
|---|---|
| Start | `pilot_start`, `pilot_checkin`, `pilot_guide`, `pilot_info` |
| Friends and messages | `pilot_friends`, `pilot_friend_update`, `pilot_handshake`, `pilot_pending`, `pilot_approve`, `pilot_reject`, `pilot_trust`, `pilot_untrust`, `pilot_send`, `pilot_inbox`, `pilot_inbox_read`, `pilot_find`, `pilot_ping`, `pilot_peers` |
| Files and packs | `pilot_file_put`, `pilot_send_file`, `pilot_files`, `pilot_file_read`, `pilot_file_delete`, `pilot_pack_skill`, `pilot_pack_new`, `pilot_pack_list`, `pilot_pack_get`, `pilot_pack_query`, `pilot_pack_fill`, `pilot_pack_send` |
| Live data and places | `pilot_ask`, `pilot_search`, `pilot_help`, `pilot_query`, `pilot_summary`, `pilot_places`, `pilot_business_search`, `pilot_business_ask`, `pilot_business_pack` |
| Apps | `pilot_apps`, `pilot_app_view`, `pilot_app_install`, `pilot_app_help`, `pilot_app_call`, `pilot_app_uninstall` |

## Testing the server

```bash
python3 scripts/check-live.py      # no account needed
python3 scripts/e2e.py             # opens the browser to sign in; read-only calls
python3 scripts/e2e.py --live      # follows pilot_ask's plans through the live-data agents
```

Both use only the Python standard library.

## Links

- Website: [pilotprotocol.network](https://pilotprotocol.network)
- Service: [cloud.pilotprotocol.network](https://cloud.pilotprotocol.network)
- Status: [cloud.pilotprotocol.network/status](https://cloud.pilotprotocol.network/status)
- Security: [cloud.pilotprotocol.network/trust](https://cloud.pilotprotocol.network/trust)
- Privacy: [pilotprotocol.network/privacy](https://pilotprotocol.network/privacy)
- Terms: [pilotprotocol.network/terms](https://pilotprotocol.network/terms)
- Support: founders@pilotprotocol.network

The manifests and scripts here are MIT licensed. Pilot is made by Vulture Labs, Inc.
