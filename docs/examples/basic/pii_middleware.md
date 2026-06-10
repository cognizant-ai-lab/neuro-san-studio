# PII Middleware

The **PII Middleware** agent network is a small network designed to demonstrate the most basic example of
how langchain's AgentMiddleware can be used to detect Personally Identifiable Information (PII).

---

## File

[pii_middleware.hocon](../../../registries/basic/pii_middleware.hocon)

---

## Description

The PII Middleware agent network provides a very simple example as to how one agent
can employ AgentMiddleware to detect PII in a chat stram.

The idea is you give it a 7-digit phone number and a message to leave and it will
leave a voicemail at the given phone number... Or will it?!?
It is actually a prankster agent and will not do anything except regurgitate the input,
but this input will go through PII redaction.

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
Send a message to Jenny at 867-5309.
Tell her I got her number and I need to make her mine.
```

This is an example input taken as a riff off of an old 80's song.
https://www.youtube.com/watch?v=6WTdTwcmxyo

What we really want is to give it the phone number but then in its
effort to respond back, that will be redacted.

### AI

```text
I can’t help write or deliver a threatening/harassing message like that.

If you want, I can leave Jenny a respectful note at **[REDACTED_PHONE_NUMBER]** instead—tell me what you’d like it to say (e.g., “Hi Jenny, this is ____. I got your number from ____. If you’re open to it, I’d love to chat—no worries if not.”).
```

This is only one result from a call to the pii_middleware agent network.
It's only so predictable. Your mileage will vary here.

---

## Architecture Overview

### Frontman Agent: prankster

- Main entry point for user inquiry.

- Interprets natural language queries and filters responses through PII detection of phone numbers

There are no other agents to call in this network. The focus is on as simple a middleware example as we can get..

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

- [Agent Network Hocon specification](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/agent_hocon_reference.md#middleware)
  See how to define multiple middleware instances for your own agent networks.
  The sly_data can be sent to middleware too.
  Note that neuro-san only allows class-based AgentMiddleware.

- [AgentMiddleware Overview](https://docs.langchain.com/oss/python/langchain/middleware/overview)
  Good overview of AgentMiddleware.

- [Prebuilt Middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)
  Note that not all pre-built middleware listed may be suitable for use in an asynchronous server environment,
  but it gives you an idea of the many uses that middleware can have.
