# FXMacroData

The **FXMacroData** agent network is a single-agent network that answers questions about official macroeconomic
data for FX analysis: the latest inflation, payrolls or policy-rate reading, the history of an indicator, when the
next release is due, recent central-bank press releases and which FX trading sessions are open. It connects to the
hosted FXMacroData MCP server, which serves data published by central banks and statistical agencies, so answers
come with the official source and the release timestamp instead of from the model's memory.

---

## File

[fxmacrodata.hocon](../../../registries/tools/fxmacrodata.hocon)

---

## Prerequisites

None for US data. The network is enabled by default and the MCP server answers without an API key.

Without a key, the server returns:

- USD announcements for the most recent 90 days, with each release readable 15 minutes after publication
- the USD release calendar
- Federal Reserve press releases
- FX market session times

Fair use without a key is 100 requests per day.

### Optional: API Key

An API key unlocks the other 21 currencies (AUD, BRL, CAD, CHF, CNH, CNY, DKK, EUR, GBP, HUF, ILS, JPY, KRW, MYR,
NGN, NOK, NZD, PEN, SEK, THB, TWD), full history and real-time releases through the same tools.

1. Get a key at [https://fxmacrodata.com/subscribe](https://fxmacrodata.com/subscribe)
2. Set it using the `FXMACRODATA_API_KEY` environment variable
3. Uncomment the `http_headers` block in the FXMacroData entry of
   [mcp\_info.hocon](../../../neuro_san_studio/mcp/mcp_info.hocon), which sends it as an `Authorization: Bearer`
   header. Keyless and keyed usage share the same URL. Leave the block commented out until you have a real key:
   the server rejects an invalid key rather than falling back to keyless access.

The API reference is at [https://fxmacrodata.com/documentation](https://fxmacrodata.com/documentation).

---

## Architecture Overview

### Frontman Agent: fx_macro_analyst

- The network's single LLM agent. It picks the FXMacroData tool that matches the question and answers from the
  returned data, citing the official source.
- Its instructions cover the one detail that most often trips up date handling: a row's `date` is the reference
  period the value describes (a CPI row dated 2026-08-31 is August inflation), while `announcement_datetime` is when
  the value was or will be published.

### Tool: FXMacroData MCP server

The agent connects to `https://mcp.fxmacrodata.com` over streamable HTTP. The `tools` list in
[mcp\_info.hocon](../../../neuro_san_studio/mcp/mcp_info.hocon) limits it to five tools that answer without a key:

- **`latest_announcements`**: the latest value of every indicator in one currency, including the indicator slugs the
  other tools expect.
- **`indicator_query`**: the history of one indicator, such as `inflation`, `non_farm_payrolls` or `policy_rate`.
- **`release_calendar`**: scheduled release times for a currency's indicators.
- **`press_releases`**: recent central-bank press releases.
- **`market_sessions`**: which FX trading sessions (Sydney, Tokyo, London, New York) are open, and when the next
  one opens or closes.

The server exposes more tools, such as `forex`, `cot_data` and `commodities`, which need an API key. With a key, add
their names to the `tools` list in that entry, or remove the `tools` key entirely to load every tool the server
exposes.

---

## Example Conversation

### Human

```text
What was the latest US CPI inflation reading, and when was it released?
```

### AI (fx_macro_analyst)

```text
US CPI inflation was 3.4% year over year for August 2026, unchanged from July. The Bureau of Labor Statistics
published it on September 11, 2026 at 08:30 New York time (12:30 UTC).
```

---

## Debugging Hints

- **"subscription_required" in a tool result**: the question asked for a currency or tool outside the keyless
  scope. The agent should say so and answer the closest US question instead. Set `FXMACRODATA_API_KEY` and
  uncomment the header to unlock it.
- **The newest release is missing**: without a key, a release becomes readable 15 minutes after publication, and
  the tool result says when a withheld release becomes available.
- **HTTP 401 `invalid_api_key`**: the `http_headers` block is uncommented but `FXMACRODATA_API_KEY` is not a valid
  key. Fix the key or comment the block out again to return to keyless access.
- **A date looks a month or a quarter off**: compare the row's `date` (reference period) with its
  `announcement_datetime` (publication time).
