#!/usr/bin/env bash
# publish-route.sh <subdomain> — make <subdomain>.jimmyhoughjr.net reach
# the pi through the Cloudflare tunnel, no dashboard needed.
#
# Creates (idempotently):
#   1. a proxied CNAME  <subdomain> -> <tunnel>.cfargotunnel.com
#   2. a tunnel ingress rule  <fqdn> -> http://localhost:80
#      (inserted before the catch-all; localhost:80 is Dokku's nginx,
#       which routes by Host header — same target for every app)
#
# One-time setup: create an API token at
# dash.cloudflare.com/profile/api-tokens with
#   Zone / DNS / Edit        (zone: jimmyhoughjr.net)
#   Account / Cloudflare Tunnel / Edit
# and store it: printf '%s' '<token>' > ~/.cf_api_token && chmod 600 ~/.cf_api_token
set -euo pipefail

DOMAIN="jimmyhoughjr.net"
TUNNEL_ID="66a2087d-afe4-4e70-9e74-05da0476cea8"

if [[ $# -ne 1 ]]; then
  echo "usage: $(basename "$0") <subdomain>" >&2
  exit 1
fi
SUB="$1"
TOKEN="${CF_API_TOKEN:-$(cat "$HOME/.cf_api_token" 2>/dev/null || true)}"
if [[ -z "$TOKEN" ]]; then
  echo "error: set CF_API_TOKEN or put the token in ~/.cf_api_token" >&2
  exit 1
fi

CF_API_TOKEN="$TOKEN" SUB="$SUB" DOMAIN="$DOMAIN" TUNNEL_ID="$TUNNEL_ID" python3 - <<'EOF'
import json, os, sys, urllib.request

token = os.environ["CF_API_TOKEN"]
sub, domain, tunnel = os.environ["SUB"], os.environ["DOMAIN"], os.environ["TUNNEL_ID"]
fqdn = f"{sub}.{domain}"
API = "https://api.cloudflare.com/client/v4"

def call(method, path, body=None):
    req = urllib.request.Request(
        API + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return json.load(e)

zones = call("GET", f"/zones?name={domain}")
if not zones.get("result"):
    sys.exit(f"error: zone {domain} not found — token missing Zone/DNS permission?")
zone = zones["result"][0]
zone_id, account_id = zone["id"], zone["account"]["id"]

# 1. DNS record (tolerate "already exists")
dns = call("POST", f"/zones/{zone_id}/dns_records", {
    "type": "CNAME", "name": sub, "content": f"{tunnel}.cfargotunnel.com",
    "proxied": True, "comment": "publish-route.sh",
})
if dns.get("success"):
    print(f"dns: created {fqdn} -> {tunnel}.cfargotunnel.com (proxied)")
elif any(e.get("code") == 81057 for e in dns.get("errors", [])):
    print(f"dns: {fqdn} already exists, leaving it")
else:
    sys.exit(f"error creating dns record: {dns.get('errors')}")

# 2. Tunnel ingress rule (fetch full config, insert before catch-all, put back)
conf = call("GET", f"/accounts/{account_id}/cfd_tunnel/{tunnel}/configurations")
if not conf.get("success"):
    sys.exit(f"error reading tunnel config: {conf.get('errors')} — token missing Cloudflare Tunnel permission?")
config = (conf["result"] or {}).get("config") or {}
ingress = config.get("ingress") or []
if any(r.get("hostname") == fqdn for r in ingress):
    print(f"ingress: rule for {fqdn} already present")
else:
    rule = {"hostname": fqdn, "service": "http://localhost:80"}
    if ingress and "hostname" not in ingress[-1]:
        ingress.insert(len(ingress) - 1, rule)  # keep catch-all last
    else:
        ingress.append(rule)
        ingress.append({"service": "http_status:404"})
    config["ingress"] = ingress
    put = call("PUT", f"/accounts/{account_id}/cfd_tunnel/{tunnel}/configurations", {"config": config})
    if not put.get("success"):
        sys.exit(f"error writing tunnel config: {put.get('errors')}")
    print(f"ingress: added {fqdn} -> http://localhost:80")

print(f"done — https://{fqdn} should answer within ~a minute")
EOF
