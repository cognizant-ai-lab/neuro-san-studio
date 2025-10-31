# Neuro AI Multi-Agent Accelerator – Getting Started

Welcome to the **Neuro AI Multi-Agent Accelerator** tutorial. In this guide, we will walk you through the process of
setting up a **Data-Driven Multi-Agent Network** using the `neuro-san` library, managing it via a Flask-based web UI,
and customizing how Large Language Model (LLM) based Agents coordinate with each other to solve tasks. We will also
explore switching LLM providers (like Ollama and Anthropic), adding custom-coded Tools, and running everything from a
single command.

---

## Table of Contents

<!-- TOC -->

* [Neuro AI Multi-Agent Accelerator – Getting Started](#neuro-ai-multi-agent-accelerator--getting-started)
    * [Table of Contents](#table-of-contents)
    * [1. Introduction](#1-introduction)
    * [2. Project Structure](#2-project-structure)
        * [Key directories and files:](#key-directories-and-files)
    * [3. Setting Up a Working Python Environment](#3-setting-up-a-working-python-environment)
    * [4. What is an LLM-based Agent?](#4-what-is-an-llm-based-agent)
        * [Agents for Autonomous Decision Making](#agents-for-autonomous-decision-making)
        * [Function Calling with Agents](#function-calling-with-agents)
        * [Data-Driven Agent Network](#data-driven-agent-network)
    * [5. Creating an Agent Network from Scratch](#5-creating-an-agent-network-from-scratch)
        * [Single Agent Network Example](#single-agent-network-example)
            * [Step 1: Create a file `registries/single_agent_example.hocon`:](#step-1-create-a-file-registriessingle_agent_examplehocon)
            * [Step 2: Run the server with this `.hocon` file. You can do so by:](#step-2-run-the-server-with-this-hocon-file-you-can-do-so-by)
        * [Multi-Agent Network Example](#multi-agent-network-example)
        * [LLM Config](#llm-config)
            * [Notes on `llm_config`:](#notes-on-llm_config)
            * [Running the multi-agent network:](#running-the-multi-agent-network)
    * [6. How to Switch LLMs in the Agent Network](#6-how-to-switch-llms-in-the-agent-network)
        * [Available Models and Preset Parameters](#available-models-and-preset-parameters)
        * [API Keys & Environment Variables](#api-keys--environment-variables)
        * [Using Local LLMs via Ollama](#using-local-llms-via-ollama)
    * [7. How to use tools in Neuro-San](#7-how-to-use-tools-in-neuro-san)
        * [Custom Tools](#custom-tools)
            * [Defining Functions in Agent Network (HOCON)](#defining-functions-in-agent-network-hocon)
            * [Schema of Parameters](#schema-of-parameters)
            * [Defining Tool in Python (Coded Tool)](#defining-tool-in-python-coded-tool)
        * [Prebuilt Tools (via toolbox)](#prebuilt-tools-via-toolbox)
            * [Using Toolbox Tools in Agent Network](#using-toolbox-tools-in-agent-network)
            * [Toolbox Configuration](#toolbox-configuration)
            * [Extending the Toolbox](#extending-the-toolbox)
    * [8. How to Access the Logs](#8-how-to-access-the-logs)
    * [9. How to Stop the servers](#9-how-to-stop-the-servers)
    * [10. Key Aspects of Neuro AI Multi-Agent Accelerator](#10-key-aspects-of-neuro-ai-multi-agent-accelerator)
    * [11. End Notes](#11-end-notes)

<!-- TOC -->

---

## 1. Introduction

**Neuro-San** is a multi-agent orchestration library that enables you to build **data-driven agent networks**. These
networks of agents can use **LLMs** (Large Language Models) and **coded tools** to coordinate and solve complex tasks
autonomously.

The library comes with a **Flask Web Client** (`neuro_san_web_client`) so that users can interact with these multi-agent
networks through a web-based UI. This entire setup is easily configurable using **HOCON** (`.hocon`) files.

**Note**: This tutorial is written with the help of the agent network example [advanced_calculator.hocon](../registries/basic/advanced_calculator.hocon).

---

## 2. Project Structure

Below is a simplified view of the reference project structure. You can adapt it to your needs.

```bash
.
├── README.md
├── coded_tools
│   └── basic
│     └── advanced_calculator
│         └── calculator_tool.py
├── logs
│   ├── client.log
│   └── server.log
├── registries
│   ├── basic
│   │      └── advanced_calculator.hocon
│   └── manifest.hocon
├── requirements.txt
├── run.py
```

### Key directories and files

* `coded_tools/`: Contains custom-coded tool classes (e.g., `calculator_tool.py`).
* `registries/`: Holds `.hocon` files that define multi-agent networks and their configurations.
* `logs/`: Where client and server logs are written.
* `run.py`: A starter script to run the server and the web client.

* Here are the detailed [instructions](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/README.md) to run
an agent network along with a web client.

---

## 3. Setting Up a Working Python Environment

Follow these steps to set up and activate your Python virtual environment:

```bash
# 1) Clone your project repository (if applicable)
git clone https://github.com/cognizant-ai-lab/neuro-san-studio
cd neuro-san-studio

# 2) Create a dedicated Python virtual environment
python -m venv venv

# 3) Activate it
# For Windows
.\venv\Scripts\activate && set PYTHONPATH=%cd%
# For Mac/Linux
source venv/bin/activate && export PYTHONPATH=`pwd`

# 4) Install the required Python packages.
pip install -r requirements.txt
```

Please find the detailed [instructions](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/README.md) to
run an agent network along with a web client.

Note: You may need to adapt the filenames if versions differ.

---

## 4. What is an LLM-based Agent?

An **LLM-based Agent** is a component in your agent network that uses a **Large Language Model** to process instructions
and make decisions. By embedding the agent’s logic in a data-driven configuration (the `.hocon` file), you can define:

<!-- pyml disable no-emphasis-as-heading,no-emphasis-as-header -->
* **Agent roles and responsibilities**
* **Tools** (or other agents) it can call
* **Function schema** that the agent can handle
<!-- pyml enable no-emphasis-as-heading,no-emphasis-as-header -->

### Agents for Autonomous Decision Making

These agents can coordinate tasks among themselves. A top-level (or front-man) agent can receive a user’s query, figure
out which sub-agents (or tools) are best suited to answer it, and orchestrate the communication necessary to generate a response.

### Function Calling with Agents

In Neuro AI Multi-Agent Accelerator, Agents may declare a function with defined parameters. Other agents can call this
function by providing the required parameters. This allows complex tasks to be broken into sub-tasks, each handled by
specialized agents or tools.

**Note**: Refer to this [OpenAI blog](https://community.openai.com/t/function-calling-parameter-types/268564/7) and
[OpenAI Cookbook](https://cookbook.openai.com/examples/function_calling_with_an_openapi_spec) for more information.

### Data-Driven Agent Network

A Data-Driven Agent Network is composed of multiple agents defined in a `.hocon` file. This file describes:

* **LLM configuration**: which model to use, how to connect to it, etc.
* **Agent definitions**: including instructions, roles, domain knowledge, and which tools/agents they can call.
* **Tools**: references to Coded Tools that contain Python functions or classes.

---

## 5. Creating an Agent Network from Scratch

### Single Agent Network Example

Let’s start simple. We’ll build a minimal `.hocon` file containing only one agent – the Math Geek. This will show how to
run a single-agent network that can handle basic math operations (though it won’t actually do the math by itself unless
you also link to or embed the coded tool).

#### Step 1: Create a file `registries/single_agent_example.hocon`

```hocon
{
    "llm_config": {
        "model_name": "llama3.1",
    },
    "commondefs": {
        "replacement_strings": {
            "instructions_prefix": """
                You are responsible for a segment of a problem.
                Only answer inquiries that are directly within your domain.
            """,
            "aaosa_instructions": """
                When you receive an inquiry:
                0. If you are clearly not the right agent...
                1. Always call your tools...
                2. ...
            """
        },
        "replacement_values": {}
    },
    "tools": [
        {
            "name": "Math Geek",
            "function": {
                "description": "I can help you to do quick calculations."
            },
            "instructions": """
                {instructions_prefix}
                Your name is `Math Geek`.
                You are the top-level agent for mathematics.
                {aaosa_instructions}
                - Only handle calculation related inquiries.
            """,
            "tools": []
        }
    ]
}
```

**Note**: You can also automatically create simple agent networks using our example agent_network_designer agent network
(see: [agent_network_designer.md](examples/agent_network_designer.md))

#### Step 2: Run the server with this `.hocon` file. You can do so by

```bash
# Make sure your venv is active
export AGENT_MANIFEST_FILE="./registries/manifest.hocon"
export AGENT_TOOL_PATH="./coded_tools"
python -m run
```

Since this agent has no further sub-agents or coded tools, it will simply respond to queries but won’t be able to do
actual calculations. It is functionally incomplete, but demonstrates a minimal single-agent network.

### Multi-Agent Network Example

Let’s take a look at a more robust multi-agent network file: `advanced_calculator.hocon`. Below is a simplified variant
with two agents: Math Geek and problem_formulator, plus a coded tool named `CalculatorTool`.

```hocon
{
    "llm_config": {
        "model_name": "llama3.1",
    },
    "commondefs": {
        "replacement_strings": {
            "instructions_prefix": """
                You are responsible for a segment of a problem...
            """,
            "aaosa_instructions": """
                When you receive an inquiry:
                0. If you are clearly not the right agent...
                1. Always call your tools...
                ...
            """
        },
        "replacement_values": {}
    },
    "tools": [
        {
            "name": "Math Geek",
            "function": {
                "description": "I can help you to do quick calculations."
            },
            "instructions": """
                {instructions_prefix}
                Your name is `Math Geek`.
                You are the top-level agent for the mathematics system.
                {aaosa_instructions}
            """,
            "tools": ["problem_formulator"]
        },
        {
            "name": "problem_formulator",
            "function": {
                "description": "Convert a math problem into a sequence of known operations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "inquiry": { "type": "string" }
                    },
                    "required": ["inquiry"]
                }
            },
            "instructions": """
                Your name is `Problem Formulator`.
                You will be handed a math problem and parse it into a known sequence of operations...
            """,
            "command": """
                - Identify operations and operands
                - Call the CalculatorTool
            """,
            "tools": ["CalculatorTool"]
        },
        {
            "name": "CalculatorTool",
            "function": {
                "description": "Solve the math operations",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "operation": { "type": "string" },
                        "operands": {
                            "type": "array",
                            "items": { "type": "float" }
                        }
                    },
                    "required": ["operation", "operands"]
                }
            },
            "class": "calculator_tool.CalculatorCodedTool",
            "command": "Perform the calculation."
        }
    ]
}
```

A few points to note about multi-agent networks:

* The snippet above is intentionally simplified. The actual `advanced_calculator.hocon` is more verbose and includes
more detail (you can see the full example provided in this tutorial’s introduction).
* The relationship between different agents can be defined in the hocon file itself. The down-chain agents can be
defined in the `tools` section of each agent definition in a parent-child style. For example the `Math Geek` agent has
access to the `problem_formulator` agent and the `problem_formulator` agent has access to the calculator agent via
'`"tools": ["CalculatorTool"]`
* It is possible to have the same down-chain agent available for several other agents at the same time.
* Defining an agent network is highly flexible. We can define all sort of networks: Single Agent Network, Hierarchical
Agent Network, DAG oriented Network, Single Agent with Coded Tools, Multiple Agents with Multiple Coded Tools.

### LLM Config

LLM configurations is a way to tell the agents which LLM (Large Language Model) to use in order to process a query sent
to it.

* LLM config is defined on top of the hocon file which implies that the same config is accessible to all the agents in
the network by default.
* It is possible to keep the default config and have separate config for each agent in the network. This means an agent
that does not have a defined config always uses the default llm_config defined on top of the hocon file.
* It is possible to have different LLMs for each of our agents for example, we can use `gpt-4o` for the front-man agent
`Math Geek` and `llama3.1` for the `problem_formulator`. Here is the hocon example to show that:

```hocon
{
    "llm_config": {
        "model_name": "gpt4-o",
    },
    "commondefs": {
        "replacement_strings": {
            "instructions_prefix": """
                You are responsible for a segment of a problem...
            """,
            "aaosa_instructions": """
                When you receive an inquiry:
                0. If you are clearly not the right agent...
                1. Always call your tools...
                ...
            """
        },
        "replacement_values": {}
    },
    "tools": [
        {
            "name": "Math Geek",
            "function": {
                "description": "I can help you to do quick calculations."
            },
            "instructions": """
                {instructions_prefix}
                Your name is `Math Geek`.
                You are the top-level agent for the mathematics system.
                {aaosa_instructions}
            """,
            "tools": ["problem_formulator"]
        },
        {
            "name": "problem_formulator",
            "llm_config": {
                "model_name": "llama3.1",
            },
            "function": {
                "description": "Convert a math problem into a sequence of known operations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "inquiry": { "type": "string" }
                    },
                    "required": ["inquiry"]
                }
            },
            "instructions": """
                Your name is `Problem Formulator`.
                You will be handed a math problem and parse it into a known sequence of operations...
            """,
            "command": """
                - Identify operations and operands
                - Call the CalculatorTool
            """
        },
    ]
}
```

#### Notes on `llm_config`

* The llm_config uses `model_name` as a parameter. We can use these models with openai, azure, ollama, anthropic and
nvidia as a provider.
* Here is a list of supported LLMs that can be used as `model_name` as of 26-Feb-2025:
    * OpenAI: ['gpt-3.5-turbo', 'gpt-3.5-turbo-16k', 'gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-4-turbo-preview',
    'gpt-4-1106-preview', 'gpt-4-vision-preview', 'gpt-4', 'gpt-4-32k']
    * AzureChatOpenAI: ['azure-gpt-3.5-turbo', 'azure-gpt-4']
    * Anthropic: ['claude-3-haiku', 'claude-3-sonnet', 'claude-3-opus', 'claude-2.1', 'claude-2.0', 'claude-instant-1.2']
    * Ollama: ['llama2', 'llama3', 'llama3.1', 'llama3:70b', 'llava', 'mistral', 'mistral-nemo', 'mixtral', 'qwen2.5:14b',
  'deepseek-r1:14b']
    * ChatNvidia: ['nvidia-llama-3.1-405b-instruct', 'nvidia-llama-3.3-70b-instruct', 'nvidia-deepseek-r1']
* Note that not all of these LLMs support function-calling, it is advisable to read the documentation before using any
of the LLMs.
* Each of these LLMs have several config params. Some of the common config parameters are: `model_name`, `temperature`, `max_tokens`.
* For the available configuration parameters of the above chat models, please refer to [Langchain Chat Models](
  https://python.langchain.com/docs/concepts/chat_models/) and their [respective documentation](https://python.langchain.com/docs/integrations/chat/)

#### Running the multi-agent network

```bash
export AGENT_MANIFEST_FILE="./registries/manifest.hocon"
export AGENT_TOOL_PATH="./coded_tools"
python -m run
```

Now, the top-level **Math Geek** agent will parse user queries, pass them to **problem_formulator**, which in turn calls
the **CalculatorTool**. The final answer is then relayed back to the user.

---

## 6. How to Switch LLMs in the Agent Network

Because **Neuro AI Multi-Agent Accelerator** uses `neuro-san`, it is LLM-agnostic, you can switch to different models or
providers by changing the `model_name` of `llm_config` in your `.hocon` file.

```hocon
"llm_config": {
    "model_name": "<your_model>",
    # Replace with the name of the model you want to use
    # You can also specify other fields, like temperature, max_tokens, etc.
}
```

### Available Models and Preset Parameters

All available models and their corresponding providers are defined in the
[default LLM info file](https://github.com/cognizant-ai-lab/neuro-san/blob/main/neuro_san/internals/run_context/langchain/llms/default_llm_info.hocon).

Each entry includes **preset parameters** that determine how the model should be used,
such as token limits or default temperature values.

If needed, you can **override these preset values** directly in your `llm_config`.

For more information on customizing or extending available models, refer to:
* [Using Custom or Non-Default LLMs](user_guide.md#using-custom-or-non-default-llms)
* [LangChain Chat Model Integration](https://python.langchain.com/docs/integrations/chat/)
for provider-specific parameter options

### API Keys & Environment Variables

For most cloud-based providers (e.g. OpenAI, Anthropic, Azure),
you’ll need to set the appropriate environment variables in your shell or .env file.
Common examples include:

* `OPENAI_API_KEY`
* `ANTHROPIC_API_KEY`
* `AZURE_OPENAI_ENDPOINT`

More details can be found in the following resources:

* [User Guide: LLM Configuration](user_guide.md#llm-configuration)
* [API Key Documentation](api_key.md)
* [.env.example](../.env.example)
* [LLM Info HOCON Reference Guide](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/llm_info_hocon_reference.md)
* [Agent HOCON Reference Guide](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/agent_hocon_reference.md)

### Using Local LLMs via Ollama

To use a locally hosted LLM with Ollama, follow the instructions in the [Ollama section](user_guide.md#ollama)
of the user guide.
These models can be configured in the same way, provided they are correctly installed and running locally.

---

## 7. How to use tools in Neuro-San

Neuro-San supports two types of tools that agents can call during execution:

1. **Custom Tools** – Built using Neuro-San’s `CodedTool` interface. These allow you to define your own logic in Python
and integrate it with the agent.
2. **Prebuilt Tools (via toolbox)** – Tools that are already implemented and configured for reuse. These include:

LangChain’s `BaseTool` implementations (e.g., `tavily_search`, `requests_get`)

Shared `CodedTool` implementations that are registered in the toolbox config file

Use **Custom Tools** when your application needs behavior that isn't covered by the prebuilt options — such as accessing
APIs, performing custom calculations, or interacting with internal systems.

### Custom Tools

In Neuro-San, custom tool integration is done through **Coded Tools** — Python class that implement the `CodedTool` interface.

These tools allow agents to perform specialized operations like API calls, database queries, or computations that go
beyond the LLM’s native capabilities.

To integrate a custom tool, **you must define it in both HOCON and python files**:

1. [**Agent Network (HOCON)**](#defining-functions-in-agent-network-hocon) – for configuration and orchestration  
2. [**Python (Coded Tool)**](#defining-tool-in-python-coded-tool) – for actual implementation

---

#### Defining Functions in Agent Network (HOCON)

Each tool must define a `function` block, and reference a Python `class`.
>The **LLM provides values** for inputs defined in `function.parameters`.  
However, users can **manually provide additional arguments** using the `args` field.

* **`function`**
    * `description`: Describes when and how to use the tool.
    * `parameters`: Defines input arguments. Optional if no parameters are required.
* **`class`**
    * Python class reference in `module.Class` format.
* **`args`**
    * User-specified arguments that override or supplement LLM inputs. Optional.

---

#### Schema of Parameters

Neuro-San supports the following data types:  
`string`, `int`, `float`, `boolean`, `array` (list), `object` (dict)

* `array` must include an `items` field to define the element type
* `object` must include a `properties` field
* The top-level `parameters` must always be an `object`

| Field       | Description                                                                 |
|-------------|-----------------------------------------------------------------------------|
| `type`      | Must be `object`                                                            |
| `properties`| Dict of argument names → each has a `type` and `description`               |
| `required`  | List of required argument names                                             |

---

#### Defining Tool in Python (Coded Tool)

* Inherit from `CodedTool`
* Implement either `invoke` or `async_invoke`
  > Neuro-San prefers `async_invoke`, and falls back to `invoke` if unavailable
* Access LLM and user-provided arguments via `args`

#### Tool Path

* The tool's path can be set via the environment variable:
  `AGENT_TOOL_PATH`

* If not set, the default path is:
  `neuro_san/coded_tools`

* A tool module placed in a folder that **matches the HOCON file name** (excluding `.hocon`)
  will be **scoped only to that specific agent network**.

* To **reuse a tool across multiple networks**, place its module directly in the configured tool path (`AGENT_TOOL_PATH`).

* This allows you to choose between:
    * **Local tools** tied to one agent network, and
    * **Shared tools** accessible by multiple networks.

---

#### Example 1: Tool with parameters

##### HOCON

```json
{
  "llm_config": {
     "model_name": "gpt-4o"
  },
  "tools": [
    {
      "name": "weather_agent",
      "instructions": "Use your tool to provide weather report to the user.",
      "tools": ["get_weather"]
    },
    {
      "name": "get_weather",
      "function": {
        "description": "Provide weather at a given loaction.",
        "parameters": {
          "type": "object",
          "properties": {
            "location": {
              "type": "string",
              "description": "Location to provide weather for"
            }
          },
          "required": ["location"]
        }
      },
      "args": {
        "current_weather": "cloudy"
      },
      "class": "weather_tool.WeatherTool"
    }
  ]
}
```

##### Python

```python
class WeatherTool(CodedTool):

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]):
        location = args.get("location")
        current_weather = args.get("current_weather")

        if current_weather:
            return f"It is {current_weather} in {location}."

        return f"It is always sunny in {location}."
```

---

#### Example 2: Tool with no parameters

##### HOCON (with no parameters)

```json
{
  "llm_config": {
     "model_name": "gpt-4o"
  },
  "tools": [
    {
      "name": "datetime_agent",
      "instructions": "Use your tool to provide current date and time..",
      "tools": ["current_date_time"]
    },
    {
      "name": "current_date_time",
      "function": {
        "description": "Return current date and time."
      },
      "class": "date_time.DateTime"
    }
  ]
}
```

##### Python (with no parameters)

```python
class DateTime(CodedTool):

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]):
        # Get current UTC time
        now = datetime.now(timezone.utc)

        return str(now)
```

### Prebuilt Tools (via Toolbox)

Neuro-San includes a powerful **Toolbox** system that allows you to reuse existing tools across agent networks without
redefining them every time.

These tools are already integrated and can be plugged into agents directly via configuration.

Toolbox tools come in two forms:

* LangChain Tools – Built-in tools like tavily_search, requests_get, etc., implemented using LangChain’s BaseTool.

* Shared Coded Tools – Predefined tools using the CodedTool interface (Python classes) that are already available and
registered in your Toolbox config.

These are called prebuilt because you can use them right away without defining their logic or schema again in the agent
network config.

#### Using Toolbox Tools in Agent Network

To use any tool from the Toolbox, simply reference it in the toolbox field of your agent config:

```json
{
  "name": "search_agent",
  "instructions": "Use web search to find information for the user.",
  "toolbox": "tavily_search"
}
```

You do **not** need to define `function`, `parameters`, or `class` for toolbox tools — that information is already
included in the langchain tools class or the Toolbox config file.

#### Toolbox Configuration

Toolbox tools are defined in a centralized configuration file.
This [file](https://github.com/cognizant-ai-lab/neuro-san/blob/main/neuro_san/internals/run_context/langchain/toolbox/toolbox_info.hocon)
includes definitions for both LangChain tools and shared coded tools. If the tool is defined in the toolbox config, you
don’t need to redefine it in the agent network — just reference it by name.

##### LangChain Example

```json
"tavily_search": {
  "class": "langchain_community.tools.tavily_search.TavilySearchResults",
  "args": {
    "api_wrapper": {
      "class": "langchain_community.utilities.tavily_search.TavilySearchAPIWrapper"
    }
  }
}
```

##### Coded Tool Example

```json
"rag_retriever": {
  "class": "rag.Rag",
  "description": "Retrieve information on the given urls",
  "parameters": {
    "type": "object",
    "properties": {
      "urls": { "type": "array", "items": { "type": "string" } },
      "query": { "type": "string" }
    },
    "required": ["urls", "query"]
  }
}
```

#### Extending the Toolbox

If you want to add your own tools to the Toolbox (so they can be reused easily):

* **For coded tools**: Implement your tool in Python using the `CodedTool` interface.

* **Add your tool to a config file**: Define an entry in your custom toolbox info file,
following the structure shown in the previous examples.

* **Register the config file** by one of the following methods:

    * Set the `toolbox_info_file` key
    * Use the `AGENT_TOOLBOX_INFO_FILE` environment variable

This setup allows you to introduce custom tools without modifying the built-in toolbox definitions.

See also

* [Toolbox](user_guide.md#toolbox) section of the user guide
* [Toolbox Info HOCON File Reference](
    https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/toolbox_info_hocon_reference.md) documentation

---

## 8. How to Access the Logs

By default, when you run:

```bash
python -m run
```

* The server logs go to logs/server.log.
* The client (web UI) logs go to logs/client.log.

Additionally, you will see logs on your terminal. Checking these files is useful for:

* Debugging agent interactions
* Viewing any errors or exceptions
* Auditing how the queries are being orchestrated

---

## 9. How to Stop the servers

When you are running the server in the foreground (via `python -m run`), simply press:

* `CTRL + C` on Windows/Mac/Linux terminals
* This will terminate both the Flask web client server and the `neuro_san` server gracefully.

If you launched them separately, you would stop each process individually (again by `CTRL + C` or sending a kill signal).

---

## 10. Key Aspects of Neuro AI Multi-Agent Accelerator

* **Flexibility of Use**: Define any agent network structure using `.hocon` files, easily adjustable for different use
cases and tasks.
* **LLM Agnostic**: Swap between OpenAI, Anthropic, Ollama, Azure, or your own custom model endpoints with minimal
configuration changes.
* **Cloud Agnostic**: Host your solutions on any cloud or on-prem python environment.
* **Tool/Function Calling**: Agents can systematically call coded tools or other sub-agents, enabling powerful, modular,
and autonomous decision workflows.
* **Hierarchical Agent Networks**: You can create nested agent networks to handle complex tasks in a structured manner.

---

## 11. End Notes

You’ve now seen how to:

* Set up a Python environment and install the requirements.
* Create single-agent and multi-agent networks in `.hocon` files.
* Switch LLM providers (e.g., Ollama, Anthropic, OpenAI).
* Add coded tools to expand agent capabilities.
* Run the server and Flask client.
* Check logs and stop the server.

Feel free to be creative, explore adding more complex agents, linking them in various ways, or building advanced coded
tools. We hope you find Neuro AI Multi-Agent Accelerator intuitive, powerful, and adaptable to your needs.

---
