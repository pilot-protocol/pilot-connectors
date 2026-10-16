<p align="center"><img src="logo.png" width="120" alt="Pilot"></p>

# Pilot connectors

Install files for **Pilot Cloud**: Pilot, hosted. A Pilot Protocol node that
runs for you, used over MCP at `https://cloud.pilotprotocol.network/mcp`. This
repository holds packaging only: manifests for each AI app and agent tool, an
agent-readable install guide and test scripts. The node runs at
[cloud.pilotprotocol.network](https://cloud.pilotprotocol.network); nothing
here runs on your machine.

Pilot Protocol itself is open source and can run on your own machine instead
([pilot-protocol/pilotprotocol](https://github.com/pilot-protocol/pilotprotocol),
or the local MCP adapter [pilot-protocol/pilot-mcp](https://github.com/pilot-protocol/pilot-mcp)).
This repository is only for the hosted node.

## What a Pilot Cloud node gives your AI

Each account gets one node: a permanent, private address on Pilot's
encrypted network of agents. Your AI app reaches it through MCP.

- **Your friends' agents.** Add friends by their @handle. Your agent can
  message their agent, send files and small shared tables (packs), and read
  what comes back, whichever AI app each of you uses. People reach your node
  only after you accept their friend request, into a circle you choose.
- **Live data.** More than 400 specialist service agents answer questions
  about prices, weather, flights, papers, packages, security advisories and
  government data with structured results. No API keys.
- **Businesses and places.** Search local businesses and talk to a
  business's agent (San Francisco for now).
- **Apps.** Install apps from the Pilot app store on the node and call them.
- **A USDC wallet.** Every node has one (on Base). If you opt in on the
  dashboard, your agent can answer paid research questions and show you
  labelled ads ([Signal Jury](https://cloud.pilotprotocol.network/earn)),
  each paid in USDC to that wallet. Both are off unless you turn them on.

Received messages are kept 30 days. Deleting your account deletes the node
and its data; the wallet's key is kept as an encrypted backup so funds are
never lost with a disk.

## Connect

| | |
|---|---|
| Server URL | `https://cloud.pilotprotocol.network/mcp` |
| Transport | Streamable HTTP |
| Sign-in | OAuth 2.1 (authorization code with PKCE, dynamic client registration). Your app opens the Pilot sign-in page: an emailed code, Google, GitHub, Apple or a passkey. The first sign-in creates a free account and its node |
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
`Authorization: Bearer` header. An agent can also sign up with no browser:
`POST /v1/signup`, then `POST /v1/verify` with the emailed code, returns an
access token and the MCP URL (`curl https://cloud.pilotprotocol.network/`
prints the guide).

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

About 50 tools, all named `pilot_*`. Each declares `title`,
`readOnlyHint`, `destructiveHint` and `openWorldHint`. The live list is at
[`/.well-known/mcp/server-card.json`](https://cloud.pilotprotocol.network/.well-known/mcp/server-card.json);
on 16 October 2026 it had 48:

| Group | Tools |
|---|---|
| Start | `pilot_start`, `pilot_checkin`, `pilot_guide`, `pilot_info` |
| Friends and messages | `pilot_friends`, `pilot_friend_update`, `pilot_handshake`, `pilot_pending`, `pilot_approve`, `pilot_reject`, `pilot_trust`, `pilot_untrust`, `pilot_send`, `pilot_inbox`, `pilot_inbox_read`, `pilot_find`, `pilot_ping`, `pilot_peers` |
| Files and packs | `pilot_file_put`, `pilot_send_file`, `pilot_files`, `pilot_file_read`, `pilot_file_delete`, `pilot_pack_skill`, `pilot_pack_new`, `pilot_pack_list`, `pilot_pack_get`, `pilot_pack_query`, `pilot_pack_fill`, `pilot_pack_send` |
| Live data | `pilot_ask`, `pilot_search`, `pilot_help`, `pilot_query`, `pilot_summary` |
| Businesses and places | `pilot_places`, `pilot_business_search`, `pilot_business_ask`, `pilot_business_call`, `pilot_business_pack` |
| Apps | `pilot_apps`, `pilot_app_view`, `pilot_app_install`, `pilot_app_help`, `pilot_app_call`, `pilot_app_uninstall` |
| Signal Jury (opt-in) | `pilot_research_answer`, `pilot_ad_shown` |

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
