# What a day of Claude Code actually costs — 2026-07-07

Real numbers, pulled from Claude Code's local transcripts (per-message token
usage, deduplicated, priced at each model's true API rate). Context: Claude
Fable 5 is included in the Max plan through **July 12, 2026**; after that it
moves to prepaid usage credits at API rates. Everything below was **$0
out-of-pocket** — covered by the Max subscription.

## The headline

| | |
|---|---|
| API-equivalent value of the whole day | **$830.08** |
| Actually paid | **$0** (Max plan) |
| The big build session, all on Fable 5 | **$158.94** |
| Same session if run on Opus 4.8 | **~$80** |

## By model, at each model's own rate

| Model | Rate (in/out per MTok) | Calls | Output tokens | API-equivalent |
|---|---|---:|---:|---:|
| Opus 4.8 | $5 / $25 | 1,315 | 1.85M | **$517.78** |
| Fable 5 (main build session) | $10 / $50 | 382 | 380K | **$158.94** |
| Fable 5 (other sessions) | $10 / $50 | 407 | 226K | **$137.67** |
| Haiku 4.5 | $1 / $5 | 1,103 | 431K | **$15.70** |
| **Total** | | **3,207** | **2.9M** | **$830.08** |

**The Haiku line is the story:** nearly as many calls as Opus, at 3% of the
cost. "Haiku for volume, big models for judgment" is measurably the right
split.

## Where the money actually goes

Cost in a long agentic session isn't what the model *writes* — it's what it
*re-reads*. Every API call replays the conversation so far. Today that meant
~1B cache-read tokens across the day. Prompt caching (reads bill at 10% of
input rate) is the only reason a day like this is affordable: uncached, the
same day would have been five figures.

| Cost component (Fable build session) | Share |
|---|---|
| Cache reads (re-reading context) | ~65% |
| Cache writes | ~21% |
| Output (what the model wrote) | ~12% |
| Fresh input | ~2% |

## What the $158.94 Fable session bought

One working day, one session:

- **watts.jimmyhoughjr.net** — electric cost calculator: EIA state-rate lookup
  with a monthly self-refreshing cron, seasonal per-device modeling, saved
  rate profiles, charts
- **vault.jimmyhoughjr.net** — sign-in (Apple/Google OIDC) + per-app user
  storage service, written in Node, **ported to Swift/Hummingbird 2**, and
  swapped live with zero downtime (RSS: 54 MB → 24.7 MB)
- **head2head.jimmyhoughjr.net** — published benchmark report of the
  Node-vs-Swift bout, plus community bout submissions (live, awaiting OAuth)
- **docs.jimmyhoughjr.net** — the from-nothing platform playbook, public on
  GitHub — including a script that publishes new Cloudflare tunnel routes via
  API (no dashboard), which it used to publish itself
- Blog landing/portfolio overhaul (live GitHub repo stats), status boards for
  the new fleet, footer nav, prev/next posts

## Fable 5 pricing context (July 2026)

- Included in Pro/Max/Team plans through **2026-07-12** (up to 50% of weekly limits)
- After: **usage credits** at $10/$50 per MTok — 2× Opus 4.8, most expensive
  GA Claude pricing to date; enable under Settings → Usage on claude.ai
- No credits enabled → Fable simply stops; plans continue covering Opus 4.8 etc.
- Anthropic says subscription access returns "when capacity allows"

## Methodology

Summed `usage` fields (input, output, cache-write 5m/1h, cache-read) from
every assistant message in today's `~/.claude/projects/*/…jsonl` transcripts,
deduplicated by message + request ID, priced per model: in/out at list rate,
cache writes at 1.25× (5-min TTL) or 2× (1-hour TTL) input rate, cache reads
at 0.1× input rate. Single-day snapshot; an unusually heavy day (crash-resume,
three workstreams, a Swift toolchain compiled on an ARM SBC — twice).

*Compiled by Claude (Fable 5) from local usage data, 2026-07-07.*
