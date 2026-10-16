#!/usr/bin/env python3
"""Check the hosted Pilot MCP server against what connector directories test.

Runs without an account: discovery documents, the 401 challenge, dynamic
client registration with each platform's callback, the authorize and token
endpoints' error handling, transports and CORS. Nothing here signs in.

    python3 scripts/check-live.py [--base https://cloud.pilotprotocol.network] [--json]

Optional: PILOT_CLIENT_ID and PILOT_CLIENT_SECRET (a pre-registered
confidential client) add checks of the token endpoint's client
authentication. They are read from the environment and never printed.
"""
import argparse, base64, hashlib, json, os, secrets, sys, urllib.error, urllib.parse, urllib.request

# Each platform's OAuth callback, as the platform documents it. "unverified"
# marks ones taken from third-party reports.
CALLBACKS = {
    "Claude (claude.ai, Desktop)": "https://claude.ai/api/mcp/auth_callback",
    "Claude (claude.com)": "https://claude.com/api/mcp/auth_callback",
    "Claude Code (loopback)": "http://localhost:53682/callback",
    "ChatGPT": "https://chatgpt.com/connector_platform_oauth_redirect",
    "OpenAI review (platform)": "https://platform.openai.com/apps-manage/oauth",
    "Meta Muse": "https://agent.meta.ai/api/hatch/oauth/callback",
    "Microsoft 365 Copilot": "https://teams.microsoft.com/api/platform/v1.0/oAuthRedirect",
    "Copilot Studio / Power Platform": "https://global.consent.azure-apim.net/redirect",
    "Gemini Enterprise": "https://vertexaisearch.cloud.google.com/oauth-redirect",
    "Gemini CLI (loopback)": "http://localhost:7777/oauth/callback",
    "Perplexity": "https://www.perplexity.ai/rest/connections/oauth_callback",
    "Perplexity Enterprise": "https://enterprise.perplexity.ai/rest/connections/oauth_callback",
    "VS Code (loopback)": "http://127.0.0.1:33418",
    "VS Code (web)": "https://vscode.dev/redirect",
    "Cursor (web)": "https://www.cursor.com/agents/mcp/oauth/callback",
    "Cursor (app scheme)": "cursor://anysphere.cursor-mcp/oauth/callback",
    "Docker MCP Toolkit": "https://mcp.docker.com/oauth/callback",
    "Gemini CLI (random port)": "http://localhost:61234/oauth/callback",
}

INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "pilot-connectors-check", "version": "1"}}}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


opener = urllib.request.build_opener(NoRedirect)


def req(method, url, body=None, headers=None, form=None):
    h = {"User-Agent": "pilot-connectors-check/1 (+https://github.com/pilot-protocol/pilot-connectors)"}
    h.update(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h.setdefault("Content-Type", "application/json")
    elif form is not None:
        data = urllib.parse.urlencode(form).encode()
        h.setdefault("Content-Type", "application/x-www-form-urlencoded")
    r = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        resp = opener.open(r, timeout=20)
        return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def jbody(raw):
    try:
        return json.loads(raw)
    except Exception:
        return None


results = []


def check(area, name, ok, detail="", level="fail"):
    """level: 'fail' for a requirement, 'warn' for a review risk, 'info' for notes."""
    results.append({"area": area, "check": name, "ok": bool(ok), "level": level if not ok else "pass", "detail": detail})


def pkce():
    v = secrets.token_urlsafe(48)
    return v, base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://cloud.pilotprotocol.network")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    B = a.base.rstrip("/")
    mcp = B + "/mcp"

    # Discovery (RFC 9728, RFC 8414)
    s, h, raw = req("GET", B + "/.well-known/oauth-protected-resource/mcp")
    prm = jbody(raw) or {}
    check("discovery", "protected-resource metadata at /.well-known/oauth-protected-resource/mcp", s == 200, f"HTTP {s}")
    check("discovery", "PRM resource equals the MCP URL", prm.get("resource") == mcp, str(prm.get("resource")))
    check("discovery", "PRM names an authorization server", bool(prm.get("authorization_servers")), str(prm.get("authorization_servers")))
    s, h, raw = req("GET", B + "/.well-known/oauth-authorization-server")
    asm = jbody(raw) or {}
    check("discovery", "authorization-server metadata", s == 200 and asm.get("issuer") == B, f"HTTP {s}, issuer {asm.get('issuer')}")
    check("discovery", "PKCE S256 advertised", "S256" in asm.get("code_challenge_methods_supported", []))
    check("discovery", "dynamic client registration endpoint", bool(asm.get("registration_endpoint")))
    check("discovery", "client_credentials grant (AWS AgentCore needs it)", "client_credentials" in asm.get("grant_types_supported", []),
          str(asm.get("grant_types_supported")), "warn")
    check("discovery", "client ID metadata documents advertised (Claude/ChatGPT/Smithery prefer CIMD)",
          asm.get("client_id_metadata_document_supported") is True, "not advertised", "warn")
    check("discovery", "revocation endpoint (RFC 7009)", bool(asm.get("revocation_endpoint")), "none", "warn")
    check("discovery", "iss in authorization response (RFC 9207, lets ChatGPT use its stable redirect)",
          asm.get("authorization_response_iss_parameter_supported") is True, "not advertised", "warn")
    s, _, _ = req("GET", B + "/.well-known/openid-configuration")
    check("discovery", "OpenID discovery (ChatGPT workspace domain restriction)", s == 200, f"HTTP {s}", "info")

    # The challenge an unauthenticated client sees
    s, h, raw = req("POST", mcp, INIT, {"Accept": "application/json, text/event-stream"})
    wa = {k.lower(): v for k, v in h.items()}.get("www-authenticate", "")
    check("transport", "unauthenticated POST /mcp answers 401", s == 401, f"HTTP {s}")
    check("transport", "WWW-Authenticate carries resource_metadata", "resource_metadata=" in wa, wa)
    check("transport", "WWW-Authenticate names the path-specific metadata (/mcp)", "oauth-protected-resource/mcp" in wa, wa, "warn")
    check("transport", "WWW-Authenticate carries scope", "scope=" in wa, wa, "warn")
    s, h, raw = req("POST", mcp, INIT, {"Accept": "application/json, text/event-stream", "Authorization": "Bearer not-a-real-token"})
    check("transport", "bad bearer token answers 401", s == 401, f"HTTP {s}")
    s, h, raw = req("POST", mcp, INIT, {"Accept": "application/json, text/event-stream", "Origin": "https://evil.example"})
    check("transport", "foreign Origin refused before auth (403) — Anthropic asks for Origin validation", s == 403,
          f"HTTP {s}; refused only for lack of a token", "warn")
    s, h, _ = req("OPTIONS", mcp, headers={"Origin": "https://claude.ai", "Access-Control-Request-Method": "POST"})
    lh = {k.lower(): v for k, v in h.items()}
    check("transport", "CORS preflight", s in (200, 204) and "access-control-allow-origin" in lh, f"HTTP {s}, ACAO {lh.get('access-control-allow-origin')}")
    check("transport", "CORS exposes Mcp-Session-Id and WWW-Authenticate",
          "mcp-session-id" in lh.get("access-control-expose-headers", "").lower() and "www-authenticate" in lh.get("access-control-expose-headers", "").lower())
    s, _, _ = req("GET", B + "/sse")
    check("transport", "legacy SSE at /sse (Copilot Studio wants Streamable HTTP only; SSE may stay as long as /mcp works)", s in (401, 200), f"HTTP {s}", "info")

    # Directory files
    s, _, raw = req("GET", B + "/.well-known/mcp/server-card.json")
    card = jbody(raw) or {}
    tools = card.get("tools", [])
    check("directories", "Smithery server card", s == 200 and bool(tools), f"HTTP {s}, {len(tools)} tools")
    missing = [t["name"] for t in tools if not (t.get("annotations") or {}).get("title")]
    check("tools", "every tool has a title annotation", not missing, ", ".join(missing))
    nohint = [t["name"] for t in tools if "readOnlyHint" not in (t.get("annotations") or {})]
    check("tools", "every tool states readOnlyHint", not nohint, ", ".join(nohint))
    sends = [t["name"] for t in tools if t["name"] in ("pilot_send", "pilot_send_file", "pilot_handshake", "pilot_approve", "pilot_app_install", "pilot_app_call", "pilot_pack_send", "pilot_business_call", "pilot_research_answer")
             and not (t.get("annotations") or {}).get("destructiveHint")]
    check("tools", "sends and grants marked destructive (Anthropic: writes that reach others should prompt)", not sends, ", ".join(sends), "warn")
    steer = [t["name"] for t in tools if any(w in (t.get("description") or "") for w in ("START HERE", "every conversation", "Call this first", "prefer pilot_"))]
    check("tools", "no descriptions that steer the model's tool choice (Anthropic/OpenAI policy)", not steer, ", ".join(steer), "warn")
    apps = [t["name"] for t in tools if t["name"].startswith("pilot_app_")]
    check("tools", "no generic app executor in the listed profile (OpenAI/Anthropic: money movement, generic executors)", not apps, ", ".join(apps), "warn")
    paid = [t["name"] for t in tools if any(w in (t.get("description") or "") for w in ("USDC",))]
    check("tools", "no ads or crypto payouts in the tool surface (Anthropic asks about sponsored content and financial transactions)", not paid, ", ".join(paid), "warn")
    longd = [t["name"] for t in tools if len(t.get("description") or "") > 1024]
    check("tools", "tool descriptions under 1,024 characters", not longd, ", ".join(longd), "warn")
    check("tools", "tool count", True, f"{len(tools)} tools", "info")
    for path, who in (("/.well-known/openai-apps-challenge", "OpenAI domain challenge (token comes from the portal)"),
                      ("/.well-known/mcp-registry-auth", "MCP Registry HTTP proof (DNS proof is the alternative)"),
                      ("/docs", "public documentation page on the service host")):
        s, _, _ = req("GET", B + path)
        check("directories", who, s == 200, f"HTTP {s}", "warn")
    s, h, raw = req("GET", B + "/pilot-icon.png")
    check("directories", "icon served", s == 200 and raw[:4] == b"\x89PNG", f"HTTP {s}, {len(raw)} bytes")
    for u in ("https://pilotprotocol.network/privacy", "https://pilotprotocol.network/terms"):
        s, _, raw = req("GET", u)
        text = raw.decode("utf-8", "ignore").lower()
        check("directories", u.rsplit("/", 1)[1] + " page", s == 200, f"HTTP {s}")
        check("directories", u.rsplit("/", 1)[1] + " mentions the hosted service (Pilot Cloud / MCP)",
              any(k in text for k in ("pilot cloud", "cloud.pilotprotocol.network", "hosted node", "pilot mcp")), "no mention found", "warn")

    # Dynamic client registration with each platform's callback, then authorize
    reg = asm.get("registration_endpoint", B + "/oauth/register")
    for who, cb in CALLBACKS.items():
        s, _, raw = req("POST", reg, {"client_name": f"check {who}", "redirect_uris": [cb], "token_endpoint_auth_method": "none",
                                      "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"]})
        c = jbody(raw) or {}
        if s != 201 or not c.get("client_id"):
            check("callbacks", f"DCR accepts {who} callback", False, f"HTTP {s} {raw[:120]!r}")
            continue
        v, ch = pkce()
        q = urllib.parse.urlencode({"response_type": "code", "client_id": c["client_id"], "redirect_uri": cb, "code_challenge": ch,
                                    "code_challenge_method": "S256", "state": "x", "scope": "pilot", "resource": mcp})
        s2, h2, _ = req("GET", asm["authorization_endpoint"] + "?" + q)
        loc = {k.lower(): v for k, v in h2.items()}.get("location", "")
        check("callbacks", f"{who}: register + authorize reaches sign-in", s2 == 302 and loc.startswith("/me"), f"DCR 201, authorize HTTP {s2} → {loc[:40]}")
    # DCR without an auth method: RFC 7591 default is client_secret_basic; Microsoft 365 needs a secret back
    s, _, raw = req("POST", reg, {"client_name": "check default auth", "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"]})
    c = jbody(raw) or {}
    check("dcr", "DCR with no auth method issues a secret (Microsoft 365 DCR needs one)", "client_secret" in c,
          f"returned token_endpoint_auth_method={c.get('token_endpoint_auth_method')}", "warn")
    s, _, raw = req("POST", reg, {"client_name": "check secret", "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"], "token_endpoint_auth_method": "client_secret_basic"})
    c2 = jbody(raw) or {}
    check("dcr", "DCR issues a secret when asked (client_secret_basic)", "client_secret" in c2)
    s, _, raw = req("POST", reg, {"client_name": "check bad", "redirect_uris": ["javascript:alert(1)"]})
    check("dcr", "DCR refuses a javascript: redirect", s == 400, f"HTTP {s}")
    s, _, raw = req("POST", reg, {"client_name": "check http", "redirect_uris": ["http://evil.example/cb"]})
    check("dcr", "DCR refuses non-loopback http", s == 400, f"HTTP {s}")

    # Authorize error handling
    cid = c.get("client_id")
    good = "https://claude.ai/api/mcp/auth_callback"
    def authz(**kw):
        p = {"response_type": "code", "client_id": cid, "redirect_uri": good, "state": "x"}
        p.update(kw)
        p = {k: v for k, v in p.items() if v is not None}
        s, h, _ = req("GET", asm["authorization_endpoint"] + "?" + urllib.parse.urlencode(p))
        return s, {k.lower(): v for k, v in h.items()}.get("location", "")
    s, loc = authz(redirect_uri="https://evil.example/cb", code_challenge=pkce()[1], code_challenge_method="S256")
    check("authorize", "unregistered redirect_uri refused without redirecting", s == 400, f"HTTP {s}")
    s, loc = authz(client_id="pc_doesnotexist", code_challenge=pkce()[1], code_challenge_method="S256")
    check("authorize", "unknown client refused", s == 400, f"HTTP {s}")
    s, loc = authz()
    check("authorize", "public client without PKCE gets invalid_request at its redirect", s == 302 and "error=invalid_request" in loc, loc[:90])
    s, loc = authz(code_challenge="abc", code_challenge_method="plain")
    check("authorize", "PKCE plain refused", s == 302 and "error=invalid_request" in loc, loc[:90])
    s, loc = authz(response_type="token", code_challenge=pkce()[1], code_challenge_method="S256")
    check("authorize", "implicit flow refused", s == 302 and "unsupported_response_type" in loc, loc[:90])

    # Token endpoint
    tok = asm.get("token_endpoint", B + "/oauth/token")
    s, _, raw = req("POST", tok, form={"grant_type": "authorization_code", "code": "nope", "redirect_uri": good, "client_id": cid, "code_verifier": "x" * 50})
    check("token", "bogus code → invalid_grant", s == 400 and (jbody(raw) or {}).get("error") == "invalid_grant", raw[:100].decode("utf-8", "ignore"))
    s, _, raw = req("POST", tok, form={"grant_type": "refresh_token", "refresh_token": "nope", "client_id": cid})
    check("token", "bogus refresh token refused", s in (400, 401), f"HTTP {s} {(jbody(raw) or {}).get('error')}")
    s, _, raw = req("POST", tok, form={"grant_type": "client_credentials", "scope": "pilot"})
    check("token", "client_credentials grant (AWS AgentCore Gateway)", s == 200, f"HTTP {s} {(jbody(raw) or {}).get('error')}", "warn")
    kid, ksec = os.environ.get("PILOT_CLIENT_ID"), os.environ.get("PILOT_CLIENT_SECRET")
    if kid and ksec:
        basic = "Basic " + base64.b64encode(f"{urllib.parse.quote(kid)}:{urllib.parse.quote(ksec)}".encode()).decode()
        # The secret is checked once a valid code is presented, so without
        # signing in only the code check can be seen here.
        s, _, raw = req("POST", tok, form={"grant_type": "authorization_code", "code": "nope", "redirect_uri": "https://agent.meta.ai/api/hatch/oauth/callback"},
                        headers={"Authorization": basic})
        e = (jbody(raw) or {}).get("error")
        check("token", "pre-registered client: token endpoint takes HTTP Basic (secret is checked after a valid code)", e == "invalid_grant", f"HTTP {s} {e}")
        s, _, raw = req("POST", tok, form={"grant_type": "client_credentials", "scope": "pilot"}, headers={"Authorization": basic})
        check("token", "client_credentials with the pre-registered client (AWS)", s == 200, f"HTTP {s} {(jbody(raw) or {}).get('error')}", "warn")
        for who, cb in (("Meta Muse", "https://agent.meta.ai/api/hatch/oauth/callback"), ("Claude", good)):
            q = urllib.parse.urlencode({"response_type": "code", "client_id": kid, "redirect_uri": cb, "state": "x", "scope": "pilot"})
            s, h, _ = req("GET", asm["authorization_endpoint"] + "?" + q)
            loc = {k.lower(): v for k, v in h.items()}.get("location", "")
            check("token", f"pre-registered client: authorize with {who} callback", (s == 302 and loc.startswith("/me")) if who == "Meta Muse" else s in (302, 400),
                  f"HTTP {s} {loc[:40]}", "info" if who != "Meta Muse" else "fail")

    if a.json:
        print(json.dumps(results, indent=1))
    else:
        cur = None
        for r in results:
            if r["area"] != cur:
                cur = r["area"]
                print(f"\n## {cur}")
            mark = {"pass": "PASS", "fail": "FAIL", "warn": "WARN", "info": "INFO"}[r["level"]]
            print(f"  {mark}  {r['check']}" + (f"  — {r['detail']}" if r["detail"] and r["level"] != "pass" or r["level"] == "info" else ""))
        n = {k: sum(1 for r in results if r["level"] == k) for k in ("pass", "fail", "warn", "info")}
        print(f"\n{n['pass']} pass, {n['fail']} fail, {n['warn']} warn, {n['info']} info")
    return 1 if any(r["level"] == "fail" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
