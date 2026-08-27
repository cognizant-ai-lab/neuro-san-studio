---
name: agent-network-periodic-triggers
description: Make a neuro-san-studio network fire itself on a cron-style schedule instead of only responding to
  client requests. Use when asked to run a network periodically, on a timer, or on a cron schedule.
---

# Periodic (cron-triggered) networks

A manifest entry can carry a `"periodic"` key so the server invokes that network on a schedule, in addition to
normal client-triggered requests. Verified against the installed `neuro-san` package source
(`periodic_manifest_dict_config_filter.py`, `periodic_event_initiator.py`).

```hocon
// registries/manifest.hocon
{
    "my_network.hocon": {
        "serve": true,
        "periodic": "0 9 * * *"    // shorthand: just a cron_schedule string, run once daily at 9am
    }
}
```

The shorthand string form is expanded into the full dict form under the hood:

```hocon
{
    "my_network.hocon": {
        "serve": true,
        "periodic": {
            "interactions": [
                {
                    "enable": true,
                    "cron_schedule": "0 9 * * *",
                    "second_at_beginning": false,
                    "text": "Do your thing",
                    "sly_data": {},
                    "metadata": { "user_id": "system" }
                }
            ]
        }
    }
}
```

- `cron_schedule` — 5 space-delimited fields (minute, hour, day-of-month, month, day-of-week) by default; set
  `second_at_beginning: true` to prepend a 6th seconds field. Validated with strict `croniter` rules at load time —
  an invalid schedule disables that interaction (logged as a warning) rather than failing the whole manifest.
- `text` — the message sent to the network's Front Man as if a client had typed it, each time the schedule fires.
- `sly_data` / `metadata` — passed through with the triggered request, same channel described in the
  `agent-network-tool-integration` skill (`sly_data`) — `metadata.user_id` defaults to `"system"`.
- `interactions` is a list — one network can have multiple independent schedules, each with its own `text`.
- `"periodic": false` (or omitting the key) disables it — the default.

House rule still applies: give the network `max_steps`/`max_execution_seconds` (see `agent-network-hocon-reference`
skill) since a misbehaving periodic network will otherwise retrigger indefinitely.

Full reference: [manifest_hocon_reference.md](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/manifest_hocon_reference.md).
