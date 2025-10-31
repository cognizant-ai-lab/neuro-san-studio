# Music Nerd Pro

This simple agent network consists in a frontman agent and a "tool" agent,
i.e. an agent that calls Python code.
This is a good way to get familiar with coded tools.
It allows to test for:

* deterministic answers
* follow-up questions
* calling a coded tool (a Python function).

## File

[music_nerd_pro.hocon](../../../registries/basic/music_nerd_pro.hocon)

## Description

Music nerd Pro is an agent network that can answer questions about music since the 60s.
It also calls a tool that increments a counter of the number of questions answered.
The agent knows it has to call the tool to keep track of the "running cost", but it
has no idea how the cost is calculated. It has to pass the previous cost to the tool
to get the new cost.

## Example conversation

```text
Human: Which band wrote Yellow Submarine?
AI: ... The Beatles ...
    ... running cost ... $1.00 ...
```

Expectation: the answer should contain:

* "The Beatles".
* a running cost of $1.00.

Follow-up question, to check the conversation history is carried over:

```text
Human: Where are they from?
AI: ... Liverpool ...
    ... running cost ... $2.00 ...
```

The answer should contain "Liverpool".
And a running cost of $2.00.
Debug logs should show that the agent has passed the previous cost to the tool.
