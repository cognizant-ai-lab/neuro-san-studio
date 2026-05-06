# Book Club Multiple LLM Config

A book recommendation network that demonstrates how to assign
different Anthropic models to individual agents using per-agent `llm_config`.

It's good for testing:

* how to use per-agent `llm_config` to assign different models within one network
* how to use different models for different task complexities

## File

[book_club_multiple_llm_config.hocon](../../../registries/basic/book_club_multiple_llm_config.hocon)

## Description

Each agent has its own `llm_config` specifying an Anthropic model:

| Agent | Model | Role |
|-------|-------|------|
| **BookClubHost** | `claude-opus` | Frontman — routes requests to genre experts |
| **FictionExpert** | `claude-sonnet` | Recommends fiction and literary novels |
| **NonFictionExpert** | `claude-sonnet` | Recommends non-fiction books |
| **MysteryExpert** | `claude-sonnet` | Recommends mystery and thriller books |
| **SciFiExpert** | `claude-sonnet` | Recommends science fiction books |
| **QuickSummary** | `claude-haiku` | Provides brief one-line book summaries |

The per-agent `llm_config` is set like this:

```hocon
"llm_config": {
    "class": "anthropic",
    "model_name": "claude-opus"
}
```

## Prerequisites

* An Anthropic API key set as the `ANTHROPIC_API_KEY` environment variable.

## Example conversation

```text
Human:
Suggest me a good book to read.

AI:
What kind of book are you in the mood for? I have experts in fiction,
non-fiction, mystery/thrillers, and science fiction.
```

Following up:

```text
Human:
I want something thrilling and suspenseful.

AI:
I'd recommend "Gone Girl" by Gillian Flynn — a masterfully crafted
psychological thriller with unreliable narrators that keeps you
guessing until the very last page.
```

Following up again:

```text
Human:
What's a good science fiction book for beginners?

AI:
I'd recommend "The Martian" by Andy Weir — a gripping, accessible
sci-fi novel about an astronaut stranded on Mars, full of humor
and real science that draws you in from page one.
```
