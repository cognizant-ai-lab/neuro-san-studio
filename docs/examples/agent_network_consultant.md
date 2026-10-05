# Agent Network Consultant

The **Agent Network Consultant** is a multi-agent system that tests and improves an existing agent network while
protecting its intended behavior. Given a network and its generated fixtures, it will:

- Run the network's fixtures in process.

- Diagnose whether each failure belongs to the network, the fixture, the network structure, a coded tool, or an
  unavailable source of grounded data.

- Make targeted changes to agent `instructions` and `description` fields.

- Correct a fixture only when the fixture's expectation is wrong.

- Delegate required structural changes to Agent Network Designer.

- Re-run affected fixtures and confirm successful changes against the full fixture suite.

Note that:

- Consultant runs through direct, in-process Neuro SAN sessions. A separate Neuro SAN server is not required. nsflow
  is installed with Studio and has a self improvement tab which can launch Consultant as a background job.

---

## File

- Agent network: [agent_network_consultant.hocon](../../registries/agent_network_consultant.hocon)
- CLI [orchestrator](../../neuro_san_studio/agent_network_consultant/network_consultant_orchestrator.py)
- Command reference: [`ns consultant`](../cli/consultant.md)

---

## Description

Agent Network Consultant combines deterministic Python orchestration with an agent network responsible for diagnosis
and repair:

1. The CLI validates the request and resolves the target network. With `--hocon-file`, it uses that existing file.

2. When the target has no fixtures, or `--force-generate` is set, the orchestrator calls
   [Agent Network Test Generator](../agent_network_test_generator.md) to create them.

3. [`FixtureRunner`](../../neuro_san_studio/agent_network_consultant/fixture_runner.py) executes the fixtures directly.
   It records each scorecard, redacts sensitive error text, and separates infrastructure failures from behavioral
   failures.

4. [`ThinkingTraceCollector`](../../neuro_san_studio/agent_network_consultant/thinking_trace_collector.py) filters and
   stores the useful per-agent traces for failed fixtures. System prompts, chat context, and cost telemetry are not
   copied into the diagnostic trace.

5. The `consultant` frontman classifies every failure as `TOOL ISSUE`, `UNGROUNDED`, `AGENT FIX`, `FIXTURE FIX`,
   `STRUCTURAL`, or `AMBIGUOUS`.

6. The frontman delegates actionable failures to a specialist:

   - `network_behavior_fixer` changes only the responsible agents' instructions or descriptions.
   - `fixture_expectation_fixer` changes only a demonstrated invalid fixture expectation.
   - `structural_change_assessor` sends a narrowly scoped modification request to Agent Network Designer.

7. [`ConsultantPersistenceMiddleware`](../../middleware/agent_network_consultant/consultant_persistence_middleware.py)
   validates instruction changes and applies them to the original HOCON source. It does not regenerate the complete
   network file for an instruction-only repair. When the source omits execution limits, the source editor also adds
   bounded `max_steps` and `max_execution_seconds` defaults.

8. The next iteration retests only the fixtures that were failing. When that subset passes, Consultant runs the full
   suite to detect regressions.

9. The loop stops after a verified pass, an actionable infrastructure or tool error, a clarification request, an
   acceptable full-suite result, a plateau, or the configured iteration limit. After a plateau or iteration limit,
   Consultant restores and verifies the best HOCON version observed during the run.

The Python orchestrator owns repeatable operations such as running fixtures, scoring results, rollback, cleanup, and
file paths. The agent network owns language-based diagnosis and deciding which narrowly scoped repair is justified.

---

## Usage

### Improve an Existing Network

The HOCON path is relative to `registries/`:

```bash
ns consultant \
  --hocon-file industry/intranet_agents.hocon
```

Add a direction only when the run has an additional goal:

```bash
ns consultant \
  --hocon-file industry/intranet_agents.hocon \
  --direction "Reduce token usage without changing existing behavior."
```

### Run Selected Fixtures

Pass the exact fixture filenames, including `.hocon`, as one space-separated list:

```bash
ns consultant \
  --hocon-file industry/intranet_agents.hocon \
  --only-fixtures employee_policy.hocon employee_benefits.hocon
```

Consultant begins with that subset. Before declaring success, it runs the complete fixture suite.

### Create and Improve a Network

Use `--use-case` instead of `--hocon-file` to create a network through Agent Network Designer before generating and
running its fixtures:

```bash
ns consultant \
  --use-case "An internal support network for employee policy and benefit questions"
```

Run `ns consultant --help` or see the [command reference](../cli/consultant.md) for every option.

---

## Example Run

### Command

```bash
ns consultant \
  --hocon-file generated/employee_support.hocon \
  --direction "Preserve existing behavior while fixing failing tests."
```

### Representative Progress

The exact counts and diagnoses depend on the target network and fixtures. A successful repair follows this shape:

```text
Target network: generated/employee_support
Existing test fixtures found; skipping ANTeGen.
--- Iteration 1/20: running tests ---
2/6 fixtures passing.
Consulting consultant to fix failing agents' instructions...
--- Iteration 2/20: running tests ---
4/4 fixtures passing (subset re-check).
Subset re-check passed; running full suite once to confirm no regressions...
All tests passing. Network is satisfiable.
```

If Consultant identifies a broken coded tool, an ungrounded expectation under the default policy, or an infrastructure
failure, it stops and reports the actionable problem instead of rewriting the network to hide it.

---

## Architecture Overview

### CLI Orchestrator: `NetworkConsultantOrchestrator`

[`NetworkConsultantOrchestrator`](../../neuro_san_studio/agent_network_consultant/network_consultant_orchestrator.py)
is the command's deterministic control plane.

**Key responsibilities:**

- Validate command options and resolve the target HOCON file.
- Create direct sessions for Consultant, Designer, and Test Generator.
- Generate or reuse fixtures.
- Run repair iterations and fixture-subset rechecks.
- Track full-suite and per-criterion progress.
- Restore the best-known HOCON after a plateau or iteration ceiling.
- Restore temporary fixture ratios and remove temporary Git worktrees during cleanup.

### Frontman Agent: `consultant`

The first agent in
[agent_network_consultant.hocon](../../registries/agent_network_consultant.hocon) is the diagnosis and routing
frontman.

**Key responsibilities:**

- Examine every failing fixture and its scorecard evidence.
- Read the job log for coded-tool failures when an nsflow job log is available.
- Read a fixture's filtered thinking trace when the failure evidence is insufficient.
- Assign exactly one failure category.
- Delegate only to the specialist responsible for that category.
- Return machine-readable control lines consumed by the Python workflow.

**Available agents and tools:**

- `network_behavior_fixer`
- `fixture_expectation_fixer`
- `structural_change_assessor`
- `read_thinking_trace`
- `read_job_log`

### Repair Agents

#### `network_behavior_fixer`

This agent handles `AGENT FIX` failures. It reads the run scratchpad, studies the failure and optional thinking trace,
groups failures by responsible agent, and sends targeted change requests to `write_all_instructions`. It may change
only agent instructions and descriptions; it cannot add, remove, or rewire tools.

After choosing a repair, it appends the prior attempt's outcome and the current attempt to `network_scratchpad`.
This prevents later rounds from silently repeating a failed approach.

#### `fixture_expectation_fixer`

This agent handles `FIXTURE FIX` failures. It must establish that the expectation is wrong before changing anything.
It copies the original fixture, changes only the invalid expectation, validates the complete result through
`validate_test_fixture`, and persists it through `persist_test_fixture` using the trusted original fixture path.

When the selected `--ungrounded` policy is `continue`, this agent can remove only the named criteria that require data
the network has no available way to obtain.

#### `structural_change_assessor`

This agent handles failures that cannot be fixed by editing instructions or descriptions. It identifies one required
add, remove, or rewire operation and calls `/agent_network_designer` in `modify` mode with that narrowly scoped
request.

### Consultant Instruction Writers

`write_all_instructions` and `instructions_writer` are loaded from
[agent_network_instruction_improver.hocon](../../registries/agent_network_instruction_improver.hocon).
The include is owned by Consultant and leaves Agent Network Instructions Editor unchanged. Consultant overlays its
repair-specific writing rules and definition middleware.

### Diagnostic Coded Tools

#### `read_thinking_trace`

[`ReadThinkingTrace`](../../coded_tools/agent_network_consultant/read_thinking_trace.py) reads one failed fixture's
filtered trace from `logs/thinking_dir/improvement/`. A call without `agent_name` lists available agents; a second call
can retrieve one selected agent's trace.

#### `read_job_log`

[`ReadJobLog`](../../coded_tools/agent_network_consultant/read_job_log.py) reads a bounded tail of the current nsflow
job log. It supplies round-level exceptions and progress rather than one fixture's reasoning trace. Outside an nsflow
job, it returns an explicit error instead of guessing a log path.

#### `network_scratchpad`

[`NetworkScratchpad`](../../coded_tools/agent_network_consultant/network_scratchpad.py) stores append-only attempt
history for one network during one continuous run. It uses Studio's shared managed-file read and write tools. The
orchestrator clears that network's scratchpad when a fresh run starts.

### Test Fixture Tools

Consultant reuses ANTeGen's `validate_test_fixture` and `persist_test_fixture` tools. This gives corrected fixtures the
same schema validation and persistence behavior used when the fixtures were created.

---

## Middleware

### Definition Middleware

[`ConsultantDefinitionMiddleware`](../../middleware/agent_network_consultant/consultant_definition_middleware.py)
extends Designer's definition middleware. It:

- Loads the target through Designer's normal definition-loading path.
- Uses Designer's shared common-instruction stripping before agents inspect or edit the definition.
- Retains the source file path needed for source-preserving persistence.
- Builds a complete diagnostic view that includes coded tools and other non-editable context.
- Redacts secret-bearing keys and recognizable credential values before exposing that context to an LLM.
- Stores a snapshot of the editable instruction and description fields for later change detection.

The shared runtime values are carried in `sly_data`, including the network definition, source path, diagnostic
context, editable-field snapshot, and trusted fixture-path mapping.

### Persistence Middleware

[`ConsultantPersistenceMiddleware`](../../middleware/agent_network_consultant/consultant_persistence_middleware.py)
extends Designer's persistence middleware while changing how successful edits reach disk. It:

- Compares the final editable fields with the snapshot captured during loading.
- Does nothing when no instruction or description changed.
- Runs the structural, toolbox, URL, and instruction validators before persistence.
- Sends validation errors back to the repairing agent for correction.
- Uses
  [`SourcePreservingHoconEditor`](../../middleware/agent_network_consultant/source_preserving_hocon_editor.py) to patch
  only changed `instructions` and `description` values in the original file.
- Adds bounded `max_steps` and `max_execution_seconds` defaults when those root settings are absent.
- Writes atomically after parsing and validating the resulting HOCON.

Structural changes are not forced through this source patcher. They are delegated to Agent Network Designer.

---

## Testing and Iteration Behavior

[`FixtureRunner`](../../neuro_san_studio/agent_network_consultant/fixture_runner.py) is not pytest. It executes Neuro
SAN fixture HOCONs directly through the same fixture driver used by the generated-test infrastructure. Fixtures remain
ordinary HOCON files under `tests/fixtures/<network-name>/`.

During iterative repair:

1. The first round establishes a baseline and the best-known HOCON snapshot.
2. Consultant repairs the current failures.
3. The next round retests only those failing fixture files.
4. A passing subset triggers a full-suite regression check.
5. Fixture count is the primary score; passed acceptance criteria break ties between rounds.
6. Three non-improving full-suite rounds form a plateau and restore the best-known HOCON.
7. A full-suite result of at least 80 percent can be accepted as good enough when regressions remain after a
   confirmation run.

Infrastructure failures stop the run before any network or fixture repair is attempted. Sensitive values in captured
exceptions are redacted before the messages are logged, returned, cached, or given to Consultant.

---

## nsflow Integration

Studio installs `nsflow` from `requirements.txt`, but Consultant's direct sessions do not require the nsflow server or
UI. When nsflow supplies `NSFLOW_JOB_ID` and `NSFLOW_JOB_DIR`, Consultant additionally writes:

- `<job-id>.progress.jsonl` for chart checkpoints.
- `<job-id>.results.json` for fixture verdicts.
- `<job-id>.tool_issues.txt` for coded-tool problems.
- `<job-id>.ungrounded.txt` for criteria that cannot be grounded.
- `<job-id>.question.txt` while a clarification is waiting for a response.
- `<job-id>.git_branch.txt` when Git snapshots are enabled.

`--max-iterations 0` runs the selected fixtures once without repairing the network in both direct and nsflow runs.
For an nsflow job, a complete-suite result is also cached once so the immediately following Self-Improve job can use
it as its first baseline without rerunning unchanged fixtures.

---

## Git Version Snapshots

`--git-versions` records meaningful HOCON checkpoints on a dedicated
`consultant-versions/<network>/<run-id>` branch. Configure the destination first:

```bash
export NETWORK_CONSULTANT_GIT_VERSIONS_REMOTE=upstream
ns consultant \
  --hocon-file industry/intranet_agents.hocon \
  --git-versions
```

The value can be an existing Git remote name or a repository URL. Consultant pushes directly to that destination. It
does not add or rewrite repository remotes, switch the user's branch, or commit the user's working tree. The command
reports an error before initialization when the environment variable is unset.

---

## Files and Temporary Data

- Target network: edited in place under `registries/`.
- Generated fixtures: `tests/fixtures/<network-name>/`.
- Filtered failure traces: `logs/thinking_dir/improvement/`.
- Per-run attempt history: `logs/network_consultant_scratchpad/`.
- One-shot nsflow generated-test cache: `/tmp/network_consultant_gentests_cache/`.
- Direct session thinking output: `/tmp/network_consultant_thinking/` and
  `/tmp/network_consultant_thinking.txt`.
- Raw test traces: a run-specific operating-system temporary directory with a
  `network_consultant_test_thinking_` prefix, unless `AGENT_TEST_THINKING_BASIS` was already supplied.
- Git worktree: a run-specific operating-system temporary directory with a `network_consultant_git_` prefix.

Consultant removes temporary directories it owns when their scope ends and restores caller-owned environment values.
It does not delete a caller-supplied thinking directory.

---

## Debugging Hints

- Run `ns validate registries/<network>.hocon` before Consultant when a target network does not load.
- Use exact fixture filenames, including `.hocon`, with `--only-fixtures`.
- Check `logs/thinking_dir/improvement/<fixture>.hocon.txt` when a behavioral diagnosis lacks evidence. The actual
  filename is the fixture basename followed by `.txt`, so a fixture named `case.hocon` produces `case.hocon.txt`.
- For an nsflow job, inspect its `<job-id>.log` for coded-tool exceptions. Direct CLI runs do not have that job log.
- An infrastructure error means Consultant intentionally made no repair. Fix the API key, import, timeout, or other
  runtime problem and run the command again.
- If the source-preserving editor reports an unsupported HOCON patch, change the relevant source style or make the
  structural edit through Agent Network Designer rather than forcing a partial rewrite.
- Use `--git-versions` when you want remotely visible checkpoints for each meaningful test result and repair.

---
