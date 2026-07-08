# The pi platform playbook

From nothing → a new app live at `<name>.jimmyhoughjr.net`, with data,
crons, accounts, and a status board. Written 2026-07-07 after building
watts, vault, and head2head this way.

**Machine bootstrap** (Dokku + Cloudflare tunnel from bare metal) is
already covered by [statusgen/SETUP.md](../statusgen/SETUP.md). This
playbook starts where that ends: the box runs Dokku, the tunnel exists,
and `dokku@192.168.0.103` accepts your key.

---

## 1. New app, the six steps

```sh
ssh dokku@192.168.0.103 apps:create <name>
ssh dokku@192.168.0.103 domains:set <name> <name>.jimmyhoughjr.net
mkdir <name>-site && cd <name>-site        # repo with a Dockerfile (see §2)
git init -b main && git add -A && git commit -m "init"
git remote add dokku dokku@192.168.0.103:<name>
git push dokku main
```

Then **one manual step in Cloudflare** (dashboard → Zero Trust → Tunnels →
published application routes): subdomain `<name>`, domain
`jimmyhoughjr.net`, service **HTTP → `localhost:80`**.

> The service URL is `localhost:80` for **every** app, always. Port 80 is
> Dokku's nginx, not any app; nginx routes by the `Host` header. Apps
> never conflict on it.

Verify before blaming DNS or the tunnel:

```sh
curl -H "Host: <name>.jimmyhoughjr.net" http://192.168.0.103/   # LAN truth
```

If LAN works and the browser says "can't find the server," it's DNS
negative-caching from before the route existed — flush or wait.

## 2. Dockerfiles that work here

**Static site** (watts, head2head, status):

```dockerfile
FROM nginx:alpine
COPY . /usr/share/nginx/html
```

**Node service** (vault's original): `FROM node:22-alpine`, copy source,
`CMD ["node", "server.js"]`, listen on 80. Zero-dep preferred.

**Swift service** (vault today): multi-stage, builds ON the pi (8-core /
16 GB handles it; first build ~8 min, cached ~5 min):

```dockerfile
FROM swift:6.1-noble AS build
# resolve deps in their own layer, then build --static-swift-stdlib
FROM ubuntu:noble   # + ca-certificates libcurl4 libxml2 for Foundation
```

**Swift gotcha: Mac-clean ≠ pi-clean.** The pi's Linux toolchain is
stricter (Sendable) and Linux Foundation has gaps (`URLResponse()`).
Always `swift build` locally first, but expect one on-device surprise.

## 3. Persistent data (survives deploys)

```sh
ssh dokku@192.168.0.103 storage:ensure-directory <name>
ssh dokku@192.168.0.103 storage:mount <name> /var/lib/dokku/data/storage/<name>:/data
ssh dokku@192.168.0.103 ps:restart <name>      # mounts apply on (re)start
```

Verify the mount took: `storage:report <name>` — the first attempt has
silently failed before.

## 4. Scheduled jobs

`app.json` in the repo root; the command runs in a fresh container from
the app image, with the storage mounts and config env:

```json
{ "cron": [{ "command": "/usr/local/bin/refresh-thing", "schedule": "0 6 2 * *" }] }
```

Confirm with `cron:list <name>`. Pattern in the wild: watts' monthly EIA
rates refresh writes to the storage mount; the page reads the mounted
copy first and falls back to the deploy-baked file.

## 5. Secrets

- Runtime: `ssh dokku@… config:set <name> KEY=value` (restarts the app).
- Build-time (Dockerfile ARG): `docker-options:add <name> build "--build-arg KEY=value"`
  — e.g. the blog's `GITHUB_TOKEN`.
- Never in the repo. Local copies live in `~/.something` chmod 600
  (`~/.eia_api_key`) or come from `gh auth token`.

## 6. Accounts & user data — vault

vault.jimmyhoughjr.net gives every subdomain app sign-in (Apple/Google)
and storage with zero app-side auth code:

1. Add the app's origin to vault's `ALLOWED_ORIGINS` (config:set).
2. Frontend calls with `credentials: "include"`:
   - `GET /api/config` → which providers are live (hide UI if none)
   - `GET /api/me` → session or 401
   - `GET/PUT /api/apps/<name>/data` → this user's private JSON blob
   - `GET/POST /api/apps/<name>/submissions` → shared public collection
     (signed-in append, public read, admin delete)
3. Sign-in links: `VAULT/auth/google?return=<your-url>` (and `apple`).

The session cookie is set on `.jimmyhoughjr.net`, so one login covers
every app.

## 7. Status board

```sh
~/repos/statusgen/bin/new-board.sh ~/status-site <slug> "Title" "Hub description"
# edit ~/status-site/<slug>/board.json (schema: statusgen/BOARD_SCHEMA.md)
cd ~/status-site && git add -A && git commit && git push dokku main
```

Section kinds: `stats`, `banner`, `barchart`, `pie`, `table`, `cards`
(items use `q` + `pill: {text, tone}`), `split` (uses `columns`).

## 8. Operational gotchas (all learned the hard way)

- **Trailing slashes in links.** nginx 301s `/blog` → `http://…/blog/`
  (it can't see the tunnel's TLS), and browsers refuse the downgrade.
  Link `/blog/` directly. Consider Cloudflare "Always Use HTTPS."
- **Long builds vs push timeouts.** A killed `git push` can leave a
  deploy lock (`apps:unlock <name>`) — but check first: the interrupted
  build may still be running and may even finish. Run long pushes in the
  background with output to a file.
- **Failed builds are safe.** Dokku retags the old image; production
  never flips to a broken build.
- **Rate limits during builds.** Anything fetching external APIs at build
  time (blog ↔ GitHub) needs a token and/or batching; the pi's IP shares
  one unauthenticated quota across all builds in an hour.
- **cloudflared DNS vs published apps.** Published-application routes in
  the dashboard create the DNS record and ingress in one step — no pi
  shell needed, which matters because only `dokku@` has key auth.

## 9. Current fleet (2026-07-07)

| App | What | Repo |
|---|---|---|
| blog | Astro site + portfolio (GitHub stats at build time) | `~/repos/personal-site` |
| status | statusgen hub + boards | `~/status-site` |
| watts | electric cost calculator, EIA rates cron | `~/watts-site` |
| vault | sign-in + user storage (Swift/HB2; Node revert in `~/repos/vault`) | `~/repos/vault-hb` |
| head2head | implementation-shootout reports + community proposals | `~/head2head-site` |
