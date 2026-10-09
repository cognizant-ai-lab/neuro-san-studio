# consultant

Generates tests and repairs failing agent-network behavior without changing the intended behavior. Consultant can
repair an existing HOCON network or design a network for a new use case before testing it.

See the [Agent Network Consultant guide](../examples/agent_network_consultant.md) for setup, workflow, nsflow
integration, and output locations.

## Usage

### Existing network

The HOCON path is relative to `registries/`. When no direction is supplied, Consultant uses the network and its
fixtures as the behavioral baseline. `--hocon-file` and `--use-case` are mutually exclusive.

```bash
ns consultant \
  --hocon-file industry/intranet_agents.hocon
```

Use the optional direction to clarify intended behavior or state constraints that every repair must preserve:

```bash
ns consultant \
  --hocon-file industry/intranet_agents.hocon \
  --direction "Preserve the current routing and response tone while fixing failures."
```

### Run selected fixtures

Pass a space-separated list of exact fixture filenames, including `.hocon`, to run a subset:

```bash
ns consultant \
  --hocon-file industry/intranet_agents.hocon \
  --direction "Preserve existing behavior while fixing failing tests." \
  --only-fixtures employee_policy.hocon employee_benefits.hocon
```

## Options

| Option | Description |
|---|---|
| `--use-case` | Describe a new network for Designer to create. Mutually exclusive with `--hocon-file`. |
| `--hocon-file` | Select an existing network relative to `registries/`. Cannot be combined with `--use-case`. |
| `--direction` | Optionally clarify intended behavior or describe constraints that repairs must preserve. |
| `--test-level` | Select `minimum`, `normal`, or `max` generated-test coverage. Defaults to `normal`. |
| `--test-guidance` | Provide additional free-text guidance for test generation. |
| `--force-generate` | Generate tests even when fixtures exist. Existing fixture files are not deleted. |
| `--ungrounded` | Choose `stop` or `continue` for criteria that no available tool can satisfy. Defaults to `stop`. |
| `--only-fixtures` | Run a space-separated list of exact fixture filenames, including `.hocon`. |
| `--max-iterations` | Limit repair attempts. Defaults to `20`; zero runs tests once without repairs. |
| `--success-ratio` | Set the `N/M` verification ratio for fixes Consultant considers stable. Defaults to `3/3`. |

Run `ns consultant --help` for the command's generated help.
