# Music Nerd LLM Fallbacks

An exact copy of [docs/examples/music_nerd.md](music_nerd.md) that uses fallbacks
in its LLM config to try a different LLM if the first one fails.

## File

[music_nerd_llm_fallbacks.hocon](../../../registries/basic/music_nerd_llm_fallbacks.hocon)

## Description

The fallback strategy is defined in the `llm_config` section
using a `fallbacks` list instead of single LLM config.
The list is ordered, and the first LLM that succeeds will be used.

```hocon
    "llm_config": {
        "fallbacks": [
            {
                # Try OpenAI first
                "model_name": "gpt-4o",
            },
            {
                # Fall back to Anthropic Claude if OpenAI is unavailable.
                "model_name": "claude-3-7-sonnet",
            }
        ]
    },
```

In this example, the agent network will use OpenAI's `gpt-4o` model first,
and if that fails (for example, due to rate limits or service outages),
it will automatically fall back to Anthropic's `claude-3-7-sonnet` model.
