# What a day of Claude Code actually costs — 2026-07-07

Real numbers from Claude Code's local transcripts: per-message token usage,
deduplicated, filtered by message timestamp, priced at each model's true API
rate. Context: Claude Fable 5 is included in the Max plan through **July 12,
2026**; after that it moves to prepaid usage credits at API rates. Everything
below cost **$0 out-of-pocket** — covered by the Max subscription.

> **Correction:** an earlier draft put the day at ~$830. That version counted
> whole transcript files, which swept in messages from July 1–6 sitting in
> still-active session files. These figures filter by each message's actual
> timestamp.

## The headline

| | |
|---|---|
| API-equivalent value, July 7 | **$423.21** |
| Actually paid | **$0** (Max plan) |
| The big build session (all Fable 5) | **$158.94** |
| Same session if run on Opus 4.8 | **~$80** |
| Trailing 9 days total (Jun 29 – Jul 7) | **$840.59** |

July 7 alone was half the trailing nine days — an unusually heavy day
(crash-resume, three workstreams, a Swift toolchain compiled twice on an ARM
SBC).

## July 7 by model, each at its own rate

| Model | Rate (in/out per MTok) | Calls | Output tokens | API-equivalent |
|---|---|---:|---:|---:|
| Opus 4.8 | $5 / $25 | 609 | 1.04M | **$250.31** |
| Fable 5 | $10 / $50 | 417 | 418K | **$172.90** |
| **Total** | | **1,026** | **1.45M** | **$423.21** |

## The Haiku lesson (trailing 9 days)

No Haiku ran on the 7th — but across Jun 29 – Jul 7, **Haiku 4.5 handled
1,103 calls for a total of $15.70**. The days that leaned on it cost $2–4
*per day*; the days that ran everything on big models cost $100–423. Same
tooling, wildly different unit economics: "Haiku for volume, big models for
judgment" is measurably the right split.

## Where the money actually goes

Cost in a long agentic session isn't what the model *writes* — it's what it
*re-reads*. Every API call replays the conversation so far; July 7 re-read
~475M cache-read tokens. Prompt caching (reads bill at 10% of the input rate)
is the only reason such a day is affordable — and reads still ended up as
**~70% of the day's cost**. Output — everything the models actually wrote —
was only ~20%.

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
every assistant message across all `~/.claude/projects/*/*.jsonl` transcripts,
deduplicated by message + request ID, attributed to days by message timestamp
(local time), priced per model: in/out at list rate, cache writes at 1.25×
(5-min TTL) or 2× (1-hour TTL) input rate, cache reads at 0.1× input rate.

A running daily version of this analysis now lives at the
[Claude usage ledger](https://docs.jimmyhoughjr.net/#claude-usage-ledger.md),
regenerated nightly.

*Compiled by Claude (Fable 5) from local usage data.*
