#!/usr/bin/env bash
# Checks every manifest in this repository. Validators that are not installed
# are skipped with a note; JSON syntax, the shared URL and the no-secrets
# check always run.
set -uo pipefail
cd "$(dirname "$0")/.."
URL="https://cloud.pilotprotocol.network/mcp"
fail=0
ok()   { printf '  ok    %s\n' "$1"; }
bad()  { printf '  FAIL  %s\n' "$1"; fail=1; }
skip() { printf '  skip  %s\n' "$1"; }

echo "JSON files parse"
while IFS= read -r f; do
  python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$f" 2>/dev/null && ok "$f" || bad "$f"
done < <(git ls-files '*.json' 2>/dev/null || find . -name '*.json' -not -path './.git/*')

echo "Every MCP manifest points at $URL"
for f in .mcp.json .cursor-plugin/mcp.json power/mcp.json gemini-extension.json server.json; do
  [ -f "$f" ] || { bad "$f missing"; continue; }
  grep -q "$URL" "$f" && ok "$f" || bad "$f does not name $URL"
done

echo "No secrets or internal hosts"
if grep -rInE '(client_secret|pc_[a-z0-9]{8,}|Bearer [A-Za-z0-9._-]{20,}|BEGIN [A-Z ]*PRIVATE KEY|\.svc\.cluster\.local|10\.[0-9]+\.[0-9]+\.[0-9]+)' \
     --exclude-dir=.git --exclude='*.png' --exclude=validate.sh --exclude=check-live.py --exclude=e2e.py . ; then
  bad "possible secret or internal address above"
else
  ok "none found"
fi

echo "Name and version agree"
python3 - <<'EOF' && ok "all manifests say pilot 1.0.0" || bad "name or version differs between manifests"
import json, sys
seen = {}
for f, path in [(".claude-plugin/plugin.json", ()), (".grok-plugin/plugin.json", ()), (".cursor-plugin/plugin.json", ()), ("gemini-extension.json", ())]:
    try:
        d = json.load(open(f))
    except FileNotFoundError:
        continue
    seen[f] = (d.get("name"), d.get("version"))
v = json.load(open("server.json"))["version"]
bad = {f: nv for f, nv in seen.items() if nv != ("pilot", v)}
for f, nv in bad.items():
    print("   ", f, nv, file=sys.stderr)
sys.exit(1 if bad else 0)
EOF

echo "Claude Code plugin"
if command -v claude >/dev/null; then
  claude plugin validate . >/dev/null 2>&1 && ok "marketplace.json" || bad "claude plugin validate ."
  claude plugin validate .claude-plugin/plugin.json >/dev/null 2>&1 && ok "plugin.json" || bad "claude plugin validate .claude-plugin/plugin.json"
else skip "claude not installed"; fi

echo "Gemini CLI extension"
if command -v npx >/dev/null; then
  tmp=$(mktemp -d)
  HOME="$tmp" npx -y @google/gemini-cli@0.64.0 extensions validate . >/dev/null 2>&1 && ok "gemini extensions validate" || bad "gemini extensions validate ."
  rm -rf "$tmp"
else skip "npx not installed"; fi

echo "Official MCP Registry"
if command -v mcp-publisher >/dev/null; then
  mcp-publisher validate >/dev/null 2>&1 && ok "mcp-publisher validate" || bad "mcp-publisher validate"
else skip "mcp-publisher not installed (brew install mcp-publisher, or the GitHub release)"; fi

echo "Kiro power (Agent Plugins format)"
python3 - <<'PY' && ok "power/plugin.json and power/mcp.json" || bad "power/ manifests"
import json, os, re, sys
p = json.load(open("power/plugin.json")); m = json.load(open("power/mcp.json"))
problems = []
if p.get("$schema") != "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json": problems.append("plugin.json $schema")
if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", p.get("name", "")): problems.append("plugin.json name")
for k in ("version", "description", "license", "keywords"):
    if not p.get(k): problems.append("plugin.json " + k)
if not p.get("author", {}).get("name"): problems.append("plugin.json author.name")
if m.get("$schema") != "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json": problems.append("mcp.json $schema")
if any(v.get("type") != "streamable-http" for v in m.get("mcpServers", {}).values()): problems.append("mcp.json type must be streamable-http")
if not os.path.exists("power/skills/pilot/SKILL.md"): problems.append("power/skills/pilot/SKILL.md")
readme = open("power/README.md").read()
if "privacy" not in readme.lower() or "@" not in readme: problems.append("README needs privacy link and support contact")
problems and print(*problems, sep="\n", file=sys.stderr)
sys.exit(1 if problems else 0)
PY
cmp -s skills/pilot/SKILL.md power/skills/pilot/SKILL.md && ok "power skill matches skills/pilot" || bad "power/skills/pilot/SKILL.md differs from skills/pilot/SKILL.md"

exit $fail
