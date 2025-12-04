# Agentforce

This agent network delegates to a Salesforce Agentforce agent to interact with a CRM system.
It uses a CodedTool to call the Agentforce APIs.
See the [Agentforce developer guide](https://developer.salesforce.com/docs/einstein/genai/guide/agent-api-get-started.html)
for more details.

## File

[agentforce.hocon](../../../registries/tools/agentforce.hocon)

## Description

Agentforce is an agent network that communicates with a Salesforce Agentforce agent to answer
questions about a CRM system. Calling the API will initiate a session the first time it's called.
The session will be reused for subsequent calls to the API thanks to the `session_id` and
`access_token` parameters in the `sly_data`. The agent's LLM does not see the sly_data and doesn't have
to worry about the session management.

## Example conversation

```text
Human: Can you give me a list of Jane Doe's most recent cases?
AI: Sure, I can help with that. Could you please provide Jane Doe's email address to look up her cases?
```

By default, if not configured, the agentforce tool will return mock responses.

A follow-up question, to check the conversation history is carried over and the session is reused, can be:

```text
Human: jdoe@example.com
AI: It looks like there are no recent cases associated with Jane Doe's email address. Is there anything else I can assist
you with?
```

## Configuration

The following environment variables should be set in order to connect to the Agentforce API:

- **AGENTFORCE_MY_DOMAIN_URL**: The domain URL of your Salesforce instance, e.g., [https://mydomain.my.salesforce.com](https://mydomain.my.salesforce.com).
- **AGENTFORCE_AGENT_ID**: The ID of the agent that you want to interact with
- **AGENTFORCE_CLIENT_ID**: The client ID of the connected app that you created in Salesforce.
- **AGENTFORCE_CLIENT_SECRET**: The client secret of the connected app that you created in Salesforce.

See the [Agentforce developer guide](https://developer.salesforce.com/docs/einstein/genai/guide/agent-api-get-started.html)
for more information about how to create a connected app and add it to an agent.

You can use the `.env` file to manage these environment variables.
The `.env` file should be in the root of your project directory.
Warning: Do not commit this `.env` file to your version control system (e.g., Git) as it contains sensitive information.

## Debugging hints

You can use the [tests/coded_tools/tools/agentforce/test_agentforce_adapter.py](../../../tests/coded_tools/tools/agentforce/test_agentforce_adapter.py)
unit tests to check your Agentforce connectivity.
