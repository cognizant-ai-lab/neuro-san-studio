# Task verification: PTO provenance prototype

An experimental mechanism that checks whether an AI agent's tool call actually did what it claimed, instead of
trusting the agent's (or the tool's) word.

The example task is booking paid time off (PTO). An employee asks an agent network to schedule a day off; the agent
calls a scheduling tool, the tool replies "submitted", and the agent tells the employee "done". That reply can be
false: the tool may have written nothing, the wrong date, the wrong employee, or the booking twice. The agent cannot
tell. This prototype checks the system of record after every call and keeps a tamper-evident record of what it found.

## Status

- **Experimental research code.** Not part of the studio's examples, and not served by default: the network is listed
  only in this folder's own manifest, not in `registries/manifest.hocon`.
- **Self-contained.** Everything lives in [pto_provenance/](pto_provenance/). Nothing outside this folder is changed.
- **Not run by CI.** The project's CI collects tests from `tests/` only, so run this folder's tests by hand (below).

## How it works

A langchain middleware sits on the call between the agent and the scheduling tool. For every call it:

1. **Tags the call** with a random idempotency key. The middleware creates the key; the agent never chooses or sees
   it, so it cannot point a failed call at another call's evidence.
2. **Records the request** in a provenance graph before the tool runs.
3. **Runs the tool**, which writes one row to a spoof SQLite HR database, stamped with the key.
4. **Records the tool's reply.**
5. **Checks the database** through a read-only connection, with a deterministic verifier (no LLM), and records the
   verdict.
6. **Anchors the graph**: copies its newest hash to a separate append-only log.
7. **Returns the tool's reply unchanged.** The verdict is evidence for people; it is not fed back to the agent.

The graph is hash-linked: every node stores a SHA-256 hash of its contents and of the earlier nodes it links to, so an
edited, removed or reordered node is detected. A record rewritten with every later hash recomputed passes that check;
the anchor catches it, because the rewritten record no longer ends at the anchored hash.

### Verdicts

| Verdict | Meaning |
|---|---|
| `verified` | The tool reported success, and exactly one row with this key matches the request. |
| `failure_confirmed` | The tool reported an error, and nothing was written: an honest failure. |
| `not_verified` | Anything else. The verdict lists each problem (no row, extra rows, a wrong field). |

### Faults

To show the verifier catching failures, the tool can fake one fault at a time. In every fault except `error`, the tool
still replies "submitted" with the requested details, so the agent cannot tell anything went wrong.

| Fault | What the tool does |
|---|---|
| `none` | Writes the booking as asked. |
| `no_write` | Writes nothing. |
| `wrong_dates` | Writes Dec 31 instead of the requested dates. |
| `wrong_employee` | Books employee E-2077 instead. |
| `duplicate` | Writes the booking twice. |
| `error` | Reports an error and writes nothing. |

The fault comes from the `PTO_FAULT` environment variable if set, otherwise from a `fault.txt` file next to the HR
database (written by the terminal verifier), otherwise `none`.

## Files

All paths are under [pto_provenance/](pto_provenance/).

| File | Role |
|---|---|
| `provenance_middleware.py` | The middleware: runs the steps above on every watched tool call. |
| `coded_tools/schedule_pto.py` | The scheduling tool: writes the booking tagged with the key, or fakes a fault. |
| `hr_database.py` | The spoof HR database (SQLite): employees and PTO requests. |
| `pto_verifier.py` | The verifier: compares the request, the reply and the rows, and returns a verdict. |
| `provenance_graph.py` | The hash-linked, append-only record of one session. |
| `anchor_log.py` | The separate log of the graph's newest hash. |
| `idempotency_context.py` | Passes the key from the middleware to the tool. |
| `fault_switch.py` | Decides which fault the tool fakes. |
| `pto_runner.py` | Runs the network with a real LLM, once per fault, and logs the verdicts. |
| `verifier_console.py` | The demo's terminal screen: shows each verdict live and switches faults. |
| `registries/pto_network.hocon` | The agent network: a trimmed copy of the intranet example's leave-booking chain. |
| `registries/manifest.hocon` | This folder's manifest, listing only the network above. |
| `tests/` | Unit tests, including attack tests. |

Run outputs (graphs, anchor logs, the HR database) are written to `pto_provenance/runs/`, which git ignores.

## Running it

Run every command from the repository root, with the virtual environment active and `PYTHONPATH` set to the
repository root (see [CONTRIBUTING.md](../CONTRIBUTING.md)).

### Tests

No LLM or network access needed:

```bash
python -m pytest task_verification/pto_provenance/tests
```

### Runner (real LLM)

The network uses Claude Haiku 4.5 through `langchain_anthropic`, so it needs `ANTHROPIC_API_KEY` in `.env`. Each run
makes real LLM calls.

```bash
python -m task_verification.pto_provenance.pto_runner                     # every fault
python -m task_verification.pto_provenance.pto_runner --faults none no_write
```

Each run gets a fresh HR database and graph, sends "I'm employee E-1042. Please schedule PTO for me on December 3,
2026.", and logs the agent's answer next to each verdict.

### Demo: studio UI plus the terminal verifier

1. Start the studio with this folder's manifest:

    ```bash
    AGENT_MANIFEST_FILE=$PWD/task_verification/pto_provenance/registries/manifest.hocon python -m neuro_san_studio run
    ```

2. In a second terminal (macOS or Linux), start the verifier. It resets the HR database and the fault to `none`:

    ```bash
    python -m task_verification.pto_provenance.verifier_console
    ```

3. Open the studio UI, pick `pto_network`, and ask it to schedule PTO. Each booking appears in the verifier terminal
   with its verdict. Press `1`-`6` to switch the fault, `q` to quit.

Things to know:

- If `ANTHROPIC_API_KEY` is set in your shell, it overrides the one in `.env`.
- If `PTO_FAULT` is set in your shell or `.env`, it overrides the verifier's fault keys.
- The server keeps one graph in memory from its first PTO call. Restart the server when you restart the verifier.

## Limits

- **Same machine.** The graph and the anchor log live on the machine that runs the agent. The LLM cannot reach them,
  but other code in that process could rewrite both consistently. A deployment would keep the anchor log on a separate
  server or write-once storage, and could have an independent service sign each node.
- **The action, not the intent.** The verifier checks that the tool did what the agent asked. It does not check that
  the agent asked for what the employee wanted, or that the agent's final message matches the verdict.
- **The employee comes from the agent.** The employee ID is a tool argument, so an agent acting for one employee could
  book another and the booking would still verify. A deployment would take it from the signed-in user.
- **A crashing tool leaves its call unverified.** The graph lists such a call as made but never checked.
- **Branch pointers are not checked.** The graph's lookup table of each branch's newest node is not covered by the
  hashes, and the integrity check does not rebuild it yet.
