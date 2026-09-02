# The Rookery bench — subscription auth and the spawn floor

*Bench run 1, 2026-09-02. Claude Code 2.1.258 on darwin 25.6.0. 17 headless runs, all exit 0.*

Rookery is a spike: a Hummingbird 2 server that a Claude session talks to, which starts agents,
registers their tools and skills, and tracks them on a board. Two questions had to be answered before
any Swift was written. This report answers both and records a third finding that arrived uninvited.

## The three verdicts

| Question | Verdict | Note |
|---|---|---|
| Does a Max subscription drive headless Claude Code? | **Pass** | Exit 0 with both key variables unset. |
| Do concurrent agents share one credential store safely? | **Pass** | 12 of 12 clean at once. |
| Does a token refresh race between agents? | **Not tested** | No token was near expiry. Still open. |

## Test 1 — the subscription drives it

The worry was that headless Claude Code falls back to API billing. It does not. Both credential
variables were removed from the environment before the call, and the call ran.

```
env -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN \
  claude -p "Reply with exactly: OK" --output-format json

exit=0   wall_ms=2846   duration_api_ms=2286
stderr: (empty)
service_tier: "standard"   costBasis: "list"   provider: "firstParty"
```

The reported `total_cost_usd` is list-price accounting and not a charge. Under the plan it reads as
window consumption.

One trap goes into the build. The credential chain reads `ANTHROPIC_API_KEY` first, then
`ANTHROPIC_AUTH_TOKEN`, which outranks the session profile **even when it is empty**, and only then the
account profile. One stray variable in a Dockerfile or an inherited CI secret moves an agent to API
billing with no error. Rookery must assert the resolved credential source at each agent boot and show
it on the board. Do not trust the setup.

## Test 2 — concurrency on one credential store

Agents ran as concurrent processes against one shared credential store. This is the topology under
consideration: agents as processes in worktrees, not as nested containers.

| Batch | Wall ms | Slowest agent | API median ms | Failures |
|---|---:|---:|---:|---:|
| 1 agent | 2,846 | 2,846 | 2,286 | 0 |
| 5 agents | 5,286 | 4,632 | — | 0 |
| 12 agents | 6,116 | 6,009 | 2,493 | 0 |

All 17 processes exited 0. No rate limiting, no authentication error, no stderr.

The API median moved very little: 2,286 ms alone against 2,493 ms at twelve-way concurrency. The
service does not queue us at this scale. The growth in wall time is local process startup. Twelve
agents finished in 6.1 seconds. The same work in sequence projects to about 34 seconds.

## The floor — every spawn pays a fixed toll

A Claude Code process loads **21,036 tokens** of context before it reads its prompt. This is the system
prompt, the tool definitions, the skills listing and the project files. The number was identical in
three independent batches, at n=1, n=5 and n=12. That agreement is the strongest internal check in the
run.

| Token class | 5 agents | 12 agents |
|---|---:|---:|
| Cache creation | 17,110 | 23,954 |
| Cache read | 88,020 | 228,358 |
| Input | 50 | 120 |
| Output | 226 | 580 |
| **Total context** | **105,180** | **252,432** |
| List cost | $0.0489 | $0.0851 |

Twelve agents that replied `A1` through `A12` used 252,432 tokens. Almost none of it was the work.

At twelve-way, 228,358 of the 252,432 tokens were cache reads, about 90%. The floor is almost free once
a cache is warm. A cold container has no cache and pays the full toll at creation rates: about $0.1315
against $0.0220 on Opus, a multiple of six.

## What the usage ledger says

The [usage ledger](claude-usage-ledger.md) prices real work at true API rates. Its 2026-09-01 breakdown
records Opus doing actual sessions rather than trivial prompts.

| 2026-09-01, claude-opus-5 | Day total | Per call |
|---|---:|---:|
| Calls | 606 | — |
| Cache read | 126,586,311 | 208,888 |
| Cache write | 1,701,780 | 2,808 |
| Output | 372,087 | 614 |
| **API-equivalent** | **$88.90** | **$0.1467** |

A real working call carries about 211,700 tokens of context.

**This corrects the finding above.** The 21,036-token floor is about 10% of one real call. It is not
the dominant cost. It dominates only for trivial spawns. An agent that takes two real turns has already
amortised it, and at twenty turns it is under 1% of that agent's consumption.

The correction also weakens the cold-versus-warm argument. Six times a small number is still a small
number: about $0.11 more per spawn on Opus. That matters for many short-lived agents and is close to
noise for a team of long-lived ones. The nesting question must be decided on isolation and operations,
not on this multiple.

The useful sizing number is blunter. At 606 calls a day and $0.1467 a call, one working agent consumes
about what one person consumes. A three-agent team is three people. The all-time ledger average is
$145.70 a day across 65 recorded days, so a standing team is a multiple of current load.

The ledger cannot see the plan's **rate window**. It prices the value the plan absorbs, not what the
window meters. Team sizing still needs a window measurement that this bench did not take.

## What it means for the build

- **Verify at boot.** An empty variable silently shadows the session profile, so each agent reports its
  resolved credential source through its hook at start. This is cheap, and it is the difference between
  a constraint and a hope.
- **The host must be Linux.** There is no `~/.claude/.credentials.json` on the Mac. The credential is in
  the Keychain, so it cannot be mounted into a Linux container. Rookery runs where the credential is a
  file: the pi, the opi, or the mini's virtual machine. This rules the Mac out as the host.
- **A queue can wait.** No rate limiting appeared at twelve, and API latency stayed flat. Concurrency is
  not the near-term governor. The rate window is.
- **Size teams as multiples of a person.** One agent is about one person of load.
- **The nesting fork stays open.** These numbers do not decide it.

## What this run does not show

- **The refresh boundary.** Contention is proven safe. No token was near expiry, so no refresh fired.
  Whether concurrent processes race on refresh is still open and still worth an hour on a Linux box.
- **Containers.** The Docker daemon was down and colima was stopped. The Keychain finding makes the Mac
  container path irrelevant in any case.
- **Real agents.** These were single-turn trivial prompts on Haiku. Turn count and model tier are both
  multipliers this run did not measure.
- **Anything on Linux.** `ssh 192.168.0.103` returned `Permission denied (publickey)` from the job, so
  no estate box was reachable.

A Keychain read was blocked by the permission classifier. Authentication was proven by running it, not
by reading the credential.
