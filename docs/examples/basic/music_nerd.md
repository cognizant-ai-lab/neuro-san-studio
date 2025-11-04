# Music Nerd

This is a very simple agent network with a single agent, used as a "Hello world!" example.
It allows to test for:

* deterministic answers
* follow-up questions

## File

[music_nerd.hocon](../../../registries/basic/music_nerd.hocon)

## Description

Music nerd is an agent network that can answer questions about music since the 60s.

## Example conversation

```text
Human: Which band wrote Yellow Submarine?
AI: ... The Beatles ...
```

Expectation: the answer should contain "The Beatles".

Follow-up question, to check the conversation history is carried over:

```text
Human: Where are they from?
AI: ... Liverpool ...
```

The answer should contain "Liverpool".
