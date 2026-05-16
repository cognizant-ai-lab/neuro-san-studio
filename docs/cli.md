# CLI reference

The `neuro-san-studio` console script dispatches to a small set of subcommands.
Run `neuro-san-studio --help` for the full list and shared options.

| Subcommand                          | Description |
|-------------------------------------|---|
| `run`                               | Start the Neuro SAN server and a client (default when no subcommand is given). |
| `init`                              | Scaffold a starter project in the current directory. |
| [`check-config`](#check-config)     | Validate every LLM configuration in a HOCON file. |
| [`check-llm-keys`](#check-llm-keys) | Validate LLM API keys and other critical environment variables. |

---

## check-config

Validates every LLM configuration in a HOCON file by creating each LLM instance
and invoking it with a trivial test prompt. It is useful for verifying that:

- Provider API keys are set and valid
- Model names are spelled correctly and reachable
- Per-agent `llm_config` overrides resolve to a working model

### Usage

```bash
# Validate the default config/llm_config.hocon
neuro-san-studio check-config

# Validate a specific HOCON file
neuro-san-studio check-config registries/music_nerd.hocon
neuro-san-studio check-config path/to/llm_config.hocon
```

The command exits with code `0` when every configuration succeeds and `1` when
any configuration fails.

### Supported HOCON formats

Both formats produced by `neuro-san-studio` are accepted:

| Format | Detected by | What gets tested |
|---|---|---|
| Agent network | Has a `tools` list | Each agent's merged `llm_config` (top-level defaults + per-agent overrides) |
| Standalone studio `llm_config` | No `tools` list | The single top-level `llm_config` |

`fallbacks` lists are expanded so every model in the list is tested
individually. Duplicate configurations are deduplicated so each unique model is
called only once.

### Output

The command prints, in order:

1. The parsed HOCON file and detected format
2. Each `(label, llm_config)` pair it discovered (with secrets redacted)
3. A per-model creation + invocation result
4. A `RESULTS SUMMARY` listing working and failing configurations

Sensitive keys (anything containing `key`, `token`, `secret`, `credential`, or
`password` at a word boundary) are redacted in the printed configs.

## check-llm-keys

`neuro-san-studio check-llm-keys` runs three progressively deeper tiers of validation on LLM API keys
and other critical environment variables: placeholder detection, format checks, and (optionally) a
live API call against each provider. Use it as a quick pre-flight check on a freshly configured
`.env` file or in CI to catch common misconfigurations before they reach the server.

### Usage

```bash
# Tier 3 — placeholder + format checks + live API calls (default)
neuro-san-studio check-llm-keys

# Tier 1 — placeholder detection only
neuro-san-studio check-llm-keys --tier 1

# Tier 2 — placeholder + format checks (no network calls)
neuro-san-studio check-llm-keys --tier 2
```

### Tiers

| Tier | Name | What it checks |
|---|---|---|
| 1 | Placeholder detection | Variable is set and not a placeholder (`YOUR_`, `REPLACE`, `TODO`, `<`, `>`, etc.). |
| 2 | Format validation | Value matches the expected format for the key type (prefix, length, character set). |
| 3 | Live validation | Makes a lightweight API call to verify the key with the provider (OpenAI, Anthropic, Google). |

Each tier is cumulative — tier 2 includes tier 1, and tier 3 includes tiers 1 and 2. Tiers 1 and 2
run entirely offline; tier 3 requires network access to reach the provider APIs.

The keys validated are: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`,
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`.

### Exit codes

The command prints a grouped results table (VALID / WARNING / ERROR) and exits with:

- `0` when only warnings are present. Missing keys (`NOT_SET`) and placeholder values
    (`PLACEHOLDER`) are treated as warnings — they do not fail the command.
- `1` when any format check fails (tier 2) or any live API call fails (tier 3) with an
    authentication error, rate limit, or out-of-credits response.

### Optional dependencies for tier 3

Tier 3 makes real API calls and therefore requires the matching provider package to be installed:

- `openai` — for `OPENAI_API_KEY`
- `anthropic` — for `ANTHROPIC_API_KEY`
- `google-genai` — for `GOOGLE_API_KEY`

If a provider package is not installed, that key's live check is skipped (with an informational
note in the output) rather than failing the command. Install the missing package only if you want
the corresponding key to be live-validated.
