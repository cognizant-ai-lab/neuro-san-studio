# Agent Network Consultant

The **Agent Network Consultant** runs fixture-based tests against an agent network and can apply targeted changes to
address failures. Give it an existing network or a new use case, and it will:

- Generate test fixtures when needed.
- Run the fixtures and diagnose each failure.
- Repair agent instructions or an incorrect fixture expectation.
- Delegate structural changes that add, remove, or reconnect agents.
- Re-run the affected fixtures and confirm the result against the complete suite.

Note that:

- `ns consultant` runs direct Neuro SAN sessions in an isolated worker process. A separate Neuro SAN server is not
  required.
- The Consultant network is installed but disabled in the default server manifest. The command loads it directly.
- Existing network files are edited in place. Instruction-only repairs preserve unrelated HOCON source text.
- The Self Improvement tab requires an nsflow build containing the
  [companion integration](https://github.com/cognizant-ai-lab/nsflow/tree/2cefb47). The command works without the tab.

---

## File

- Agent network: [agent_network_consultant.hocon](../../registries/agent_network_consultant.hocon)
- Command reference: [`ns consultant`](../cli/consultant.md)

---

## Description

Agent Network Consultant separates repeatable test execution from language-based diagnosis and repair:

1. The command validates the request and selects an existing network with `--hocon-file`, or asks Agent Network
   Designer to create one from `--use-case`.
2. If fixtures do not exist, Agent Network Test Generator creates them. `--force-generate` requests a new generation
   pass even when fixtures are already present.
3. Consultant runs the fixtures directly and records their scorecards and filtered agent reasoning.
4. The frontman classifies each failure as a tool problem, an unavailable source of grounded data, an agent behavior
   problem, an incorrect fixture expectation, a structural problem, or an ambiguous requirement.
5. A specialist applies the narrowest justified change. Instruction repairs affect only the responsible agents;
   fixture repairs affect only a proven incorrect expectation; structural work is delegated to Designer.
6. Changed instructions and descriptions are validated and patched into the original HOCON without regenerating the
   complete file.
7. Consultant first retests the failed fixtures. When that subset passes, it runs the complete suite to detect
   regressions before stopping.

The run stops safely when all fixtures pass, a verified result meets the acceptance threshold, repeated repairs stop
improving the network, the iteration limit is reached, or a tool or infrastructure problem requires user action.

---

## Example Run

### Command

The HOCON path is relative to `registries/`. `--direction` is optional and describes behavior that repairs must
preserve.

```bash
ns consultant \
  --hocon-file industry/intranet_agents.hocon \
  --direction "Preserve the existing routing and response tone while fixing failures."
```

To begin with selected fixtures, provide their exact filenames after `--only-fixtures`:

```bash
ns consultant \
  --hocon-file industry/intranet_agents.hocon \
  --only-fixtures employee_policy.hocon employee_benefits.hocon
```

A passing subset is always followed by a complete-suite check.

### Representative Progress

```text
Target network: industry/intranet_agents
--- Iteration 1/20: running tests ---
2/6 fixtures passing.
Consulting Agent Network Consultant to fix failing agents' instructions...
--- Iteration 2/20: running tests ---
4/4 fixtures passing (subset re-check).
Subset re-check passed; running full suite once to confirm no regressions...
All tests passing after full-suite confirmation. Stopping without further changes.
```

---

## Architecture Overview

### CLI Orchestrator: `NetworkConsultantOrchestrator`

The CLI orchestrator owns the deterministic parts of a run:

- Resolve or create the target network.
- Generate or reuse fixtures.
- Run fixtures and collect results.
- Track improvement across repair rounds.
- Confirm focused repairs against the complete suite.
- Clean up temporary data owned by the run.

### Frontman Agent: `consultant`

The frontman examines the failure evidence and selects exactly one response for each failure. It can call:

- `network_behavior_fixer` for incorrect agent behavior.
- `fixture_expectation_fixer` for an invalid test expectation.
- `structural_change_assessor` for changes to agents, tools, or network connections.
- `read_thinking_trace` for one fixture's filtered agent reasoning.
- `read_job_log` for an active nsflow job's runtime errors.

The frontman reports tool problems and ungrounded requirements instead of changing the network to hide them. When a
requirement is ambiguous, it asks the user for clarification before continuing.

### Repair Agents

`network_behavior_fixer` groups related failures by responsible agent and requests only the required instruction or
description changes. It records previous attempts in a run-specific scratchpad so later rounds can avoid repeating a
failed approach.

`fixture_expectation_fixer` changes a fixture only after establishing that the expectation is wrong. The complete
fixture is validated before it is saved.

`structural_change_assessor` handles changes that cannot be expressed through instructions or descriptions. It sends
one narrowly scoped modification request to Agent Network Designer.

### Middleware

[`ConsultantDefinitionMiddleware`](../../middleware/agent_network_consultant/consultant_definition_middleware.py)
loads the target definition, prepares a redacted diagnostic view, and records the editable fields before repair.

[`ConsultantPersistenceMiddleware`](../../middleware/agent_network_consultant/consultant_persistence_middleware.py)
compares the repaired definition with that original snapshot, validates the result, and applies only changed
`instructions` and `description` values to the source file. Structural changes do not pass through this source
patcher.

---

## nsflow Integration

Direct `ns consultant` runs ask clarification questions in the terminal. When nsflow supplies a job context,
Consultant instead exchanges progress, results, tool issues, ungrounded criteria, and clarification answers through
the job directory. Both modes limit each clarification wait to five minutes and preserve the same Consultant
conversation after an answer arrives.

The command does not modify the caller's environment. It creates a copied environment for its worker process and
removes temporary directories that it owns when the run finishes.

---

## Files

- Target network: `registries/<network>.hocon`
- Generated fixtures: `tests/fixtures/<network>/`
- Filtered fixture traces: `logs/thinking_dir/improvement/<run-id>/`
- Run-specific repair history: `logs/agent_network_consultant_scratchpad/`

---

## Debugging Hints

- Run `ns validate registries/<network>.hocon` when the target does not load.
- Use exact fixture filenames, including `.hocon`, with `--only-fixtures`.
- Inspect `logs/thinking_dir/improvement/<run-id>/` when a behavioral diagnosis lacks evidence.
- For an nsflow job, inspect its job log for coded-tool exceptions.
- Resolve API-key, import, timeout, or other infrastructure failures before starting another repair run.
- Use Agent Network Designer for structural changes that cannot be represented as instruction or description edits.

Run `ns consultant --help` or read the [command reference](../cli/consultant.md) for all available options.
