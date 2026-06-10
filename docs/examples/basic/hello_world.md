# Hello World

The **Hello World** agent network is a small network designed to demonstrate the most basic example of one agent calling another by hocon configuration only.

---

## File

[hello_world.hocon](../../../registries/basic/hello_world.hocon)

---

## Description

The Hello World agent network provides a very simple example as to how one agent
can call another one. The idea is you give it some prescribed text and it has
the ability to return the phrase "Hello, world!".  But you are dealing with LLMs,
it might not return what you expect! In the agent world, you need to be prepared
for statistical outcomes.

---

## Prerequisites

This agent network requires the following setup:

### Python Dependencies

Nothing special.

### Environment Variables

Nothing special

---

## Example Conversation

### Human

```text
From earth, I approach a new planet and wish to send a short 2-word greeting to the new orb.
```

This is an example of a phrase that is likely to goad the agent network into returning
what we want: "Hello, world!".  If you can do better, let us know.

### AI

```text
Hello, world!
```

This is the ideal result from a call to the hello_world agent network.
It's only so predictable. Your mileage will vary here. Get used to that with LLMS involved ;).

---

## Architecture Overview

### Frontman Agent: announcer

- Main entry point for user inquiry.

- Interprets natural language queries and delegates tasks to the synonymizer tool.

This guy sets up the framing of the problem for the synonymizer to return
"hello world" given the particular input above.

It calls one and only one other agent as a tool.

### Tool: synonymizer

This agent is tries to create synonyms for each word of a given phrase
The constraints of the instructions are such that it tries to pick 5 letter words,
thus steering it towards a response like "hello world".


#### Tool Arguments and Parameters

- `name`: A brief description of the what the input should pertain to.

- `input_string`: Words or phrases to use as nput.

---

## Debugging Hints

When developing or debugging with OpenAI models, keep the following in mind:

- **API Key Validation**: Ensure your `OPENAI_API_KEY` is valid and has access to preview tools.

- **Rate Limits**: Be aware of API rate limits that may affect LLM calling frequency.

### Common Issues

- **Import Errors**: Ensure langchain-openai is installed

- **Authentication Failures**: Verify API key is set and valid

- **Model Errors**: Confirm the specified GPT model is accessible

---

## Resources

- [Agent Network Hocon specification](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/agent_hocon_reference.md)

