# Neuro-SAN Integration Quick Start

This tutorial will teach you how to use a neuro-san agent network as a Python library using the "direct" session feature.

## Who is this for ?

This tutorial maybe useful, if you:

- Have already created an agent network in neuro-san-studio and want to run it programmatically
- Want to integrate neuro-san agents into your Python applications
- Are starting fresh and want to learn step-by-step how to create and invoke agents

## What you'll learn

By the end of this tutorial, you will know how to:

1. Create and configure a basic agent
2. Register your agent with neuro-san
3. Invoke agents directly from Python code
4. Create reusable functions for agent interactions
5. Use HTTP requests to communicate with a neuro-san server

## Prerequisites

Before starting, ensure you have:
- Setup your neuro-san environment -> [README](../README.md)
- API keys for your chosen LLM provider (such as OpenAI for GPT-4o)
- An empty folder to work in

## Setup

First, import the necessary libraries:

```py
import os
from pprint import pprint
import warnings

# Suppress coroutine warnings for cleaner output
warnings.filterwarnings('ignore', category=RuntimeWarning)
```

## Step 1: Create a Basic Agent

An agent in neuro-san is defined using a HOCON configuration file. Let's create a simple
"hello_world" agent that greets users.

**Note:** This example uses the `gpt-4o` model. You can substitute it with any available
model (e.g., `gpt-3.5-turbo`, `claude-3-sonnet`, etc.). Make sure your API keys are
set in your environment variables.

> **Tip:** If you already have a working agent and manifest, you can skip to Step 3.

```py
# Define the agent configuration in HOCON format
basic_agent_hocon = '''
{
    "llm_config": {
        "model_name": "gpt-4o",
    },

    "tools": [
        {
            "name": "HelloWorldAgent",
            "function" : {
                # The description acts as an initial prompt. 
                "description": """I greet people"""
            },
             "instructions": """You are an agent that greets people. When you 
            receive a request, respond with a friendly greeting message.""",
        },
    ]
}
'''

agent_file_name = "hello_world.hocon"

# Create the registries directory if it doesn't exist
os.makedirs("./registries", exist_ok=True)

# Write the agent configuration to a file
with open(f"./registries/{agent_file_name}", "w") as f:
    f.write(basic_agent_hocon)

print(f"✓ Created agent configuration: ./registries/{agent_file_name}")
```

**What's happening here?**
- We define an agent configuration that specifies which LLM model to use
- The agent has a description and instructions that guide its behavior
- We save this configuration to `./registries/hello_world.hocon`

## Step 2: Register the Agent

neuro-san uses a `manifest.hocon` file to discover available agents. Let's create this manifest and register our agent.

```py
# Define the manifest that lists all available agents
manifest_hocon = '''
{
    "hello_world.hocon": true,
}
'''

# Write the manifest file
with open(f"./registries/manifest.hocon", "w") as f:
    f.write(manifest_hocon)

print("✓ Created manifest: ./registries/manifest.hocon")
```

**What's happening here?**
- The manifest lists all agent configuration files and enables/disables them
- Setting `"hello_world.hocon": true` tells neuro-san to load this agent
- If you have multiple agents, you can enable them all here

Next, tell neuro-san where to find the manifest:

```py
# Set the manifest location as an environment variable
os.environ['AGENT_MANIFEST_FILE'] = './registries/manifest.hocon'

print("✓ Set AGENT_MANIFEST_FILE environment variable")
```

## Step 3: Invoke the Agent

Now for the exciting part! Let's create a session and talk to our agent!

### 3.1: Create a Session

```py
from neuro_san.client.agent_session_factory import DirectAgentSessionFactory

# Create a factory for building agent sessions
factory = DirectAgentSessionFactory()

# Specify which agent to use (matches the filename without .hocon)
agent_name = 'hello_world'

# Create a direct session with the agent
session = factory.create_session(
    agent_name=agent_name,
    use_direct=True,  # Run the agent directly in-process
    metadata={},       # Optional metadata for the session
)

print(f"✓ Created session with agent: {agent_name}")
```

### 3.2: Prepare Your Message

```py
# Define the message you want to send to the agent
user_message = 'Hello how are you!?'

# Format it in the structure neuro-san expects
request_payload = {
    "user_message": {
        "text": user_message,
    }
}
```

### 3.3: Get the Response

The agent returns a streaming response. Let's collect all the messages:

```py
# Get the streaming response (returns a generator)
stream = session.streaming_chat(request_payload)

# Collect all messages from the stream
msg = []
for chat_msg in stream:
    msg.append(chat_msg)
    if chat_msg.get("done") is True:
        break

# msg = list(stream) # or you could do this too

# Print the agent's response
print(f"Agent Response: {msg[-1]['response']['text']}")
```

**Expected output:**

```txt
Agent Response: Hello! I'm doing well, thank you for asking. How about you?
```

### 3.4: Inspect the Full Response

To see all the details of what the agent returned:

```py
pprint(msg)
```

**What you'll see:**

The response includes rich metadata about the conversation, including:

```txt
[{'response': {'chat_context': {'chat_histories': [{'messages': [{'origin': [{'instantiation_index': 1,
                                                                              'tool': 'HelloWorldAgent'}],
                                                                  'text': 'Hello '
                                                                          'how '
                                                                          'are '
                                                                          'you!?',
                                                                  'type': <ChatMessageType.HUMAN: 2>},
                                                                 {'origin': [{'instantiation_index': 1,
                                                                              'tool': 'HelloWorldAgent'}],
                                                                  'text': 'Hello! '
                                                                          "I'm "
                                                                          'doing '
                                                                          'great, '
                                                                          'thank '
                                                                          'you '
                                                                          'for '
                                                                          'asking. '
                                                                          'How '
                                                                          'about '
                                                                          'you? '
                                                                          "How's "
                                                                          'your '
                                                                          'day '
                                                                          'going?',
                                                                  'type': <ChatMessageType.AI: 4>}],
                                                    'origin': [{'instantiation_index': 1,
                                                                'tool': 'HelloWorldAgent'}]}]},
               'text': "Hello! I'm doing great, thank you for asking. How "
                       "about you? How's your day going?",
               'type': <ChatMessageType.AGENT_FRAMEWORK: 101>}}]
```

**Understanding the response:**
- `response.text`: The actual text response from the agent
- `chat_context.chat_histories`: Full conversation history with message types and origins
- `type`: Message type indicators (HUMAN, AI, AGENT_FRAMEWORK)

## Step 4: Create a Reusable Function

Instead of repeating all that code every time, let's wrap it in a convenient function:

```py
from neuro_san.client.agent_session_factory import DirectAgentSessionFactory


def invoke_agent(agent_name: str, user_text: str, sly_data=None):
    """
    Invoke a neuro-san agent and return its response.
    
    Args:
        agent_name: Name of the agent to invoke (without .hocon extension)
        user_text: The message to send to the agent
        sly_data: Optional additional data to pass to the agent
    
    Returns:
        The final message from the agent containing the response
    """
    # Create the factory and session
    factory = DirectAgentSessionFactory()
    session = factory.create_session(
        agent_name=agent_name,
        use_direct=True,
        metadata={},
    )

    # Prepare the request
    request_payload = {
        "user_message": {
            "text": user_text,
        },
        "sly_data": sly_data,
    }

    # Stream the response and collect messages
    stream = session.streaming_chat(request_payload)
    msg = []
    for chat_msg in stream:
        msg.append(chat_msg)
        if chat_msg.get("done") is True:
            break
    
    # Return the last message (which contains the complete response)
    return msg[-1]
```

### Using the Function

Now invoking an agent is just one line of code:

```py
# Invoke the agent with a simple message
response = invoke_agent('hello_world', 'Hello! How are you?')

# Print just the text response
print(response['response']['text'])
```

**Expected output:**

```txt
Hello! I'm doing great, thank you for asking. How about you? How's your day going?
```

## Step 5: Using HTTP Requests (Alternative Method)

If you prefer running neuro-san as a separate server process, you can interact with it
via HTTP requests instead of direct invocation.

### 5.1: Start the Server

First, start the neuro-san server in a terminal:

```bash
python -m neuro_san.service.main_loop.server_main_loop
```

The server will start on `http://localhost:8080` by default.

### 5.2: Make HTTP Requests

Now you can send requests to your agent via HTTP:

```py
import requests

# Define the agent and message
agent_name = 'hello_world'
request_payload = {
    "user_message": {
        "text": "Hello! How are you?"
    }
}

# Send POST request to the agent endpoint
response = requests.post(
    f'http://localhost:8080/api/v1/{agent_name}/streaming_chat',
    json=request_payload,
    timeout=240
)

# Check for errors
response.raise_for_status()

# Parse the JSON response
data = response.json()

# View the response
pprint(data)
```

**When to use HTTP vs Direct invocation:**
- **Direct invocation**: Faster, runs in the same process, better for tight integration
- **HTTP requests**: Better for microservices, allows multiple clients, easier to scale

## Summary

Congratulations! You've learned how to:

1. ✓ **Create an agent configuration** using HOCON format
2. ✓ **Register your agent** in a manifest file
3. ✓ **Invoke agents directly** using `DirectAgentSessionFactory`
4. ✓ **Build reusable functions** for cleaner code
5. ✓ **Use HTTP requests** to communicate with a neuro-san server

## Further Reading

This tutorial is based on the
[agent_cli](https://github.com/cognizant-ai-lab/neuro-san/blob/main/neuro_san/client/agent_cli.py)
code. You can go through it for a better understanding.

## Troubleshooting

**Agent not found?**
- Verify the manifest path is correct in `AGENT_MANIFEST_FILE`
- Check that the agent name matches the filename (without `.hocon`)
- Ensure the agent is enabled in `manifest.hocon` with `true`

**API key errors?**
- Set your OpenAI API key: `export OPENAI_API_KEY=your_key_here`
- Or use a different model that you have credentials for

**Import errors?**
- Make sure neuro-san is installed: `pip install neuro-san`
- Check your Python environment is activated
