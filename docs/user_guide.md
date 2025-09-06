# User guide

<!-- TOC -->

* [User guide](#user-guide)
  * [Simple agent network](#simple-agent-network)
  * [Hocon files](#hocon-files)
    * [Import and substitution](#import-and-substitution)
    * [Manifest](#manifest)
    * [Agent network](#agent-network)
      * [Agent specifications](#agent-specifications)
      * [Tool specifications](#tool-specifications)
      * [LLM specifications](#llm-specifications)
  * [LLM configuration](#llm-configuration)
    * [OpenAI](#openai)
    * [AzureOpenAI](#azureopenai)
    * [Anthropic](#anthropic)
    * [Bedrock](#bedrock)
      * [Default Bedrock models](#default-bedrock-models)
    * [Gemini](#gemini)
    * [Ollama](#ollama)
      * [Prerequisites](#prerequisites)
      * [Configuration](#configuration)
      * [Using Ollama in Docker or Remote Server](#using-ollama-in-docker-or-remote-server)
      * [Example agent network](#example-agent-network)
    * [See also](#see-also)
  * [LLM Fallbacks](#llm-fallbacks)
  * [Using custom or non-default LLMs](#using-custom-or-non-default-llms)
    * [Using the `class` Key](#using-the-class-key)
    * [Extending the default LLM info file](#extending-the-default-llm-info-file)
      * [Registering custom LLM info file](#registering-custom-llm-info-file)
  * [Coded tools](#coded-tools)
    * [Simple tool](#simple-tool)
    * [API calling tool](#api-calling-tool)
    * [Sly data](#sly-data)
  * [Toolbox](#toolbox)
    * [Default tools in toolbox](#default-tools-in-toolbox)
      * [Langchain tools in toolbox](#langchain-tools-in-toolbox)
      * [Coded tools in toolbox](#coded-tools-in-toolbox)
    * [Usage in agent network config](#usage-in-agent-network-config)
    * [Adding tools in toolbox](#adding-tools-in-toolbox)
  * [Logging and debugging](#logging-and-debugging)
  * [Advanced](#advanced)
    * [Subnetworks](#subnetworks)
    * [AAOSA](#aaosa)
  * [Connect with other agent frameworks](#connect-with-other-agent-frameworks)

<!-- TOC -->

## Simple agent network

The `music_nerd` agent network is the simplest agent network possible: it contains a single agent
that answers questions about music since the 60s. See its description here: [docs/examples/music_nerd.md](../docs/examples/music_nerd.md).

The steps to start the server and the client are described in the [README](../README.md).
When starting, the first thing the server will do is load the agent network configurations
from the "manifest" file. The manifest file is specified by the `AGENT_MANIFEST_FILE` environment variable:

```bash
AGENT_MANIFEST_FILE="./registries/manifest.hocon"
```

Open [./registries/manifest.hocon](../registries/manifest.hocon) and look at its contents. It should look something
like this:

```hocon
{
    # ... other agent networks ... #
    "music_nerd.hocon": true,
    # ... other agent networks ... #
}
```

This tells the server to load the `music_nerd.hocon` file from the same `/registries` folder.

Setting the value to `false` would make the server ignore this agent network.

Open [../registries/music_nerd.hocon](../registries/hello_world.hocon) and have a look at it.
For now just note that it contains:

* an `llm_config` section that specifies which LLM to use by default for the agents in this file
* a `tools` section that contains a single agent, the "frontman", called `MusicNerd`

Read the instructions of the agent to see what it does.
Feel free to modify the instructions to see how it affects the agent's behavior.
See if you can make it a soccer expert for instance!

We'll describe the structure of agent networks' `.hocon` files in next section.

## Hocon files

### Import and substitution

HOCON files support importing content from other HOCON files using the unquoted keyword `include`, followed by
whitespace and the path to the imported file as a quoted string:

```hocon
include "config.hocon"
```

> **Note**: The file path in include should be an **absolute path** to ensure it can be resolved correctly.

HOCON supports value substitution by referencing previously defined configuration values. This allows constants to be
defined once and reused throughout the file.

To substitute a value, wrap the referenced key in `${}`:

```hocon
"function": ${aaosa_call}
```

To substitute a nested value inside an object or dictionary, use dot notation:

```hocon
"name": ${info.name}
```

Note that substitutions are **not parsed inside quoted strings**. If you need to include a substitution within a string,
you can quote only the non-substituted parts:

```hocon
"instructions": ${instruction_prefix} "main instruction" ${instruction_suffix}
```

You can see a working example here: [../registries/smart_home_include.hocon](../registries/smart_home_include.hocon).

For more details, please see [https://github.com/lightbend/config/blob/main/HOCON.md#substitutions](https://github.com/lightbend/config/blob/main/HOCON.md#substitutions)

### Manifest

A manifest file is a list of agent network configurations that the server will load.

It's simple dictionary where the keys are the names of the agent network configuration files
and the values are booleans. For instance:

```hocon
{
    "agent_network_A.hocon": true,
    "agent_network_B.hocon": false,
    "agent_network_C.hocon": true,
}
```

In this example the server will load agent networks A and C but not B.

When you start the server, you can see which agent networks have been loaded by looking at the logs:

```bash
> python -m neuro_san.service.main_loop.server_main_loop --port 30011

tool_registries found: ['agent_network_A', 'agent_network_C']
```

For more details, please check the [Agent Manifest HOCON File Reference](
    https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/manifest_hocon_reference.md) documentation.

### Agent network

#### Agent specifications

<!-- pyml disable line-length -->
| **Field**    | **Description**                                                                                                                               |
|--------------|-----------------------------------------------------------------------------------------------------------------------------------------------|
| name         | Text handle for other agent specs and hosting system to refer to.                                                                             |
| function     | Open AI function spec (standard) that formally describes the various inputs that the agent expects.                                           |
| instructions | Text that sets up the agent in detail for its task.                                                                                           |
| command      | Text that sets the agent in motion after it receives all its inputs.                                                                          |
| tools        | Optional list of references to other agents that this agent is allowed to call in the course of working through their input and instructions. |
| llm_config   | Optional agent-specification for different LLMs for different purposes such as specialization, costs, etc.                                    |
<!-- pyml enable line-length -->

#### Tool specifications

<!-- pyml disable line-length -->
| **Field** | **Description**                                                                                                                                                                        |
|-----------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name      | A unique identifier used to reference this tool in other agent specifications.                                                                                                         |
| class     | A Python import path pointing to the class or function to invoke when the tool is called. Must follow the format `<module>.<Class>`. See [Coded tools](#coded-tools) for more details. |
| function  | An OpenAI-compatible function schema that defines the expected input parameters for the tool specified in `class`.                                                                     |
| toolbox   | The name of a predefined tool from the toolbox. If this field is set, you must not specify `class` or `function`.                                                                      |
<!-- pyml enable line-length -->

#### LLM specifications

<!-- pyml disable line-length -->
| **Field**   | **Description**                                                                                                                                |
|-------------|------------------------------------------------------------------------------------------------------------------------------------------------|
| model_name  | Name of the model to use (i.e. “gpt-4o”, “claude-3-haiku”).                                                                                    |
| class       | Optional key for using custom models or providers. See [Using Custom or Non-Default LLMs](#using-custom-or-non-default-llms) for more details. |
| temperature | Optional level of randomness 0.0-1.0 to use for LLM results.                                                                                   |
<!-- pyml enable line-length -->

See next section for more information about how to specify the LLM(s) to use.

For a full description of the fields, please refer to the [Agent Network HOCON File Reference](
    https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/agent_hocon_reference.md) documentation.

## LLM configuration

The `llm_config` section in the agent network configuration file defines which LLM should be used by the agents.

You can specify it at two levels:
* **Network-level**: Applies to all agents in the file.
* **Agent-level**: Overrides the network-level configuration for a specific agent.

Neuro-SAN includes several predefined LLM providers and models. To use one of these, set the `model_name` key to
the name of the model you want. In addition, model-specific parameters (such as `temperature`, `max_tokens`, etc.)
can be set alongside `model_name`.
A full list of available models and parameters can be found in the
[default LLM info file](https://github.com/cognizant-ai-lab/neuro-san/blob/main/neuro_san/internals/run_context/langchain/llms/default_llm_info.hocon).

> ⚠️ Different providers may require unique configurations or environment variables.

The following sections provide details for each supported provider, including required parameters and setup instructions.

### OpenAI

To use an OpenAI LLM, set the `OPENAI_API_KEY` environment variable to your OpenAI API key
and specify which model to use in the `model_name` field:

```hocon
    "llm_config": {
        "model_name": "gpt-4o",
    }
```

See [./examples/music_nerd.md](./examples/music_nerd.md) for an example.

### AzureOpenAI

To create an Azure OpenAI resource

* Go to Azure [portal](https://portal.azure.com/)
* Click on `Create a resource`
* Search for `Azure OpenAI`
* Select `Azure OpenAI`, then click Create  

After your Azure OpenAI resource is created, you must deploy a model

* Go to Azure [portal](https://portal.azure.com/)
* Under `Resources`, select your Azure OpenAI resource
* Click on `Go to Azure AI Foundry portal`
* Click on `Create new deployment`
* Choose a model (e.g., `gpt-4o`), then pick a deployment name (e.g., `my-gpt4o`), and click `Deploy`
* Find the `api_version` on the deployed model page (e.g., "2024-12-01-preview")
* Optionally, set environment variables to the value of the deployment name and API version

    export AZURE_OPENAI_DEPLOYMENT_NAME="Your deployment name"\
    export OPENAI_API_VERSION="Your OpenAI API version"

Finally, get your API key and endpoint

* Go to Azure [portal](https://portal.azure.com/)
* Under `Resources`, select your Azure OpenAI resource
* Click on `Click here to view endpoints`
* Optionally, set environment variables to the value of the API key and the endpoint

    export AZURE_OPENAI_API_KEY="your Azure OpenAI API key"\
    export AZURE_OPENAI_ENDPOINT="https://your_base_url.openai.azure.com"

If you set the environment variables (recommended), the `llm_config` in your `.hocon` file would be as follows:

```hocon
    "llm_config": {
        "model_name": "azure-gpt-4o",
    }
```

If you did NOT set the environment variables, the `llm_config` in your `.hocon` file would be as follows:

```hocon
    "llm_config": {
        "model_name": "azure-gpt-4o",
        "openai_api_key": "your_api_key"
        "openai_api_version": "your_api_version",
        "azure_endpoint": "your_end_point",
        "deployment_name": "your_deployment_name"
    }
```

> **Note**: Make sure your `model_name` starts with `azure-`. E.g., if you have a `gpt-4o` model,
> your model name should be `azure-gpt-4o`, or else your agent network might think you are using
> an OpenAI model (and not an Azure OpenAI model).
>
> **Tip**: While `OPENAI_API_KEY` may still be recognized for backward compatibility,
> it's recommended to use `AZURE_OPENAI_API_KEY` to avoid conflicts and align with upcoming changes in LangChain.
>
> **Note**: Some Azure OpenAI deployments may have a lower `max_tokens` limit than the default associated with the
> `model_name` in Neuro-San. If the `max_tokens` value in your `llm_config` exceeds the actual limit of the model
> specified by `deployment_name`, the LLM will fail to return a response — even if the prompt itself is within limits.
> To fix this, explicitly set a `max_tokens` value in your `llm_config` that matches the deployed model’s actual capacity.

<!-- pyml disable line-length-->
See [Azure OpenAI Quickstart](
    https://learn.microsoft.com/en-us/azure/ai-services/openai/chatgpt-quickstart?tabs=keyless%2Ctypescript-keyless%2Cpython-new%2Ccommand-line&pivots=programming-language-python) for more information.
<!-- pyml enable line-length-->

### Anthropic

To use Anthropic models, set the `ANTHROPIC_API_KEY` environment variable to your Anthropic API key
and specify which model to use in the `model_name` field of the `llm_config` section of an agent network hocon file:

```hocon
    "llm_config": {
        "model_name": "claude-3-7-sonnet",
    }
```

Here you can get an Anthropic API [key](https://console.anthropic.com/settings/keys)

### Bedrock

To use Amazon Bedrock models, you need valid AWS credentials. Below are the recommended ways to provide credentials,
followed by guidance on how to select and configure models.

1. Environment variables

    You can set the following environment variables directly:

   * `AWS_ACCESS_KEY_ID`

   * `AWS_SECRET_ACCESS_KEY`

   * `AWS_REGION` or `AWS_DEFAULT_REGION`

    > Note: You may set `region_name` in the `llm_config` of the agent network HOCON file instead

    This is sufficient if you only have **one AWS profile** or if you're certain these environment variables
    correspond to the correct credentials.

2. Named profile (**required for multiple profiles**)

    If you have **multiple profiles** in `~/.aws/credentials` or `~/.aws/config`, it's recommended to explicitly set
    the credentials_profile_name field to avoid ambiguity. This tells the system exactly which profile to use,
    even if other credentials are present in the environment.

    If `credentials_profile_name` is not specified in the `llm_config` of the HOCON file:

   * The default profile will be used.

   * On EC2 instance, credentials may be automatically loaded from the Instance Metadata Service (IMDS).

    See the full AWS credential resolution order
    [here](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html)

   > Note: You may also need to specify environment variable `AWS_REGION` or the `region_name` field if
region is not set in your AWS profile.

3. Model selection

    In your agent network HOCON file, specify the model name, the credentials profile, and the region (if needed):

    ```hocon
        "llm_config": {

            # Bedrock documentation lists both model name and model ID.
            # Use the **Model ID** as the value for "model_name".
            "model_name": "bedrock-us-claude-3-7-sonnet",

            # Optional if using env vars or default profile
            "credentials_profile_name": "<profile_name>",

            # Optional, but required if not defined in your profile config
            # or with env var AWS_REGION or AWS_DEFAULT_REGION
            "region_name": "us-west-2"
        }
    ```

#### Default Bedrock models

The default supported Bedrock model names currently include:

* `bedrock-us-claude-opus-4`

* `bedrock-us-claude-sonnet-4`

* `bedrock-us-claude-3-7-sonnet`

These models require access to one of the following AWS regions:

* `us-east-1`

* `us-east-2`

* `us-west-2`

If these are not available in your account, you can still use other Bedrock models available to you by
[using the class key](#using-the-class-key).

To find which models are available in your region, refer to the official AWS documentation:
[Supported models – Amazon Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html)

### Gemini

To use Gemini models, set the `GOOGLE_API_KEY` environment variable to your Google Gemini API key
and specify which model to use in the `model_name` field of the `llm_config` section of an agent network hocon file:

```hocon
    "llm_config": {
        "model_name": "gemini-2.0-flash",
    }
```

You can get an Google Gemini API [key](https://ai.google.dev/gemini-api/docs/api-key) here.

### Ollama

This guide walks you through how to use a locally running LLM via [Ollama](https://github.com/ollama/ollama) in neuro-san.

#### Prerequisites

1. Download and Install Ollama

   Download Ollama from [https://ollama.com](https://ollama.com) and install it on your machine.

2. Download the Model

   Use the following command to download and prepare the model:

   ```bash
    ollama run <model_name>      # replace <model_name> with your chosen model, e.g. qwen3:8b
   ```

   This ensures the model is downloaded and ready for use.

3. Update the Model (Optional)

    Ollama may release updates to a model (e.g., performance improvements) under the same model name.
    To update the model to the latest version:

    ```bash
    ollama pull <model_name>     # replace <model_name> with your chosen model, e.g. qwen3:8b
    ```

4. Tool Calling Support

    Ensure that the chosen model from Ollama supports tool use. You can check this in
    [Ollama's searchable model directory](https://ollama.com/search?c=tools).

5. Default LLM Info

   To use the model in the `hocon` file, its name and relevant information, such as `max_token`, must be included in the
   [default llm info file](https://github.com/cognizant-ai-lab/neuro-san/blob/main/neuro_san/internals/run_context/langchain/llms/default_llm_info.hocon).

#### Configuration

In your agent network hocon file, set the model name in the `llm_config` section. For example:

```hocon
    "llm_config": {
        "model_name": "qwen3:8b",
    }
```

> Note: Some Ollama models include reasoning or "thinking" capabilities, which may make their responses more verbose.
You can disable this behavior by adding `"reasoning": false` to `llm_config`.
The default is `None`, which means the model will use its built-in default behavior. For more details,
see [ChatOllama documentation](https://python.langchain.com/api_reference/ollama/chat_models/langchain_ollama.chat_models.ChatOllama.html#langchain_ollama.chat_models.ChatOllama.reasoning)

Make sure the model you specify is already downloaded and available in the Ollama server.

> Tip: Ollama models may respond slowly depending on model size and hardware.
If you're encountering the default 120 seconds timeouts,
you can increase it by setting the `max_execution_seconds` key in the agent network HOCON.
See [agent network documentation](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/agent_hocon_reference.md#max_execution_seconds)
for more details.

#### Using Ollama in Docker or Remote Server

By default, Ollama listens on `http://127.0.0.1:11434`. However, if you are running Ollama inside Docker or
on a remote machine, you need to explicitly set the `base_url` in `llm_config`.

Here’s a ready-to-use `llm_config` block—just replace `<HOST>` with your setup:

```hocon
    "llm_config": {
        "model_name": "qwen3:8b",
        "base_url": "http://<HOST>:11434"
    }
```

Examples:

* Local (default): omit `base_url` or use `127.0.0.1`

* Remote VM: `<HOST>` → `192.168.1.10`

* Public DNS: `<HOST>` → `example.com`

* Docker Compose: `<HOST>` → container name (ensure port `11434` is exposed)

Just paste the block and update `<HOST>` to match your environment.

> If you omit the port, and `base_url` starts with

* `http` → port 80

* `https` → port 443

* neither → defaults to `http://<base_url>:11434`

For more information on logic of parsing the `base_url` see [Ollama python SDK](https://github.com/ollama/ollama-python/blob/main/ollama/_client.py#L1173)

#### Example agent network

See the [./examples/music_nerd_pro_local.md](./examples/music_nerd_pro_local.md) for a complete working example.

For more information about how to use Ollama with LangChain,
see [this page](https://python.langchain.com/docs/integrations/chat/ollama/)

### See also

For a full description of `llm_config`, please refer to the [LLM config](
    https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/agent_hocon_reference.md#llm_config) documentation.

## LLM Fallbacks

Neuro-SAN supports LLM fallbacks, which allow you to specify a list of LLMs to use in case the primary LLM fails.
In the `llm_config` block, put each LLM configuration in a `fallbacks` list.
The list of LLM configs is tried in order until one succeeds.

In this example, as seen in [./examples/music_nerd_llm_fallbacks.md](./examples/music_nerd_llm_fallbacks.md),
the agent network will use OpenAI's `gpt-4o` model first,
and if that fails (for example, due to rate limits or service outages),
it will automatically fall back to Anthropic's `claude-3-7-sonnet` model:

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

## Using custom or non-default LLMs

If your desired model is not listed in the
[default llm info file](https://github.com/cognizant-ai-lab/neuro-san/blob/main/neuro_san/internals/run_context/langchain/llms/default_llm_info.hocon),
you can use it in one of two ways:

1. Use the `class` key directly in `llm_config`.

2. Extend the default LLM info file with your own models and providers.

### Using the `class` Key

You can define an LLM directly in `llm_config` using the `class` key in two different scenarios:

1. For supported providers

    Set the `class` key to one of the values listed below, then specify the model using the `model_name` key.

    | LLM Provider  | `class` Value   |
    |:--------------|:----------------|
    | Amazon Bedrock| `bedrock`       |
    | Anthropic     | `anthropic`     |
    | Azure OpenAI  | `azure_openai`  |
    | Google Gemini | `gemini`        |
    | NVidia        | `nvidia`        |
    | Ollma         | `ollama`        |
    | OpenAI        | `openai`        |

    For example,

    ```hocon
        "llm_config": {
            "class": "openai",
            "model_name": "gpt-4.1-mini"
        }
    ```

    <!-- markdownlint-disable MD013 -->
    You may only provide parameters that are explicitly defined for that provider's class under the `classes.<class>.args`
    section of  
    [default llm info file](https://github.com/cognizant-ai-lab/neuro-san/blob/main/neuro_san/internals/run_context/langchain/llms/default_llm_info.hocon).
    Unsupported parameters will be ignored.
    <!-- markdownlint-enable MD013 -->

2. For custom providers

    Set the `class` key to the full Python path of the desired LangChain-compatible chat model class in the format:

    ```hocon
    <langchain_package>.<module>.<ChatModelClass>
    ```

    Then, provide any constructor arguments supported by that class in `llm_config`, such as

    ```hocon
        "llm_config": {
            "class": "langchain_groq.chat_models.ChatGroq",
            "model": "llama-3.1-8b-instant",
            "temperature": 0.5
        }
    ```

    For a full list of available chat model classes and their parameters, refer to:  
    [LangChain Chat Integrations Documentation](https://python.langchain.com/docs/integrations/chat/)

    > _Note: Neuro-SAN requires models that support **tool-calling** capabilities._

### Extending the default LLM info file

You can also add new models or providers by extending the
[default llm info file](https://github.com/cognizant-ai-lab/neuro-san/blob/main/neuro_san/internals/run_context/langchain/llms/default_llm_info.hocon).

1. Adding new models for supported providers

    In your custom LLM info file, define the new model using a unique key (e.g. `gpt-4.1-mini`) and assign it a `class`
    and `max_output_tokens`, such as:

    ```hocon
    "gpt-4.1-mini": {
        "class": "openai",
        "max_output_tokens": 32768
    }
    ```

2. Adding custom providers

* Adding model and class in llm info file

    To support a custom provider, define the `class` value (e.g. `groq`), the model config, and also extend the
    `classes` section:

    ```hocon
    "llama-3.3-70b-versatile": {
        "class": "groq",
        "max_output_tokens": 32768
    }

    "classes": {
        "factories": [ "llm_info.groq_langchain_llm_factory.GroqLangChainLlmFactory" ]
        "groq": {
            "temperature": 0.5,
            # Add arguments that you want to pass to the llm here.
        }
    }
    ```

    You can then reference the new provider class (`groq` in this case) in any `llm_config`.

* Implementing a custom factory

    You’ll need to implement a factory class that matches the path you specified in `factories`.

    * Your factory must subclass [`LangChainLlmFactory`](https://github.com/cognizant-ai-lab/neuro-san/blob/main/neuro_san/internals/run_context/langchain/llms/langchain_llm_factory.py)
    * It must implement a `create_base_chat_model(config, callbacks)` method
        * `config` will contain:
            * `model_name`
            * `class` (e.g. `groq`)
            * Parameters defined under `classes.groq
        `callbacks` is typically used for token counting

    <!-- markdownlint-disable MD013 -->
    See
    [`StandardLangChainLlmFactory`](https://github.com/cognizant-ai-lab/neuro-san/blob/main/neuro_san/internals/run_context/langchain/llms/standard_langchain_llm_factory.py)
    as a reference implementation.
    <!-- markdownlint-enable MD013 -->

#### Registering custom LLM info file

To load your own llm info file, you can specify its location using one of the following methods:

* The `llm_info_file` key in your agent’s HOCON configuration
    > **Note:** The `agent_llm_info_file` key has been **deprecated as of version 0.5.46**.  
    > Please use `llm_info_file` instead.  
    > `agent_llm_info_file` will remain supported until `neuro-san==0.6.0`.

* The `AGENT_LLM_INFO_FILE` environment variable (fallback if the above is not set)

For more information on llm info file, please see [LLM Info HOCON File Reference](
    https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/llm_info_hocon_reference.md) documentation.

## Coded tools

Coded tools are coded functionalities that extend agent's capabilities beyond its core reasoning capabilities and allow
it to interact with databases, APIs, and external services.

### Simple tool

[music_nerd_pro](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/examples.md#music-nerd-pro) is a
simple agent that helps with music-related inquiries. It uses a simple coded tool which is implemented in Python -- The
coded tool does not call an API.

### API calling tool

[intranet_agents_with_tools](
    https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/examples.md#intranet-agents-with-tools) is a
    multi-agent system that mimics the intranet of a major corporation. It allows you to interact with and get
    information from various departments such as IT, Finance, Legal, HR, etc. The HR agent calls a coded tool
    implemented in Python that calls HCM APIs.

### Sly data

A `sly_data` dictionary can be passed along with the `ChatRequest` from the client side.
The `sly_data` will not be seen by the LLMs, and by default, will not leave the agent network.
Within the agent network the `sly_data` is visible to the coded tools and can be used as a
bulletin-board between coded tools.

This policy is one of security-by-default, whereby no `sly_data` gets out of the agent network
at all unless otherwise specified. It's only when a boundary is crossed that the question of
what goes through arises. There are 3 boundaries:

1. What goes out to external networks (`to_downstream`). For instance, you may not want to send
   credentials to an agent network that lives on another server.
2. What comes in from external networks (`from_upstream`). For instance, you might not trust what's
   coming from an agent network that lives on another server.
3. What goes back to the client (`to_upstream`). For instance, you might not want secrets from
   the server side to be shared with the clients that connect to it.

So by default nothing is shared, and you have to explicitly state what goes through.

Suppose you have an agent network that takes in two numbers,
the name of an operation (say, addition/subtraction/multiplication/division), and asks another
agent network to perform the operation on the numbers. To pass the numbers as `sly_data` to the
downstream agent network you must specify the following in the .hocon file of the agent that
is connecting to the downstream agent network:

```hocon
"allow": {
    "to_downstream": {
        # Specifying this allows specific sly_data
        # keys from this agent network to be sent
        # to downstream agent networks
        "sly_data": ["x", "y"]
   }
}
```

To get `sly_data` coming back from a downstream agent network, i.e., to get the result of
adding two numbers, you must specify the following in the .hocon file of the agent that is
connecting to the downstream agent network:

```hocon
"allow": {
    "from_downstream": {
        # Specifying this allows specific sly_data
        # keys to be ingested from downstream agent
        # networks as sly_data for this agent network
        "sly_data": ["equals"]
    }
}
```

To allow frontman agent to return `sly_data` to the client, you must specify the following in
the .hocon file of the frontman (the only agent that is connected to the client):

```hocon
"allow": {
    "to_upstream": {
        # Specifying this allows sly_data keys
        # from this network to be passed back
        # to the calling client
        "sly_data": ["equals"]
    }
}
```

All the above .hocon "allow" blocks can be combined in a single "allow" block. An example
is given in here [math_guy_passthrough.hocon](
    https://github.com/cognizant-ai-lab/neuro-san/blob/main/neuro_san/registries/math_guy_passthrough.hocon#L54)

For a full reference, please check the [neuro-san documentation](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/agent_hocon_reference.md#allow)

## Toolbox

The **Toolbox** is a flexible and extensible system for managing tools that can be used by agents. It simplifies the
integration of **LangChain** and **custom-coded tools** in a agent network configuration.

### Default tools in toolbox

#### Langchain tools in toolbox

| Name               | Description                                           |
| ------------------ | ----------------------------------------------------- |
| `tavily_search`    | Web search via Tavily. |
| `requests_get`     | HTTP GET requests.                                    |
| `requests_post`    | HTTP POST requests.                                   |
| `requests_patch`   | HTTP PATCH requests.                                  |
| `requests_put`     | HTTP PUT requests.                                    |
| `requests_delete`  | HTTP DELETE requests.                                 |
| `requests_toolkit` | Bundle of all above request tools.                    |

#### Coded tools in toolbox

| Name             | Description                                                    |
| ---------------- | -------------------------------------------------------------- |
| `website_search` | Searches the internet via DuckDuckGo. |
| `rag_retriever`  | Performs RAG (retrieval-augmented generation) from given URLs. |

### Usage in agent network config

To use tools from toolbox in your agent network, simply call them with field `toolbox`:

```json
    {
        "name": "name_of_the_agent",
        "toolbox": "name_of_the_tool_from_toolbox"
    }
```

### Adding tools in toolbox

1. Create the toolbox configuration file. This can be either HOCON or JSON files.
2. Define the tools
   * langchain tools
       * Each tool or toolkit must have a `class` key.
       * The specified class must be available in the server's `PYTHONPATH`.
       * Additional dependencies (outside of `langchain_community`) must be installed separately.

        Example:

        ```hocon
            "tavily_search": {
                # Fully qualified class path of the tool to be instantiated.
                "class": "langchain_community.tools.tavily_search.TavilySearchResults",

                # (Optional) URL for reference documentation about this tool.
                "base_tool_info_url": "https://python.langchain.com/docs/integrations/tools/tavily_search/",

                # Arguments for the tool's constructor.
                "args": {
                    "api_wrapper": {
                        # If the argument should be instantiated as a class, specify it using the "class" key.
                        # This tells the system to create an instance of the provided class instead of passing it as-is.
                        "class": "langchain_community.utilities.tavily_search.TavilySearchAPIWrapper"
                    },
                }
            }
        ```

   * coded tools
       * Similar to how one can define it in agent network config file
       * `description` let the agent know what the tool does.
       * `parameters` are arguments' definitions and types. This is optional.
       * `class` specifies the tool's implementation as **module.ClassName** where the module can be found in `AGENT_TOOL_PATH`.

        Example:

        ```json
            "rag_retriever": {
                "class": "rag.Rag",
                "description": "Retrieve information on the given urls",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "urls": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "List of url to retrieve info from"
                        },
                        "query": {
                            "type": "string",
                            "description": "Query for retrieval"
                        }
                    },
                    "required": ["urls", "query"]
                },
            }
        ```

        > Note: if environment variable `AGENT_TOOL_PATH` is not set, it defaults to the `coded_tool/` directory.

3. Make your own toolbox info file available to the agent system in one of the following ways

   * Define the `toolbox_info_file` key in your agent’s HOCON configuration (preferred method)
       > **Note:** The `agent_toolbox_info_file` key has been **deprecated as of version 0.5.46**.  
       > Please use `toolbox_info_file` instead.  
       > `agent_toolbox_info_file` will remain supported until `neuro-san==0.6.0`.
   * Set the `AGENT_TOOLBOX_INFO_FILE` environment variable as a fallback option

For more information on toolbox, please see [Toolbox Info HOCON File Reference](
    https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/toolbox_info_hocon_reference.md) documentation.

## Logging and debugging

1. To debug your code, set up your environment per these [instructions](https://github.com/cognizant-ai-lab/neuro-san-studio).
Furthermore, please install the build requirements in your virtual environment via the following commands:

    ```bash
    . ./venv/bin/activate
    pip install -r requirements-build.txt
    ```

2. Suppose you want to debug the coded tool for `music_nerd_pro` agent network. Add the following lines of code to the
`music_nerd_pro`'s coded tool Python file (E.g., to the first line of `invoke` method in `Accountant` [class](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/coded_tools/music_nerd_pro/accounting.py)

    ```python
    import pytest
    pytest.set_trace()
    ```

3. Start the client and server via `python3 -m run`, select `music_berd_pro` agent network, and ask a question like
`Where was John Lennon born?`. The code execution stops at the line where you added `pytest.set_trace` statement. You
can step through the code, view variable values, etc. by typing commands in the terminal. For all the debugger options,
please refer to pdb [documentation](https://ugoproto.github.io/ugo_py_doc/pdf/Python-Debugger-Cheatsheet.pdf)

The client and server logs will be saved to `logs/nsflow.log` and `logs/server.log` respectively.

## Advanced

* Tools' arguments can be overidden in the agent network config file using the `args` key.

Example:

```hocon
{
    "name": "web_searcher",
    "toolbox": "tavily_search",
    "args": {
                # This will override the number of search results to 3
                "max_results": 3
            }
}
```

### AAOSA

AAOSA stands for **A**daptive **A**gent **O**riented **S**oftware **A**rchitecture.

In this architecture, agents decide if they can answer inquiries or if they need to call other agents to help them.

Reference:
[Iterative Statistical Language Model Generation for Use with an
Agent-Oriented Natural Language Interface](https://citeseerx.ist.psu.edu/document?repid=rep1&type=pdf&doi=3004005f1e736815b367be83f2f90cc0fa9e0411)

<!-- (https://citeseerx.ist.psu.edu/document?repid=rep1&type=pdf&doi=011fb718658d611294613286c0f4b143aed40f43) -->

Look at [../registries/smart_home.hocon](../registries/smart_home.hocon) and in particular:

* aaosa_instructions
* aaosa_call
* aaosa_command

### External Agent Networks

When designing an agent network in a `.hocon` file, it is possible to use other agent networks as tools.
This makes it possible for an agent to delegate a query to another agent network.
This is an elegant way to reuse agent networks and keep them specialized.

If the agent network is hosted on the same server,
it can be referenced by adding a forward-slash `/` in front of the served agent's name.
This is typically the stem of an agent network hocon file in a deployment's registries directory.

Example: `/expedia` to reference an agent network defined in `expedia.hocon`.

An agent provided with `"tools": ["/expedia"]` will be able to call the expedia agent network and delegate
travel inquiries to it.

Furthermore, it is also possible to reference agents on other neuro-san servers by using a URL as a tool reference.

Example: `"tools": ["http://192.168.1.1:8080/expedia"]` will call the expedia agent network hosted on the server
at IP address `192.168.1.1` and port `8080`.

This enables entire ecosystems of agent webs.

Look at [Consumer Decision Assistant](examples/consumer_decision_assistant.md) for an example.

### Memory

TBD

## Connect with other agent frameworks

* MCP: [MCP BMI SSE](./examples/mcp_bmi_sse.md) is an example of an agent network that uses [MCP](https://www.anthropic.com/news/model-context-protocol)
to call an agent that calculates the body mass index (BMI).
* A2A: [A2A research report](./examples/a2a_research_report.md) is an example of an agent network that uses a coded tool
as an A2A client to connect to CrewAI agents running in an A2A server to write a report on a provided topic.
* CrewAI: see the A2A example above.
* Agentforce: [Agentforce](./examples/agentforce.md) is an agent network that delegates queries to a [Salesforce Agentforce](https://www.salesforce.com/agentforce/)
agent to interact with a CRM system.
* Agentspace: [Agentspace_adapter](./examples/agentspace_adapter.md) is an agent network adapter that delegates queries
to a [Google Agentspace](https://cloud.google.com/agentspace/agentspace-enterprise/docs/overview) agent to interact with
different data store connectors on google cloud.
