#!/usr/bin/env python3
"""Daily Claude Code usage ledger.

Scans every Claude Code transcript on this Mac (~/.claude/projects/*/*.jsonl),
tallies per-model token usage for one day, prices it at true API rates, and
maintains a running ledger showing what the subscription is saving.

Usage:  usage-report.py [YYYY-MM-DD]   (default: today)
        Then commit/push are handled automatically (skipped cleanly offline).

Output: ~/repos/docs/data/usage-ledger.json  (data, one entry per day)
        ~/repos/docs/claude-usage-ledger.md  (rendered report, on docs site)
"""
import json, glob, os, sys, subprocess, datetime, collections

HOME = os.path.expanduser("~")
DOCS = os.path.join(HOME, "repos/docs")
SITE = os.path.join(HOME, "docs-site")
LEDGER = os.path.join(DOCS, "data/usage-ledger.json")
REPORT = os.path.join(DOCS, "claude-usage-ledger.md")

PLAN_MONTHLY = 200.00  # $/mo — edit to your actual Max plan price

# (input $/MTok, output $/MTok) — cache write 5m=1.25x, 1h=2x, read=0.1x input
RATES = [("fable", (10, 50)), ("opus", (5, 25)), ("sonnet", (3, 15)), ("haiku", (1, 5))]

def rate_for(model):
    for key, r in RATES:
        if key in model:
            return r
    return None

def scan(day):
    """Tally usage for `day` (datetime.date) across all projects."""
    per = collections.defaultdict(lambda: {"n": 0, "in": 0, "out": 0, "cw5": 0, "cw1h": 0, "cr": 0})
    seen = set()
    day_iso = day.isoformat()
    for f in glob.glob(HOME + "/.claude/projects/*/*.jsonl"):
        # transcripts are append-only: skip files last touched before the day
        if datetime.date.fromtimestamp(os.path.getmtime(f)) < day:
            continue
        try:
            fh = open(f, errors="replace")
        except OSError:
            continue
        for line in fh:
            try:
                e = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            ts = e.get("timestamp", "")
            if not ts:
                continue
            # timestamps are UTC ISO; convert to local date
            try:
                local = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
            except ValueError:
                continue
            if local.date().isoformat() != day_iso:
                continue
            m = e.get("message") or {}
            u, model = m.get("usage"), m.get("model")
            if not u or not model or model == "<synthetic>":
                continue
            key = (m.get("id"), e.get("requestId"))
            if key in seen:
                continue
            seen.add(key)
            t = per[model]
            t["n"] += 1
            t["in"] += u.get("input_tokens", 0)
            t["out"] += u.get("output_tokens", 0)
            cc = u.get("cache_creation") or {}
            if cc:
                t["cw5"] += cc.get("ephemeral_5m_input_tokens", 0)
                t["cw1h"] += cc.get("ephemeral_1h_input_tokens", 0)
            else:
                t["cw5"] += u.get("cache_creation_input_tokens", 0)
            t["cr"] += u.get("cache_read_input_tokens", 0)
    return per

def cost(t, r):
    i, o = r
    return (t["in"] * i + t["cw5"] * i * 1.25 + t["cw1h"] * i * 2.0
            + t["cr"] * i * 0.10 + t["out"] * o) / 1e6

def main():
    day = (datetime.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1
           else datetime.date.today())
    per = scan(day)

    models = {}
    for model, t in per.items():
        r = rate_for(model)
        models[model] = dict(t, cost=round(cost(t, r), 2) if r else None)
    day_total = round(sum(m["cost"] or 0 for m in models.values()), 2)

    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    try:
        ledger = json.load(open(LEDGER))
    except (OSError, json.JSONDecodeError):
        ledger = {"days": {}}
    ledger["days"][day.isoformat()] = {
        "models": models, "cost": day_total,
        "calls": sum(m["n"] for m in models.values()),
        "out": sum(m["out"] for m in models.values()),
    }
    json.dump(ledger, open(LEDGER, "w"), indent=1, sort_keys=True)

    generated = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    render(ledger, day, generated)
    entry = ledger["days"][day.isoformat()]
    stamp_board(f"{generated} · ${entry['cost']:,.0f} today ({entry['calls']} calls)")
    print(f"{day}: {day_total:,.2f} USD API-equivalent "
          f"({ledger['days'][day.isoformat()]['calls']} calls)")
    publish(day)

def short(model):
    for key, _ in RATES:
        if key in model:
            return key.capitalize()
    return model

def render(ledger, day, generated):
    days = dict(sorted(ledger["days"].items(), reverse=True))
    month = day.strftime("%Y-%m")
    mtd = [d for d in days if d.startswith(month)]
    mtd_total = sum(days[d]["cost"] for d in mtd)
    all_total = sum(d["cost"] for d in days.values())

    L = []
    L.append("# Claude usage ledger — what the plan saves\n")
    L.append(f"*Generated {generated} — refreshed on every status push and nightly at 23:45.*\n")
    L.append("Daily API-equivalent value of all Claude Code usage on this machine,")
    L.append("from local transcripts, priced at each model's true API rate")
    L.append(f"(cache writes 1.25×/2×, reads 0.1×). Plan cost assumed **${PLAN_MONTHLY:,.0f}/mo** —")
    L.append("subscription usage bills $0, so this is what the plan absorbs.\n")

    L.append(f"## {day.strftime('%B %Y')} so far\n")
    L.append("| | |")
    L.append("|---|---|")
    L.append(f"| API-equivalent, month to date | **${mtd_total:,.2f}** |")
    L.append(f"| Plan cost | ${PLAN_MONTHLY:,.2f}/mo |")
    mult = mtd_total / PLAN_MONTHLY if PLAN_MONTHLY else 0
    L.append(f"| Coverage multiple | **{mult:,.1f}×** the subscription price |")
    L.append(f"| Days recorded | {len(mtd)} |\n")

    L.append("## Daily log\n")
    L.append("| Date | Calls | Output tokens | Models (API-equivalent) | Day total |")
    L.append("|---|---:|---:|---|---:|")
    for d, v in days.items():
        parts = ", ".join(
            f"{short(m)} ${t['cost']:,.0f}"
            for m, t in sorted(v["models"].items(), key=lambda kv: -(kv[1]["cost"] or 0))
            if t["cost"] is not None)
        L.append(f"| {d} | {v['calls']:,} | {v['out']:,} | {parts} | **${v['cost']:,.2f}** |")
    L.append(f"\nAll-time recorded: **${all_total:,.2f}** across {len(days)} day(s).\n")

    latest = days[day.isoformat()] if day.isoformat() in days else None
    if latest:
        L.append(f"## Breakdown — {day.isoformat()}\n")
        L.append("| Model | Calls | Uncached in | Cache write | Cache read | Output | Cost |")
        L.append("|---|---:|---:|---:|---:|---:|---:|")
        for m, t in sorted(latest["models"].items(), key=lambda kv: -(kv[1]["cost"] or 0)):
            cw = t["cw5"] + t["cw1h"]
            c = f"${t['cost']:,.2f}" if t["cost"] is not None else "?"
            L.append(f"| {m} | {t['n']:,} | {t['in']:,} | {cw:,} | {t['cr']:,} | {t['out']:,} | {c} |")

    L.append("\n*Generated by `docs/bin/usage-report.py` — runs on every status push and nightly at 23:45 via launchd.*")
    open(REPORT, "w").write("\n".join(L) + "\n")

def stamp_board(generated):
    """Show the generation time on the Clauffice Reports card (deployed by the next status push)."""
    board_path = os.path.join(HOME, "status-site/clauffice/board.json")
    try:
        board = json.load(open(board_path))
    except (OSError, json.JSONDecodeError):
        return
    for s in board.get("sections", []):
        if s.get("title") != "Reports":
            continue
        for item in s.get("items", []):
            if "claude-usage-ledger" in item.get("href", ""):
                item["meta"] = f"Generated {generated} · nightly 23:45 + every status push"
        json.dump(board, open(board_path, "w"), indent=2)

def publish(day):
    def run(cmd, cwd):
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True).returncode == 0

    run(["git", "add", "-A"], DOCS)
    run(["git", "commit", "-m", f"usage ledger: {day}"], DOCS)
    if not run(["git", "push", "origin", "main"], DOCS):
        print("note: github push failed (offline?) — committed locally")
    if run(["./sync-docs.sh"], SITE):
        run(["git", "add", "-A"], SITE)
        run(["git", "commit", "-m", f"sync: usage ledger {day}"], SITE)
        if not run(["git", "push", "dokku", "main"], SITE):
            print("note: dokku push failed — committed locally, next run retries")

if __name__ == "__main__":
    main()
