#!/usr/bin/env python3
"""End-to-end test of the hosted Pilot MCP server, signed in.

Does what a desktop MCP client (Claude Code, Cursor, VS Code) does:
registers a client, opens the browser for sign-in and consent, catches the
code on a loopback port, exchanges it with PKCE, then speaks Streamable HTTP.
Only read-only tools are called unless --writes is given, so it is safe on a
real account.

    python3 scripts/e2e.py [--base URL] [--out results.json] [--no-browser]

With --no-browser it prints the URL to open instead.
"""
import argparse, base64, hashlib, http.server as httpserver, json, secrets, socket, statistics, sys, threading, time, urllib.error, urllib.parse, urllib.request, webbrowser

UA = "pilot-connectors-e2e/1 (+https://github.com/pilot-protocol/pilot-connectors)"
PROTOCOLS = ["2025-11-25", "2025-06-18", "2025-03-26"]

# Read-only calls, as a reviewer's first session would make them.
SAFE_CALLS = [
    ("pilot_info", {}),
    ("pilot_guide", {}),
    ("pilot_friends", {}),
    ("pilot_pending", {}),
    ("pilot_trust", {}),
    ("pilot_inbox", {"limit": 5}),
    ("pilot_files", {"limit": 5}),
    ("pilot_peers", {}),
    ("pilot_search", {"query": "weather", "limit": 5}),
    ("pilot_ask", {"task": "What is Bitcoin trading at in euros right now?"}),
    ("pilot_find", {"target": "list-agents"}),
    ("pilot_ping", {"target": "list-agents"}),
    ("pilot_help", {"agent": "open-meteo"}),
    ("pilot_apps", {}),
    ("pilot_pack_list", {}),
    ("pilot_pack_skill", {}),
    ("pilot_business_search", {"q": "coffee", "limit": 3}),
    ("pilot_places", {"q": "coffee", "lat": 37.7749, "lng": -122.4194, "radius_m": 800}),
]


def http(method, url, data=None, headers=None, timeout=150):
    h = {"User-Agent": UA}
    h.update(headers or {})
    r = urllib.request.Request(url, data=data, method=method, headers=h)
    t = time.time()
    try:
        resp = urllib.request.urlopen(r, timeout=timeout)
        return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read(), time.time() - t
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read(), time.time() - t


def sign_in(base, mcp, open_browser):
    meta = json.loads(http("GET", base + "/.well-known/oauth-authorization-server")[2])
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    redirect = f"http://127.0.0.1:{port}/callback"
    s, _, raw, _ = http("POST", meta["registration_endpoint"], json.dumps({
        "client_name": "Pilot connectors e2e test", "redirect_uris": [redirect], "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"]}).encode(), {"Content-Type": "application/json"})
    client = json.loads(raw)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    url = meta["authorization_endpoint"] + "?" + urllib.parse.urlencode({
        "response_type": "code", "client_id": client["client_id"], "redirect_uri": redirect, "code_challenge": challenge,
        "code_challenge_method": "S256", "state": state, "scope": "pilot", "resource": mcp})
    got = {}

    class H(httpserver.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Pilot e2e test: signed in. You can close this tab.")

        def log_message(self, *a):
            pass

    srv = httpserver.HTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.handle_request, daemon=True).start()
    print("Sign in and approve in the browser:\n" + url, flush=True)
    if open_browser:
        webbrowser.open(url)
    t0 = time.time()
    while "code" not in got and "error" not in got:
        if time.time() - t0 > 1800:
            sys.exit("timed out waiting for the browser")
        time.sleep(0.5)
    if got.get("state") != state or "code" not in got:
        sys.exit(f"sign-in failed: {got}")
    s, _, raw, _ = http("POST", meta["token_endpoint"], urllib.parse.urlencode({
        "grant_type": "authorization_code", "code": got["code"], "redirect_uri": redirect, "client_id": client["client_id"],
        "code_verifier": verifier, "resource": mcp}).encode(), {"Content-Type": "application/x-www-form-urlencoded"})
    tok = json.loads(raw)
    if s != 200:
        sys.exit(f"token exchange failed: {s} {tok}")
    return meta, client, tok


def parse_rpc(headers, raw):
    """A JSON-RPC response, plain or as server-sent events."""
    if headers.get("content-type", "").startswith("text/event-stream"):
        last = None
        for block in raw.decode("utf-8", "ignore").split("\n\n"):
            data = "\n".join(l[5:].lstrip() for l in block.splitlines() if l.startswith("data:"))
            if data:
                try:
                    msg = json.loads(data)
                    if "result" in msg or "error" in msg:
                        last = msg
                except ValueError:
                    pass
        return last
    try:
        return json.loads(raw)
    except ValueError:
        return None


class Session:
    def __init__(self, mcp, token):
        self.mcp, self.token, self.sid, self.n, self.version = mcp, token, None, 0, None

    def rpc(self, method, params=None, notify=False, extra=None):
        self.n += 1
        body = {"jsonrpc": "2.0", "method": method}
        if not notify:
            body["id"] = self.n
        if params is not None:
            body["params"] = params
        h = {"Authorization": "Bearer " + self.token, "Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.sid:
            h["Mcp-Session-Id"] = self.sid
        if self.version:
            h["Mcp-Protocol-Version"] = self.version
        h.update(extra or {})
        s, hd, raw, dt = http("POST", self.mcp, json.dumps(body).encode(), h)
        if hd.get("mcp-session-id"):
            self.sid = hd["mcp-session-id"]
        return s, hd, (None if notify else parse_rpc(hd, raw)), dt


LIVE_TASKS = [
    "What is Bitcoin trading at in euros right now?",
    "Will it rain in Lisbon tomorrow afternoon?",
    "Any new security advisories for OpenSSL this week?",
    "Find recent papers on agent-to-agent protocols.",
]


def call(sess, name, args):
    st, hd, msg, dt = sess.rpc("tools/call", {"name": name, "arguments": args})
    res = (msg or {}).get("result") or {}
    text = " ".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")
    ok = st == 200 and msg is not None and "error" not in msg and not res.get("isError")
    return ok, text, dt


def steps_of(plan_text):
    """(agent, filters) pairs from a pilot_ask plan, wherever they sit in it."""
    try:
        plan = json.loads(plan_text.split(" Notice:")[0])
    except ValueError:
        return []
    out = []
    def walk(o):
        if isinstance(o, dict):
            ag = o.get("agent") or o.get("specialist") or o.get("hostname")
            if isinstance(ag, str) and ag not in ("pilot-mom", "list-agents") and ("filters" in o or "data" in o or "command" in o or "query" in o):
                f = o.get("filters") if isinstance(o.get("filters"), dict) else (o.get("data") if isinstance(o.get("data"), dict) else {})
                out.append((ag, f))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, str) and o.strip().startswith("{"):
            try:
                walk(json.loads(o))
            except ValueError:
                pass
    walk(plan)
    seen, uniq = set(), []
    for ag, f in out:
        k = (ag, json.dumps(f, sort_keys=True))
        if k not in seen:
            seen.add(k)
            uniq.append((ag, f))
    return uniq[:3]


def live_data(sess, rec):
    for task in LIVE_TASKS:
        ok, text, dt = call(sess, "pilot_ask", {"task": task})
        steps = steps_of(text)
        rec("live", f"pilot_ask: {task}", ok and bool(steps), f"{dt:.2f}s, {len(text)} chars, steps {[s[0] for s in steps]}", plan=text[:6000])
        for ag, filters in steps:
            okh, th, dth = call(sess, "pilot_help", {"agent": ag})
            rec("live", f"  pilot_help {ag}", okh, f"{dth:.2f}s, {len(th)} chars: {th[:100]!r}")
            okq, tq, dtq = call(sess, "pilot_query", {"agent": ag, "filters": filters})
            rec("live", f"  pilot_query {ag} {json.dumps(filters)[:80]}", okq and len(tq) > 40, f"{dtq:.2f}s, {len(tq)} chars: {tq[:160]!r}", seconds=round(dtq, 2), chars=len(tq))
            oks, ts, dts = call(sess, "pilot_summary", {"agent": ag, "filters": filters, "question": task})
            rec("live", f"  pilot_summary {ag}", oks and len(ts) > 40, f"{dts:.2f}s, {len(ts)} chars: {ts[:160]!r}", seconds=round(dts, 2), chars=len(ts))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://cloud.pilotprotocol.network")
    ap.add_argument("--out", default="e2e-results.json")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--live", action="store_true", help="only the live-data path: pilot_ask, then each step of its plan")
    a = ap.parse_args()
    base = a.base.rstrip("/")
    mcp = base + "/mcp"
    R = []

    def rec(area, name, ok, detail="", **kw):
        R.append({"area": area, "check": name, "ok": bool(ok), "detail": detail, **kw})
        print(f"  {'PASS' if ok else 'FAIL'}  [{area}] {name}" + (f"  — {detail}" if detail else ""), flush=True)

    meta, client, tok = sign_in(base, mcp, not a.no_browser)
    rec("oauth", "authorization code + PKCE exchange", "access_token" in tok,
        f"token_type={tok.get('token_type')} expires_in={tok.get('expires_in')} scope={tok.get('scope')} refresh={'refresh_token' in tok}")
    at = tok["access_token"]

    # Initialize with each protocol version the major clients send
    for v in PROTOCOLS:
        s = Session(mcp, at)
        st, hd, msg, dt = s.rpc("initialize", {"protocolVersion": v, "capabilities": {}, "clientInfo": {"name": "pilot-e2e", "version": "1"}})
        res = (msg or {}).get("result", {})
        rec("protocol", f"initialize {v}", st == 200 and "serverInfo" in res,
            f"HTTP {st}, negotiated {res.get('protocolVersion')}, session={'yes' if hd.get('mcp-session-id') else 'no'}, {dt:.2f}s")
    sess = Session(mcp, at)
    st, hd, msg, dt = sess.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "pilot-e2e", "version": "1"}})
    init = (msg or {}).get("result", {})
    sess.version = init.get("protocolVersion")
    rec("protocol", "server info and capabilities", bool(init.get("capabilities")),
        f"{init.get('serverInfo')} caps={sorted(init.get('capabilities', {}))} instructions={len(init.get('instructions') or '')} chars")
    sess.rpc("notifications/initialized", notify=True)

    st, hd, msg, dt = sess.rpc("tools/list")
    tools = (msg or {}).get("result", {}).get("tools", [])
    rec("protocol", "tools/list", bool(tools), f"{len(tools)} tools, {dt:.2f}s")
    card = json.loads(http("GET", base + "/.well-known/mcp/server-card.json")[2])
    cn, ln = {t["name"] for t in card.get("tools", [])}, {t["name"] for t in tools}
    rec("protocol", "server card matches tools/list", cn == ln, f"only in card: {sorted(cn - ln)}; only live: {sorted(ln - cn)}")
    rec("protocol", "tools declare outputSchema (structured results)", any("outputSchema" in t for t in tools),
        f"{sum(1 for t in tools if 'outputSchema' in t)} of {len(tools)}")
    for m in ("prompts/list", "resources/list"):
        st, hd, msg, dt = sess.rpc(m)
        rec("protocol", m, st == 200 and msg is not None and "error" not in msg, json.dumps((msg or {}).get("result") or (msg or {}).get("error"))[:120])
    st, hd, msg, dt = sess.rpc("ping")
    rec("protocol", "ping", st == 200 and "result" in (msg or {}), f"{dt:.2f}s")

    if a.live:
        live_data(sess, rec)
        json.dump({"base": base, "results": R}, open(a.out, "w"), indent=1)
        print(f"\n{sum(r['ok'] for r in R)} pass, {sum(not r['ok'] for r in R)} fail → {a.out}")
        return

    # Read-only tool calls
    lat = []
    names = {t["name"]: t for t in tools}
    for name, args in SAFE_CALLS:
        if name not in names:
            rec("tools", f"{name}", False, "not listed")
            continue
        st, hd, msg, dt = sess.rpc("tools/call", {"name": name, "arguments": args})
        res = (msg or {}).get("result") or {}
        text = " ".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")
        ok = st == 200 and msg is not None and "error" not in msg and not res.get("isError")
        lat.append(dt)
        rec("tools", f"{name} {json.dumps(args)}", ok, f"{dt:.2f}s, {len(text)} chars, structured={'structuredContent' in res}: {text[:140]!r}",
            seconds=round(dt, 2), chars=len(text), error=res.get("isError", False) or (msg or {}).get("error"))

    # Errors
    st, hd, msg, dt = sess.rpc("tools/call", {"name": "pilot_does_not_exist", "arguments": {}})
    rec("errors", "unknown tool gives an error", msg is not None and ("error" in msg or (msg.get("result") or {}).get("isError")), json.dumps(msg)[:140])
    st, hd, msg, dt = sess.rpc("tools/call", {"name": "pilot_inbox_read", "arguments": {"id": "does-not-exist"}})
    rec("errors", "bad argument gives a readable error", msg is not None and ("error" in msg or (msg.get("result") or {}).get("isError")), json.dumps(msg)[:160])
    st, hd, msg, dt = sess.rpc("nonexistent/method")
    rec("errors", "unknown method → JSON-RPC error", msg is not None and "error" in msg, json.dumps(msg)[:120])

    # Origin validation, with a valid token (MCP spec: servers must validate Origin)
    st, hd, msg, dt = sess.rpc("ping", extra={"Origin": "https://evil.example"})
    rec("security", "foreign Origin with a valid token is refused", st == 403, f"HTTP {st}")
    st, hd, msg, dt = sess.rpc("ping", extra={"Origin": "https://claude.ai"})
    rec("security", "claude.ai Origin with a valid token is accepted", st == 200, f"HTTP {st}")
    # Token in the query string must not work
    st, _, _, _ = http("POST", mcp + "?access_token=" + at, json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}).encode(),
                       {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
    rec("security", "token in the query string is refused", st == 401, f"HTTP {st}")
    st, _, _, _ = http("POST", mcp, json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}).encode(),
                       {"Authorization": "Bearer " + at + "x", "Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
    rec("security", "altered token refused", st == 401, f"HTTP {st}")

    # Refresh and rotation
    if tok.get("refresh_token"):
        form = lambda rt: urllib.parse.urlencode({"grant_type": "refresh_token", "refresh_token": rt, "client_id": client["client_id"]}).encode()
        s1, _, raw, _ = http("POST", meta["token_endpoint"], form(tok["refresh_token"]), {"Content-Type": "application/x-www-form-urlencoded"})
        t2 = json.loads(raw)
        rec("oauth", "refresh token gives a new access token", s1 == 200 and "access_token" in t2, f"HTTP {s1}")
        s2, _, raw, _ = http("POST", meta["token_endpoint"], form(tok["refresh_token"]), {"Content-Type": "application/x-www-form-urlencoded"})
        rec("oauth", "used refresh token is refused (rotation)", s2 == 400, f"HTTP {s2}")
        if s1 == 200:
            s3 = Session(mcp, t2["access_token"])
            st, _, msg, _ = s3.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "pilot-e2e", "version": "1"}})
            rec("oauth", "refreshed access token works", st == 200, f"HTTP {st}")

    # Session end
    if sess.sid:
        st, _, _, _ = http("DELETE", mcp, None, {"Authorization": "Bearer " + at, "Mcp-Session-Id": sess.sid})
        rec("protocol", "DELETE ends the session", st in (200, 204, 405), f"HTTP {st}")

    if lat:
        q = sorted(lat)
        rec("latency", "tool-call latency (Microsoft store: p50 ≤ 2 s, p99 ≤ 9 s)", statistics.median(q) <= 2 and q[-1] <= 9,
            f"p50 {statistics.median(q):.2f}s, max {q[-1]:.2f}s over {len(q)} calls")
    json.dump({"base": base, "when": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "init": {k: init.get(k) for k in ("protocolVersion", "serverInfo", "capabilities")},
               "instructions": init.get("instructions"), "tools": tools, "results": R}, open(a.out, "w"), indent=1)
    print(f"\n{sum(r['ok'] for r in R)} pass, {sum(not r['ok'] for r in R)} fail → {a.out}")


if __name__ == "__main__":
    main()
