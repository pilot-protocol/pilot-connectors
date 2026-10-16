# Installing Pilot Cloud (for AI agents)

Pilot Cloud is Pilot, hosted: a Pilot Protocol node that runs for the person,
used over MCP. There is nothing to download, build or run: add one remote
server by URL and let the person sign in.

## Server

- Name: `pilot`
- URL: `https://cloud.pilotprotocol.network/mcp`
- Transport: Streamable HTTP (in configs: `"type": "streamableHttp"`, `"type": "http"` or `"transport": "http"`, whichever your client uses)
- Auth: OAuth 2.1. The server answers an unauthenticated request with `401`
  and a `WWW-Authenticate` header pointing at its metadata; clients that
  support MCP OAuth discover everything from there (dynamic client
  registration, PKCE S256, scope `pilot`). No client ID or secret needs to
  be configured.

## Steps

1. Add the server to the client's MCP configuration. For Cline, in
   `cline_mcp_settings.json`:

   ```json
   {
     "mcpServers": {
       "pilot": {
         "type": "streamableHttp",
         "url": "https://cloud.pilotprotocol.network/mcp"
       }
     }
   }
   ```

   Other clients use the same URL under their own key, for example
   `"serverUrl"` in Windsurf's `mcp_config.json` or `"url"` in Cursor's
   `mcp.json`.

2. Start the connection. The client opens a browser window at
   `https://cloud.pilotprotocol.network/oauth/authorize`. Ask the person to
   sign in (an emailed six-digit code, Google, GitHub, Apple or a passkey) and to approve the
   connection. A free account and its Pilot node are created on first
   sign-in; the node can take up to a minute to start.

3. Check it works: list the server's tools (about 50, all named `pilot_*`)
   and call `pilot_info`. It returns the node's address.

4. Tell the person they can now say "Start Pilot".

## If the client cannot do OAuth

Either way gives a bearer token for the same node.

- **The Pilot key.** Ask the person to open https://cloud.pilotprotocol.network,
  sign in, and copy the **Pilot key** from the **Connect** page.
- **Sign up from the agent, no browser.** `POST https://cloud.pilotprotocol.network/v1/signup`
  with `{"email": "<their email>"}` emails them a six-digit code; ask them for
  it, then `POST /v1/verify` with `{"email", "code", "label": "<this client>"}`.
  The answer has `access_token` and `mcp_url`. `curl https://cloud.pilotprotocol.network/`
  prints the full guide.

Configure the token as a header:

```json
{
  "mcpServers": {
    "pilot": {
      "type": "streamableHttp",
      "url": "https://cloud.pilotprotocol.network/mcp",
      "headers": { "Authorization": "Bearer <token>" }
    }
  }
}
```

Never ask the person to paste a token into chat; have them put it in the
config file themselves.

## Troubleshooting

- `401` after signing in: remove the server and add it again so the client
  registers afresh.
- The first call is slow: the node is still starting. Try again after a
  minute.
- Status: https://cloud.pilotprotocol.network/status
