# Agent Network Test Generator

The **Agent Network Test Generator** is an agent network that automatically generates
[data-driven test fixture HOCON files](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/test_case_hocon_reference.md)
for existing agent networks. Provide the name of an agent network and it will:

- Read the target network's HOCON definition (agents, instructions, metadata, sample queries).

- Analyze the network's capabilities and design test scenarios.

- Build and validate test fixture HOCON files with interactions, expected responses, and sly\_data.

- Save the fixtures under `tests/fixtures/<agent_name>/`.

Note:

- This tool writes files to your `tests/fixtures/` directory. Generated fixtures are not
automatically added to the integration test suite; you must manually register them in
[test\_integration\_test\_hocons.py](../tests/integration/test_integration_test_hocons.py)
if you want them to run as part of CI.

- The quality of generated test cases depends on the LLM. You should review the output
and adjust `gist` criteria, `keywords`, `value` checks, and `sly_data` as needed before
committing fixtures.

- An `OPENAI_API_KEY` (or equivalent) is required since the agents use an LLM
to analyze the target network and design test cases.

---

## File

[agent\_network\_test\_generator.hocon](../registries/agent_network_test_generator.hocon)

---

## Description

The Agent Network Test Generator operates as a six-step pipeline orchestrated by a
frontman agent with two specialized sub-agents and three coded tools:

1. **Read the target network** -- The frontman calls the
[`read_agent_network`](../coded_tools/agent_network_test_generator/read_agent_network.py)
coded tool with the user-provided HOCON file path. This tool:
   - Parses the target network's HOCON file using `AgentNetworkRestorer`.
   - Extracts a structured summary of every agent: name, instructions, description,
     parameters, sly\_data schemas, sub-tools, and class references.
   - Returns the full network summary to the frontman and stores `target_agent_name`
     in `sly_data` for the `persist_test_fixture` tool.

2. **Plan test scenarios** -- The frontman calls the `test_scenario_planner` sub-agent
with the network summary and a `test_level`. The planner analyzes the network's
capabilities and designs a list of test scenarios, each describing what to test, what
user messages to send, and what sly\_data to use.

3. **Build test fixtures (batched)** -- The frontman calls the `test_fixture_builder`
sub-agent ONCE with ALL scenarios from step 2 and the network summary. The builder
produces a complete test fixture dictionary for each scenario, conforming to the
neuro-san test case HOCON schema.

4. **Validate each fixture** -- For each fixture from step 3, the frontman calls the
[`validate_test_fixture`](../coded_tools/agent_network_test_generator/validate_test_fixture.py)
coded tool, which programmatically checks the fixture against the schema. If validation
fails, the frontman retries the `test_fixture_builder` with the error messages (up to
3 attempts per fixture).

5. **Persist each validated fixture** -- For each validated fixture, the frontman calls
the [`persist_test_fixture`](../coded_tools/agent_network_test_generator/persist_test_fixture.py)
coded tool, which:
   - Serializes the test fixture dictionary as human-readable JSON (valid HOCON).
   - Prepends a reference comment linking to the
     [test case HOCON schema documentation](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/test_case_hocon_reference.md).
   - Writes the file to `tests/fixtures/<agent_name>/<file_name>.hocon`.

6. **Return a summary** of all generated test cases with their file paths and what
each one tests.

---

## Test Level

The `test_level` parameter controls how many test scenarios are generated. It is
optional and defaults to `minimum` if not specified.

| Level     | Scenario Count | Description                                                                 |
|-----------|----------------|-----------------------------------------------------------------------------|
| `minimum` | 2--3           | One core happy-path scenario and one critical edge case.                    |
| `normal`  | 5--7           | Main happy paths, a few edge cases, and at least one error/boundary case.   |
| `max`     | 10--15         | Exhaustive: all capabilities, edge cases, errors, and multi-turn flows. |

The user specifies the level naturally in their prompt:

```text
Generate test cases for basic/coffee_finder_advanced with minimum coverage
Generate test cases for basic/music_nerd_pro with max coverage
Generate test cases for basic/hello_world
```

The last example defaults to `minimum`.

---

## Example Conversation

### Human

```text
Generate test cases for basic/music_nerd_pro with minimum coverage
```

### AI (agent\_network\_test\_generator)

```text
I've generated the following test fixtures for basic/music_nerd_pro:

1. tests/fixtures/basic/music_nerd_pro/yellow_submarine_with_followup.hocon
   - Tests a two-turn conversation: asks which band wrote "Yellow Submarine",
     then follows up with "Where are they from?"
   - Validates the "answer" key contains "Beatles" / "Liverpool" using keywords
   - Validates "running_cost" using exact value checks (3.0, then 6.0)

2. tests/fixtures/basic/music_nerd_pro/hidden_gem_recommendation.hocon
   - Tests a single-turn request for a hidden gem recommendation
   - Validates the response mentions a specific song or album using gist
```

---

## Architecture Overview

### Frontman Agent: `agent_network_test_generator`

The frontman agent is the sole entry point. It receives the user's request (which
network to generate tests for and optionally the test level), orchestrates the
read-plan-build-validate-persist pipeline, and returns a summary of generated fixtures.

**Available Tools:**

- `read_agent_network` -- Coded tool: reads and summarizes a target agent network HOCON
- `test_scenario_planner` -- Sub-agent: designs test scenarios from the network summary
- `test_fixture_builder` -- Sub-agent: builds complete test fixture dictionaries from
  scenario descriptions
- `validate_test_fixture` -- Coded tool: programmatically validates a test fixture against
  the schema
- `persist_test_fixture` -- Coded tool: writes a generated test fixture to disk

### Sub-Agents

#### `test_scenario_planner`

Analyzes the network summary and designs test scenarios. Each scenario includes a
`scenario_name`, `description`, and `interactions` (sequence of user messages, sly\_data,
and expected behavior). The planner respects the `test_level` parameter to control how
many scenarios to generate.

Key planning rules:
- Uses the network's `sample_queries` as inspiration for realistic inputs
- Plans deterministic sly\_data values (e.g. time overrides) using exact key names and
  formats from the `sly_data_schema` and `sly_data_output_schema` in the network summary
- Accounts for multi-turn conversation state (e.g. information provided in message 1
  is not re-asked in message 2)
- Plans separate interactions for each question-and-answer step when an agent collects
  information before completing an action
- Does not assume a specific order of follow-up questions from the agent
- Never pre-sets runtime-managed sly\_data keys (`running_cost`, `TopicMemory`,
  `username`)
- If the network includes an agent named "Accountant", plans for `running_cost`
  assertions (3.0 per interaction turn)

#### `test_fixture_builder`

Produces complete test fixture dictionaries conforming to the neuro-san test case HOCON
schema. Accepts one or more scenarios in a single batched call to reduce LLM round-trips.

Key building rules:
- Only uses valid stock tests: `keywords`, `not_keywords`, `value`, `not_value`, `gist`,
  `not_gist`, `less`, `not_less`, `greater`, `not_greater`
- Keywords must be short distinctive phrases (max 5 words), case-sensitive
- `gist` criteria are short, specific, and focused on one essential fact each
- Does not assume a specific order of follow-up questions from the agent
- Preserves float types in `value` tests (e.g. `3.0` not `3`)
- Never pre-sets runtime-managed sly\_data keys
- If the network includes an agent named "Accountant", includes `running_cost`
  assertions starting at 3.0 and incrementing by 3.0 per turn

### Coded Tools

#### `read_agent_network`

[read\_agent\_network.py](../coded_tools/agent_network_test_generator/read_agent_network.py)

- Parses the target network's HOCON file using `AgentNetworkRestorer`
- Extracts agent metadata, instructions, parameters, and sly\_data schemas
- Returns the full network summary to the frontman and stores `target_agent_name` in
  `sly_data` for the `persist_test_fixture` tool

#### `validate_test_fixture`

[validate\_test\_fixture.py](../coded_tools/agent_network_test_generator/validate_test_fixture.py)

- Programmatically validates a test fixture dictionary against the schema
- Checks top-level keys (`agent`, `success_ratio`, `connections`, `interactions`)
- Checks per-interaction keys (`text`, `timeout_in_seconds`, `response`, optional
  `sly_data`)
- Validates response structure (`response.text` or `response.structure` with valid
  stock tests only)
- Rejects forbidden sly\_data keys (`running_cost`, `TopicMemory`, `username`)
- Rejects keywords longer than 5 words
- Rejects integer values in `value` stock tests (must be float)
- Returns `{"valid": true}` or `{"valid": false, "errors": [...]}`

#### `persist_test_fixture`

[persist\_test\_fixture.py](../coded_tools/agent_network_test_generator/persist_test_fixture.py)

- Receives a test fixture dictionary and a file name
- Serializes as indented JSON (valid HOCON) with a reference comment
- Sanitizes the file name and ensures `.hocon` extension
- Creates the output directory structure under `tests/fixtures/`

---

## Running a Generated Test Fixture

Generated fixtures are not automatically registered in the test suite. To run one:

### Option A: Quick one-off run

<!-- pyml disable blanks-around-fences -->

```bash
source venv/bin/activate
export PYTHONPATH=$(pwd)
export AGENT_MANIFEST_FILE=$(pwd)/registries/manifest.hocon
export AGENT_TOOL_PATH=$(pwd)/coded_tools
python -c "
from unittest import TestCase
from neuro_san.test.unittest.dynamic_hocon_unit_tests import DynamicHoconUnitTests
import os

tc = TestCase()
tc.maxDiff = None
source_file = os.path.join(os.getcwd(), 'tests/integration/test_integration_test_hocons.py')
dh = DynamicHoconUnitTests(source_file, path_to_basis='../fixtures')

test_hocon = 'basic/music_nerd_pro/yellow_submarine_with_followup.hocon'
test_name = DynamicHoconUnitTests.test_name_from_hocon_file(test_hocon)
dh.one_test_hocon(tc, test_name, test_hocon)
print('TEST PASSED')
"
```

<!-- pyml enable blanks-around-fences -->

### Option B: Register in the integration test suite

Add the fixture path to the `@parameterized.expand` list in
`tests/integration/test_integration_test_hocons.py`, then run:

```bash
python -m pytest tests/integration/test_integration_test_hocons.py -v -k "yellow_submarine"
```

---

## Tips for Better Test Fixtures

- **Review `gist` criteria** -- Keep them concise. Overly specific criteria can cause
  false negatives with the LLM-based gist assessor.
- **Use `keywords` or `value` when possible** -- These are deterministic and more
  reliable than `gist`.
- **Keywords must be short** -- Each keyword entry should be a short distinctive phrase
  (max 5 words). Use `gist` for full-sentence meaning checks.
- **Keywords are case-sensitive** -- Use exact casing as it appears in the agent's
  response (e.g. `"Order ID"` not `"order id"`).
- **Be careful with `not_keywords`** -- Agents often mention unavailable items by name
  when explaining why they are not options. Only use `not_keywords` for words that should
  truly never appear in any context.
- **Check `sly_data` keys** -- Ensure they match exactly what the coded tools read
  (e.g. `"time"` not `"fixed_time"`).
- **Check `sly_data` value formats** -- Use the same format the agents understand
  (e.g. `"8 am"` not `"2026-03-17T08:00:00"`).
- **Never pre-set runtime keys in `sly_data`** -- `running_cost`, `TopicMemory`, and
  `username` are managed internally by coded tools and must never appear in sly\_data.
  They may still appear in `response.structure` assertions.
- **Verify numeric values** -- If a coded tool produces deterministic values (e.g.
  `Accountant` adds `3.0` per call), use `"value"` with the exact expected float.
- **Don't assume follow-up question order** -- Agents may ask follow-up questions in
  any order. Provide all required info in a single user message or use order-agnostic
  gist assertions.
- **Delete memory files before multi-turn tests** -- Networks that persist state
  (e.g. `TopicMemory.json`) can cause test interference. Delete any memory files
  before running multi-turn test fixtures.

---

## Debugging Hints

- If the LLM generates incorrect response structures, check the `test_fixture_builder`
  instructions in `agent_network_test_generator.hocon` for guidance on the correct format.
- If a fixture fails validation, the frontman will automatically retry with error messages.
  Check the `validate_test_fixture` error output for specific schema violations.
- If the agent times out or hits max iterations, increase `max_execution_seconds` or
  `max_iterations` in `agent_network_test_generator.hocon`.

---
