# check-llm-keys

`neuro-san-studio check-llm-keys` runs three progressively deeper tiers of validation on LLM API keys
and other critical environment variables: placeholder detection, format checks, and (optionally) a
live API call against each provider. Use it as a quick pre-flight check on a freshly configured
`.env` file or in CI to catch common misconfigurations before they reach the server.

## Usage

```bash
# Tier 3 — placeholder + format checks + live API calls (default)
neuro-san-studio check-llm-keys

# Tier 1 — placeholder detection only
neuro-san-studio check-llm-keys --tier 1

# Tier 2 — placeholder + format checks (no network calls)
neuro-san-studio check-llm-keys --tier 2
```

## Tiers

| Tier | Name | What it checks |
|---|---|---|
| 1 | Placeholder detection | Variable is set and not a placeholder (`YOUR_`, `REPLACE`, `TODO`, `<`, `>`, etc.). |
| 2 | Format validation | Value matches the expected format for the key type (prefix, length, character set). |
| 3 | Live validation | Makes a lightweight API call to verify the key with the provider (OpenAI, Anthropic, Google). |

Each tier is cumulative — tier 2 includes tier 1, and tier 3 includes tiers 1 and 2. Tiers 1 and 2
run entirely offline; tier 3 requires network access to reach the provider APIs.

The keys validated are: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`,
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`.

## Exit codes

The command prints a grouped results table (VALID / WARNING / ERROR) and exits with:

- `0` when only warnings are present. Missing keys (`NOT_SET`) and placeholder values
    (`PLACEHOLDER`) are treated as warnings — they do not fail the command.
- `1` when any format check fails (tier 2) or any live API call fails (tier 3) with an
    authentication error, rate limit, or out-of-credits response.

## Optional dependencies for tier 3

Tier 3 makes real API calls and therefore requires the matching provider package to be installed:

- `openai` — for `OPENAI_API_KEY`
- `anthropic` — for `ANTHROPIC_API_KEY`
- `google-genai` — for `GOOGLE_API_KEY`

If a provider package is not installed, that key's live check is skipped (with an informational
note in the output) rather than failing the command. Install the missing package only if you want
the corresponding key to be live-validated.
