# consultant

Generates tests and iteratively improves an agent network without changing its intended behavior. Consultant can
improve an existing HOCON network or design a network for a new use case before testing it.

See the [Agent Network Consultant guide](../examples/agent_network_consultant.md) for setup, workflow, nsflow
integration, Git snapshots, and output locations.

## Usage

### Existing network

The HOCON path is relative to `registries/`. When no direction is supplied, Consultant uses the network and its
fixtures as the behavioral baseline.

```bash
ns consultant \
  --hocon-file industry/intranet_agents.hocon
```

Use the optional direction when the run has an additional improvement goal:

```bash
ns consultant \
  --hocon-file industry/intranet_agents.hocon \
  --direction "Reduce token usage without changing existing behavior."
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

<!-- pyml disable line-length -->

| Option | Description |
|---|---|
| `--use-case` | Describe a new network to create through Agent Network Designer before testing. |
| `--hocon-file` | Select the existing network using a path relative to `registries/`. |
| `--direction` | Optionally describe behavior to preserve or an additional improvement goal. |
| `--test-level` | Select `minimum`, `normal`, or `max` generated-test coverage. Defaults to `normal`. |
| `--test-guidance` | Provide additional free-text guidance for test generation. |
| `--force-generate` | Generate tests even when fixtures exist. Existing fixture files are not deleted. |
| `--ungrounded` | Choose `stop` or `continue` for criteria that no available tool can satisfy. Defaults to `stop`. |
| `--only-fixtures` | Run a space-separated list of exact fixture filenames, including `.hocon`. |
| `--max-iterations` | Limit test-and-repair iterations. Defaults to `20`; zero runs tests once without repairs. |
| `--success-ratio` | Set the verification ratio in `N/M` form. Defaults to `3/3`. |
| `--git-versions` | Push meaningful HOCON checkpoints to a dedicated branch on the configured upstream. |

<!-- pyml enable line-length -->

Run `ns consultant --help` for the command's generated help.

`--git-versions` requires `NETWORK_CONSULTANT_GIT_VERSIONS_REMOTE` to contain an existing Git remote name, such as
`upstream`, or a repository URL. Consultant pushes directly to that destination and does not add or rewrite Git
remotes in the local repository. The command reports an error before starting when the variable is unset.
