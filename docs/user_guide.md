# User guide

<!-- TOC -->

- [User guide](#user-guide)
  - [Simple agent network](#simple-agent-network)
  - [Hocon files](#hocon-files)
    - [Import and substitution](#import-and-substitution)
    - [Manifest](#manifest)
    - [Agent network](#agent-network)
      - [Agent specifications](#agent-specifications)
      - [Tool specifications](#tool-specifications)
      - [Middleware specifications](#middleware-specifications)
      - [LLM specifications](#llm-specifications)
  - [LLM configuration](#llm-configuration)
    - [OpenAI](#openai)
    - [AzureOpenAI](#azureopenai)
    - [Anthropic](#anthropic)
    - [Bedrock](#bedrock)
      - [Default Bedrock models](#default-bedrock-models)
    - [Gemini](#gemini)
      - [Gemini with ADC](#gemini-with-adc)
        - [Gemini with ADC Prerequisites](#gemini-with-adc-prerequisites)
        - [Gemini with ADC Configuration](#gemini-with-adc-configuration)
    - [Ollama](#ollama)
      - [Ollama Prerequisites](#ollama-prerequisites)
      - [Ollama Configuration](#ollama-configuration)
      - [Using Ollama in Docker or Remote Server](#using-ollama-in-docker-or-remote-server)
      - [Example agent network](#example-agent-network)
    - [Configuring Default Models with Environment Variables](#configuring-default-models-with-environment-variables)
      - [Using Optional Environment Variable Substitution](#using-optional-environment-variable-substitution)
      - [Setting Your Own Default Model](#setting-your-own-default-model)
      - [Changing the System Default Model](#changing-the-system-default-model)
    - [See also](#see-also)
  - [LLM Fallbacks](#llm-fallbacks)
  - [Reasoning Models](#reasoning-models)
    - [OpenAI and AzureOpenAI Models](#openai-and-azureopenai-models)
    - [Anthropic and Bedrock Models](#anthropic-and-bedrock-models)
    - [Gemini Models](#gemini-models)
      - [Thinking Level](#thinking-level)
      - [Thinking Budget](#thinking-budget)
    - [Ollama Models](#ollama-models)
  - [Using custom or non-default LLMs](#using-custom-or-non-default-llms)
    - [Using the `class` Key](#using-the-class-key)
    - [Extending the default LLM info file](#extending-the-default-llm-info-file)
      - [Registering custom LLM info file](#registering-custom-llm-info-file)
  - [Coded tools](#coded-tools)
    - [Simple tool](#simple-tool)
    - [API calling tool](#api-calling-tool)
    - [Sly data](#sly-data)
  - [Toolbox](#toolbox)
    - [Default tools in toolbox](#default-tools-in-toolbox)
      - [Langchain tools in toolbox](#langchain-tools-in-toolbox)
      - [Coded tools in toolbox](#coded-tools-in-toolbox)
    - [Usage in agent network config](#usage-in-agent-network-config)
    - [Adding tools in toolbox](#adding-tools-in-toolbox)
  - [MCP Servers](#mcp-servers)
    - [MCP Server Configuration](#mcp-server-configuration)
    - [Authentication](#authentication)
  - [Middleware](#middleware)
    - [class](#class)
    - [args](#args)
      - [Special args](#special-args)
    - [Example](#example)
  - [Agent Skills](#agent-skills)
    - [How it works](#how-it-works)
    - [SKILL.md format](#skillmd-format)
    - [Configuration](#configuration)
  - [Logging](#logging)
  - [Debugging](#debugging)
  - [Advanced](#advanced)
    - [AAOSA](#aaosa)
    - [External Agent Networks](#external-agent-networks)
    - [Memory](#memory)
  - [Connect with other agent frameworks](#connect-with-other-agent-frameworks)
  - [Plugins](#plugins)
  - [Test](#test)
    - [Unit test](#unit-test)
    - [Integration Test](#integration-test)
      - [Add test case](#add-test-case)
        - [Automatic generation](#automatic-generation)
        - [Manual creation](#manual-creation)
        - [Register the fixture](#register-the-fixture)
      - [Run test](#run-test)
  - [Improving agent networks](#improving-agent-networks)

<!-- TOC -->

## Simple agent network

The `music_nerd` agent network is the simplest agent network possible: it contains a single agent
that answers questions about music since the 60s. See its description here: [docs/examples/music_nerd.md](examples/basic/music_nerd.md).

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
    "basic/music_nerd.hocon": true,
    # ... other agent networks ... #
}
```

This tells the server to load the `music_nerd.hocon` file from the same `/registries` folder.

Setting the value to `false` would make the server ignore this agent network.

Open [../registries/basic/music_nerd.hocon](../registries/basic/music_nerd.hocon) and have a look at it.
For now just note that it contains:

- an `llm_config` section that specifies which LLM to use by default for the agents in this file
- a `tools` section that contains a single agent, the "frontman", called `MusicNerd`

Read the instructions of the agent to see what it does.
Feel free to modify the instructions to see how it affects the agent's behavior.
See if you can make it a soccer expert for instance!

We'll describe the structure of agent networks' `.hocon` files in next section.

## Hocon files

### Import and substitution

HOCON files support importing content from other HOCON files using the unquoted keyword `include`, followed by
whitespace and the path to the imported file as a quoted string:

```hocon
include "registries/aaosa.hocon"
```

> **Note**: The file path in include should be an **absolute path**
> or relative to the **root folder** to ensure it can be resolved correctly.

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

You can also substitute environment variables:

```hocon
"api_key": ${API_KEY}
"database_url": ${DATABASE_URL}
```

For optional substitutions, use `${?...}` syntax. If the value is not found, the entire line will be ignored rather
than causing an error:

```hocon
"optional_setting": ${?OPTIONAL_CONFIG}
"feature_flag": ${?ENABLE_FEATURE}
```

Note that substitutions are **not parsed inside quoted strings**. If you need to include a substitution within a string,
you can quote only the non-substituted parts:

```hocon
"instructions": ${instruction_prefix} "main instruction" ${instruction_suffix}
```

Also not that if you're using json notation you need to put the include with the curly braces:

```hocon
{
    include "registries/aaosa.hocon"

    ...
            "function": ${aaosa_call}
    ...
}
```

You can see working examples here:
- Using json notation: [registries/basic/smart_home.hocon](../registries/basic/smart_home.hocon)
- Using hocon notation: [registries/basic/coffee_finder.hocon](../registries/basic/coffee_finder.hocon)

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
| middleware   | Optional list of AgentMiddleware instances to apply during agent execution. Order of appearance matters. See [Middleware](#middleware) for more details. |
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

#### Middleware specifications

<!-- pyml disable line-length -->
| **Field** | **Description**                                                                                                                                                                  |
|-----------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| class     | Fully-qualified class name of the `AgentMiddleware` to instantiate (e.g. `langchain.agents.middleware.PIIMiddleware`). Only class-based middleware is supported.    |
| args      | Optional dictionary of keyword arguments passed to the middleware class constructor. Keys are argument names, values are argument values. See [Middleware](#middleware) for special framework-populated args (`origin`, `origin_str`, `sly_data`). |
<!-- pyml enable line-length -->

#### LLM specifications

<!-- pyml disable line-length -->
| **Field**   | **Description**                                                                                                                                |
|-------------|------------------------------------------------------------------------------------------------------------------------------------------------|
| model_name  | Name of the model to use (i.e. “gpt-4o”, “claude-3-haiku”).                                                                                    |
| class       | Optional key for using custom models or providers. See [Using Custom or Non-Default LLMs](#using-custom-or-non-default-llms) for more details. |
| temperature | Optional parameter controlling response randomness. Higher values increase variability; lower values make outputs more deterministic. Valid range depends on the provider.                                                                                  |
<!-- pyml enable line-length -->

See next section for more information about how to specify the LLM(s) to use.

For a full description of the fields, please refer to the [Agent Network HOCON File Reference](
    https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/agent_hocon_reference.md) documentation.

## LLM configuration

The `llm_config` section in the agent network configuration file defines which LLM should be used by the agents.

You can specify it at two levels:
- **Network-level**: Applies to all agents in the file.
- **Agent-level**: Overrides the network-level configuration for a specific agent.

Neuro-SAN includes several predefined LLM providers and models. To use one of these, set the `model_name` key to
the name of the model you want. In addition, model-specific parameters (such as `temperature`, `max_tokens`, etc.)
can be set alongside `model_name`.
A full list of available models and parameters can be found in the
[default LLM info file](https://github.com/cognizant-ai-lab/neuro-san/blob/main/neuro_san/internals/run_context/langchain/llms/default_llm_info.hocon).

> - If `model_name` is not provided, the default `gpt-5.2` will be used.
> See [GPT-5.2 model documentation](https://developers.openai.com/api/docs/models/gpt-5.2) for supported parameters.
> - ⚠️ Different providers may require unique configurations or environment variables.

The following sections provide details for each supported provider, including required parameters and setup instructions.

### OpenAI

To use an OpenAI LLM, set the `OPENAI_API_KEY` environment variable to your OpenAI API key
and specify which model to use in the `model_name` field:

```hocon
    "llm_config": {
        "model_name": "gpt-4o",
    }
```

See [./examples/music_nerd.md](examples/basic/music_nerd.md) for an example.

### AzureOpenAI

To create an Azure OpenAI resource

- Go to Azure [portal](https://portal.azure.com/)
- Click on `Create a resource`
- Search for `Azure OpenAI`
- Select `Azure OpenAI`, then click Create  

After your Azure OpenAI resource is created, you must deploy a model

- Go to Azure [portal](https://portal.azure.com/)
- Under `Resources`, select your Azure OpenAI resource
- Click on `Go to Azure AI Foundry portal`
- Click on `Create new deployment`
- Choose a model (e.g., `gpt-4o`), then pick a deployment name (e.g., `my-gpt4o`), and click `Deploy`
- Find the `api_version` on the deployed model page (e.g., "2024-12-01-preview")
- Optionally, set environment variables to the value of the deployment name and API version

    export AZURE_OPENAI_DEPLOYMENT_NAME="Your deployment name"\
    export OPENAI_API_VERSION="Your OpenAI API version"

Finally, get your API key and endpoint

- Go to Azure [portal](https://portal.azure.com/)
- Under `Resources`, select your Azure OpenAI resource
- Click on `Click here to view endpoints`
- Optionally, set environment variables to the value of the API key and the endpoint

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

   - `AWS_ACCESS_KEY_ID`

   - `AWS_SECRET_ACCESS_KEY`

   - `AWS_REGION` or `AWS_DEFAULT_REGION`

    > Note: You may set `region_name` in the `llm_config` of the agent network HOCON file instead

    This is sufficient if you only have **one AWS profile** or if you're certain these environment variables
    correspond to the correct credentials.

2. Named profile (**required for multiple profiles**)

    If you have **multiple profiles** in `~/.aws/credentials` or `~/.aws/config`, it's recommended to explicitly set
    the credentials_profile_name field to avoid ambiguity. This tells the system exactly which profile to use,
    even if other credentials are present in the environment.

    If `credentials_profile_name` is not specified in the `llm_config` of the HOCON file:

   - The default profile will be used.

   - On EC2 instance, credentials may be automatically loaded from the Instance Metadata Service (IMDS).

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

- `bedrock-us-claude-opus-4`

- `bedrock-us-claude-sonnet-4`

- `bedrock-us-claude-3-7-sonnet`

These models require access to one of the following AWS regions:

- `us-east-1`

- `us-east-2`

- `us-west-2`

If these are not available in your account, you can still use other Bedrock models available to you by
[using the class key](#using-the-class-key).

To find which models are available in your region, refer to the official AWS documentation:
[Supported models – Amazon Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html)

### Gemini

To use Gemini models, set the `GOOGLE_API_KEY` environment variable to your Google Gemini API key
and specify which model to use in the `model_name` field of the `llm_config` section of an agent network hocon file:

```hocon
    "llm_config": {
        "model_name": "gemini-3-flash",
        "temperature": 1.0
    }
```

> ⚠️ For Gemini 3.0+ models, it is recommended to set `temperature` to `1.0`. Using `0.7` may lead to infinite loops,
degraded reasoning performance, and failures on complex tasks. Therefore, this value should be explicitly set to avoid
falling back to the default of `0.7`.

You can get a Google Gemini API [key](https://ai.google.dev/gemini-api/docs/api-key) here.

#### Gemini with ADC

If you are running in a **Google Cloud environment** (GCP VM, Cloud Run, GKE, etc.) or prefer to authenticate
using your organization's GCP identity — without a personal API key — you can use
**Application Default Credentials (ADC)**.

ADC is Google's standard credential resolution mechanism. It automatically picks up credentials from:
- `gcloud auth application-default login` (local development)
- Attached service accounts (Cloud Run, GKE, Compute Engine)
- Workload Identity Federation

This approach is recommended for **enterprise and on-prem-to-cloud** deployments where managing individual
API keys is not desirable or permitted.

> An example implementation of Gemini with ADC can be found in the
> [neuro-san-gemini-example](https://github.com/subhadeep-banerjee/neuro-san-gemini-example) repository.

##### Gemini with ADC Prerequisites

1. Install the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) (`gcloud`).

2. Authenticate your local environment with ADC:

    ```bash
    gcloud auth application-default login
    ```

3. Install the required package (already included in `requirements.txt`):

    ```bash
    pip install langchain-google-vertexai
    ```

4. Set the following environment variables (or add them to your `.env` file):

    ```bash
    GCP_PROJECT_ID=your-gcp-project-id
    GCP_REGION=your-vertex-ai-region   # e.g. us-central1, europe-west4, asia-south1
    ```

##### Gemini with ADC Configuration

Because ADC-based Vertex AI access requires the `project` and `location` fields — which are not part of
Neuro-SAN's default Gemini model definitions — you must use the `class` key to instantiate
`ChatVertexAI` directly in your `llm_config`:

```hocon
llm_config: {
    class: "langchain_google_vertexai.chat_models.ChatVertexAI"
    model_name: "gemini-2.5-flash"   # configurable: any Vertex AI Gemini model (e.g. "gemini-2.0-flash", "gemini-1.5-pro")
    temperature: 0.2                 # configurable: 0.0 (deterministic) to 1.0 (creative); use 1.0 for Gemini 3.0+ models
    max_tokens: 2048                 # configurable: maximum number of tokens in the model's response
    project: ${GCP_PROJECT_ID}
    location: ${GCP_REGION}
}
```

The `project` and `location` values are read from environment variables at startup via HOCON substitution.
No API key is required — authentication is handled transparently by Google's ADC library.

> ⚠️ Do **not** set `GOOGLE_API_KEY` when using ADC. The two authentication paths are mutually exclusive.
> If `GOOGLE_API_KEY` is present in the environment, it may take precedence and cause unexpected errors.

<!-- -->

> **Tip**: To centralize the LLM configuration and reuse it across multiple agent networks, define it in a
> separate file (e.g. `registries/llm_config.hocon`) and include it in your agent network HOCON files:
>
> ```hocon
> include "registries/llm_config.hocon"
> ```

For more information on Vertex AI authentication and available models, see the
[Vertex AI documentation](https://cloud.google.com/vertex-ai/docs/authentication) and the
[LangChain ChatVertexAI reference](https://python.langchain.com/docs/integrations/chat/google_vertex_ai_palm/).

### Ollama

This guide walks you through how to use a locally running LLM via [Ollama](https://github.com/ollama/ollama) in neuro-san.

#### Ollama Prerequisites

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

#### Ollama Configuration

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

<!-- pyml disable line-length -->
Note that if your ollama model is not listed in [default_LLM_info.hocon file](https://github.com/cognizant-ai-lab/neuro-san/blob/main/neuro_san/internals/run_context/langchain/llms/default_llm_info.hocon#L1005) it might throw an 404 error, in which case explicitly adding the class should help.
<!-- pyml enable line-length -->

```hocon
    "llm_config": {
            "class" : "ollama",
            "model_name": "llama3.1:8b",
        }
```

For more information about using unlisted ollama models with neuro-san, please refer to the [agent hocon reference](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/agent_hocon_reference.md#model_name).

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

- Local (default): omit `base_url` or use `http://127.0.0.1:11434`

- Remote VM: `http://192.168.1.10:11434`

- Public DNS: `http://example.com:11434`

- Docker Compose: `http://<container name>:11434` (ensure port `11434` is exposed)

Note:

- `base_url` **must starts** with `http://` or `https://`, otherwise the server defaults to `http://localhost:11434`.

- if the port is omitted:

    - `http` → port 80

    - `https` → port 443

You can also set the environment variable `OLLAMA_HOST`, but `base_url` takes precedence.

For more information on logic of parsing the `base_url`
see [Ollama python SDK](https://github.com/ollama/ollama-python/blob/main/ollama/_client.py#L1274)

#### Example agent network

See the [./examples/music_nerd_pro_local.md](examples/basic/music_nerd_pro_local.md) for a complete working example.

For more information about how to use Ollama with LangChain,
see [this page](https://python.langchain.com/docs/integrations/chat/ollama/)

### Configuring Default Models with Environment Variables

You can easily switch LLM models across all agent networks that share the same configuration by
using environment variable substitution in your HOCON files.

#### Using Optional Environment Variable Substitution

In your agent network's `llm_config`, use the `${?MODEL_NAME}` syntax to allow overriding the
model via an environment variable:

```hocon
"llm_config": {
    "model_name": ${?MODEL_NAME}
}
```

If the `MODEL_NAME` environment variable is not set, this will default to `gpt-5.2` (the system default).

#### Setting Your Own Default Model

To specify a custom default model that will be used when the environment variable is not set,
define `model_name` twice:

```hocon
"llm_config": {
    "model_name": "claude-3-7-sonnet",
    "model_name": ${?MODEL_NAME}
}
```

In this example:
- If `MODEL_NAME` is set, it will use that model
- If `MODEL_NAME` is not set, it will use `claude-3-7-sonnet`

#### Changing the System Default Model

Alternatively, you can change the system-wide default model used by Neuro-SAN by modifying the `default_model_name`
value in the
<!-- pyml disable line-length -->
[default LLM info file](https://github.com/cognizant-ai-lab/neuro-san/blob/main/neuro_san/internals/run_context/langchain/llms/default_llm_info.hocon#L1005).
<!-- pyml enable line-length -->

> **Tip**: Using environment variable substitution is particularly useful when you want to quickly test different
models across multiple agent networks without modifying each configuration file individually.
Simply set the `MODEL_NAME` environment variable before starting the server:
>
> ```bash
> export MODEL_NAME="claude-3-7-sonnet"
> python -m run
> ```

### See also

For a full description of `llm_config`, please refer to the [LLM config](
    https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/agent_hocon_reference.md#llm_config) documentation.

## LLM Fallbacks

Neuro-SAN supports LLM fallbacks, which allow you to specify a list of LLMs to use in case the primary LLM fails.
In the `llm_config` block, put each LLM configuration in a `fallbacks` list.
The list of LLM configs is tried in order until one succeeds.

In this example, as seen in [./examples/music_nerd_llm_fallbacks.md](examples/basic/music_nerd_llm_fallbacks.md),
the agent network will use OpenAI's `gpt-5.2` model first,
and if that fails (for example, due to rate limits or service outages),
it will automatically fall back to Anthropic's `claude-3-7-sonnet` model:

```hocon
    "llm_config": {
        "fallbacks": [
            {
                # Try OpenAI first
                "model_name": "gpt-5.2",
            },
            {
                # Fall back to Anthropic Claude if OpenAI is unavailable.
                "model_name": "claude-3-7-sonnet",
            }
        ]
    },
```

## Reasoning Models

Some LLM providers offer reasoning models where reasoning or thinking behavior can be
toggled or adjusted in the `llm_config` section of your agent network HOCON file.

### OpenAI and AzureOpenAI Models

You can control the reasoning depth using the `reasoning_effort` field with one of the following values:
`minimal`, `low`, `medium`, or `high`.

> Note that `minimal` is only supported for `gpt-5` variants.

You can also control output detail using the `verbosity` field with one of the following values:
`low`, `medium`, or `high`.

Example:

```hocon
    "llm_config": {
        "model_name": "gpt-5",
        "reasoning_effort": "low",
        "verbosity": "low"
    }
```

For more detail, see [LangChain ChatOpenAI documentation](https://reference.langchain.com/python/integrations/langchain_openai/ChatOpenAI/#langchain_openai.chat_models.ChatOpenAI.reasoning_effort).

### Anthropic and Bedrock Models

Claude models support extended thinking, which allows them to use additional tokens for internal reasoning
before generating a final answer.
This improves performance on complex tasks and can provide insight into the model’s reasoning process.

For Anthropic models, extended thinking is configured with the `thinking` field.

Example:

```hocon
    "llm_config": {
        "model_name": "claude-3-7-sonnet-20250219",
        "thinking": {"type": "enabled", "budget_tokens": 10000}
    }
```

> Ensure that budget_tokens is at least **1024** and less than the model’s maximum token limit.

**Supported models for extended thinking:**

- Claude Sonnet 4.5 (`claude-sonnet-4-5-20250929`)
- Claude Sonnet 4 (`claude-sonnet-4-20250514`)
- Claude Sonnet 3.7 (`claude-3-7-sonnet-20250219`)
- Claude Haiku 4.5 (`claude-haiku-4-5-20251001`)
- Claude Opus 4.1 (`claude-opus-4-1-20250805`)
- Claude Opus 4 (`claude-opus-4-20250514`)

These same models can also be accessed via AWS Bedrock. In that case, extended thinking is configured under `model_kwargs`.

Example:

```hocon
    "llm_config": {
        "model_name": "bedrock-us-claude-3-7-sonnet",
        "credentials_profile_name": "<profile_name>",
        "region_name": "us-west-2",
        "model_kwargs": {
            "thinking": {"type": "enabled", "budget_tokens": 1024}
        }
    }
```

See
[Langchain ChatAnthropic documentation](https://reference.langchain.com/python/integrations/langchain_anthropic/ChatAnthropic/?h=chat#langchain_anthropic.chat_models.ChatAnthropic.thinking)
for more information.

### Gemini Models

Some Gemini models support configurable thinking depth. Depending on the model version, this can be controlled using
`thinking_level` (Gemini 3+) or `thinking_budget` (Gemini 2.5).

#### Thinking Level

For Gemini 3+ models, use `thinking_level` to control reasoning depth.

| Value | Models | Description |
|-------|--------|-------------|
| `minimal` | Flash | Matches the "no thinking" setting for most queries |
| `low` | Flash, Pro | Minimizes latency and cost |
| `medium` | Flash | Balances latency/cost with reasoning depth |
| `high` | Flash, Pro | Maximizes reasoning depth (default) |

> Note that minimal does not guarantee that thinking is off.

#### Thinking Budget

For Gemini 2.5 models, use thinking_budget (an integer token count)

- Set to `0` to disable thinking (where supported)
- Set to `-1` for dynamic thinking (model decides)
- Set to a positive integer to constrain token usage

Example:

```hocon
    "llm_config": {
        "model_name": "gemini-3-flash",
        "temperature": 1.0,
        "thinking_level": "minimal"
    }
```

For more details, see the
[documentation](https://docs.langchain.com/oss/python/integrations/chat/google_generative_ai#thinking-support)

### Ollama Models

For Ollama’s [supported reasoning models](https://ollama.com/search?c=thinking),
you can control reasoning behavior using the `reasoning` field with one of the follwing values:

- `true`: Enables reasoning mode.
- `false`: Disables reasoning mode.
- `null` (default): Uses the model’s default reasoning behavior.
- `low`, `medium`, `high`. Enables reasoning with a custom intensity level. Currently, this is only supported `gpt-oss`.

Example:

```hocon
    "llm_config": {
        "model_name": "qwen3:8b",
        "reasoning": true
    }
```

For more information, see
[Langchain ChatOllama documentation](https://reference.langchain.com/python/integrations/langchain_ollama/#langchain_ollama.ChatOllama.reasoning).

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
    | Azure OpenAI  | `azure-openai`  |
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

- Adding model and class in llm info file

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

- Implementing a custom factory

    You’ll need to implement a factory class that matches the path you specified in `factories`.

    - Your factory must subclass [`LangChainLlmFactory`](https://github.com/cognizant-ai-lab/neuro-san/blob/main/neuro_san/internals/run_context/langchain/llms/langchain_llm_factory.py)
    - It must implement a `create_base_chat_model(config, callbacks)` method
        - `config` will contain:
            - `model_name`
            - `class` (e.g. `groq`)
            - Parameters defined under `classes.groq
        `callbacks` is typically used for token counting

    <!-- markdownlint-disable MD013 -->
    See
    [`StandardLangChainLlmFactory`](https://github.com/cognizant-ai-lab/neuro-san/blob/main/neuro_san/internals/run_context/langchain/llms/standard_langchain_llm_factory.py)
    as a reference implementation.
    <!-- markdownlint-enable MD013 -->

#### Registering custom LLM info file

To load your own llm info file, you can specify its location using one of the following methods:

- The `llm_info_file` key in your agent’s HOCON configuration
- The `AGENT_LLM_INFO_FILE` environment variable (fallback if the above is not set)

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
| `requests_get`     | HTTP GET requests.                                    |
| `requests_post`    | HTTP POST requests.                                   |
| `requests_patch`   | HTTP PATCH requests.                                  |
| `requests_put`     | HTTP PUT requests.                                    |
| `requests_delete`  | HTTP DELETE requests.                                 |
| `requests_toolkit` | Bundle of all above request tools.                    |

#### Coded tools in toolbox

| Name             | Description                                                    |
| ---------------- | -------------------------------------------------------------- |
| `get_current_date_time` | Get current date and time for a specified timezone.     |

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
   - langchain tools
       - Each tool or toolkit must have a `class` key.
       - The specified class must be available in the server's `PYTHONPATH`.
       - Additional dependencies (outside of `langchain_community`) must be installed separately.

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

   - coded tools
       - Similar to how one can define it in agent network config file
       - `description` let the agent know what the tool does.
       - `parameters` are arguments' definitions and types. This is optional.
       - `class` specifies the tool's implementation as **module.ClassName** where the module can be found in `AGENT_TOOL_PATH`.

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

   - Define the `toolbox_info_file` key in your agent’s HOCON configuration
   - Set the `AGENT_TOOLBOX_INFO_FILE` environment variable as a fallback option

For more information on toolbox, please see [Toolbox Info HOCON File Reference](
    https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/toolbox_info_hocon_reference.md) documentation.

## MCP Servers

Agents can invoke tools exposed by remote **Model Context Protocol (MCP)** servers.
URLs must either:
- start with `https://mcp`, **or**
- end with `/mcp`.

### MCP Server Configuration

MCP servers can be configured in one of two formats under the `tools` field.

1. String Reference

    Use this format when you want to expose **all tools** from an MCP server and do not need inline tool filtering.

    ```json
    "tools": ["https://example.com/mcp"]
    ```

   - All tools exposed by the MCP server will be available to the agent.
   - Tool filtering is not supported in this format unless it is provided via the
    `MCP_SERVERS_INFO_FILE` environment variable (see Authentication & Configuration below).

2. Dictionary Reference

    Use this format when you want to explicitly control which tools are exposed from a given MCP server.

    ```json
    "tools": [
        {
            "url": "https://example.com/mcp",
            "tools": ["tool_1"]
        }
    ]
    ```

   - The tools key specifies a whitelist of tools made available to the agent.
   - If the tools key is omitted, all tools from the MCP server will be accessible.

### Authentication

MCP servers may require authentication. Authentication and optional tool filtering can be configured using one of the
following methods.

1. http_headers in sly_data

    Authentication headers can be provided directly in sly_data.
    Each MCP server URL can have its own set of headers, depending on the authentication scheme it requires.

    ```json
    {
        "http_headers": {
            "<MCP_URL_1>": {
                "Authorization": "Bearer <token_value>"
            },
            "<MCP_URL_2>": {
                "client_id": "<client_id_value>",
                "client_secret": "<client_secret_value>"
            }
        }
    }
    ```

   - The exact header fields depend on the authentication mechanism implemented by the MCP server.
   - This method supports per-server credentials.

2. `MCP_SERVERS_INFO_FILE` Environment Variable

    Alternatively, you can set the `MCP_SERVERS_INFO_FILE` environment variable to point to a HOCON file
    that defines MCP server configuration, including authentication headers and optional tool filtering.

    ```json
    {
    "https://example.com/mcp": {
        http_headers: {
            Authorization: "Bearer <token>"
        },
        tools: ["tool_1", "tool_2"]
    }
    }
    ```

   - MCP server URLs in this file must exactly match those referenced in the agent network HOCON file.
   - If authentication headers are defined in both sly_data, and `MCP_SERVERS_INFO_FILE` then sly_data takes precedence.
   - Tool filtering from `MCP_SERVERS_INFO_FILE` is applied only if no tool filtering is defined
    directly in the agent network HOCON configuration.
   - For example, see [mcp_info.hocon](../mcp/mcp_info.hocon)

## Middleware

Middleware allows custom code to be injected at key points during agent execution — before or after the agent runs,
and before or after each LLM call. This makes it possible to inspect, modify, or intercept data flowing through
an agent without changing the agent's core logic.

Middleware is configured per agent using the optional `middleware` key in an agent's specification.
The value is a list of dictionaries, each describing one `AgentMiddleware` instance to apply.
When multiple middleware are listed, order of appearance matters — they are applied in sequence.

For an overview of middleware, see the [Overview](https://docs.langchain.com/oss/python/langchain/middleware/overview).

For a working example, see [pii_middleware.hocon](../registries/basic/pii_middleware.hocon).

### class

_Required._ The fully-qualified class name of the `AgentMiddleware` to instantiate. For example:

```hocon
"class": "langchain.agents.middleware.PIIMiddleware"
```

An `AgentMiddleware` can hook into the following points of agent execution (asynchronous variants are preferred
in the Neuro SAN server environment):

- `abefore_agent()` — called before the agent execution starts
- `aafter_agent()` — called after the agent execution completes
- `abefore_model()` — called before each LLM call
- `aafter_model()` — called after each LLM call
- `awrap_model_call()` - intercept and control async model execution via handler callback
- `awrap_tool_call()` - intercept and control async tool execution via handler callback

Only class-based middleware is supported (not annotation-based). See
[AgentMiddleware](https://docs.langchain.com/oss/python/langchain/middleware/custom#class-based-middleware)
for details on how to implement one.

### args

A dictionary of keyword arguments passed to the middleware class constructor. Keys are argument names and
values are argument values, matching the constructor signature of the class being instantiated. For example:

```hocon
"args": {
    "pii_type": "phone_number",
    "detector": "[a-zA-Z0-9]{3}-[a-zA-Z0-9]{4}",
    "strategy": "redact",
    "apply_to_output": true
}
```

#### Special args

The following argument names are recognized by the agent framework and automatically populated if they appear
in both the middleware dictionary and the class constructor signature:

- **`origin`** — a list of dictionaries describing where in the agent network hierarchy this middleware
  was instantiated.
- **`origin_str`** — a simpler string representation of `origin`.
- **`sly_data`** — the agent's `sly_data` dictionary, shared across all middleware and coded tools for
  the current request. See [Sly data](#sly-data) for more information.

### Example

The following example shows a `prankster` agent that uses `PIIMiddleware` to detect and redact phone numbers
from both inputs and outputs:

```hocon
{
    "name": "prankster",
    "function": {
        "description": "Send me a phone number and I will leave a message on its voicemail for you.",
        "parameters": {
            "phone_number": {
                "type": "string",
                "description": "The phone number to send the message to."
            },
            "message": {
                "type": "string",
                "description": "The message to send to the phone number."
            }
        }
    },
    "instructions": "You are an impotent wannabe prank caller. ...",
    "tools": [],
    "middleware": [
        {
            "class": "langchain.agents.middleware.PIIMiddleware",
            "args": {
                "pii_type": "phone_number",
                "detector": "[a-zA-Z0-9]{3}-[a-zA-Z0-9]{4}",
                "strategy": "redact",
                "apply_to_output": true
            }
        }
    ]
}
```

See [pii_middleware.hocon](../registries/basic/pii_middleware.hocon) for the full working network.

## Agent Skills

[Agent Skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) are supported
using a middleware implementation. `AgentSkillsMiddleware` is a built-in middleware that implements the
[Agent Skills specification](https://agentskills.io/specification). It gives an agent access to
a library of **skills** — structured, reusable instruction sets stored as `SKILL.md` files — without
loading their full content into the prompt upfront.

### How it works

The middleware uses a **progressive disclosure** pattern to keep token usage low:

1. **At startup** (`abefore_agent`): scans all configured skill sources, parses the YAML
   frontmatter (name, description) from each `SKILL.md`, and caches the full file content, but
   only injects the parsed metadata into the system prompt.
2. **Before each model call** (`awrap_model_call`): injects a compact list of available skills into
   the system prompt so the agent knows what is available.
3. **On demand**: when the agent decides a skill is relevant, it calls one of three tools registered
   by the middleware to load the full content:

| Tool | Description |
|------|-------------|
| `get_full_skill_content` | Loads the complete `SKILL.md` for a named skill |
| `load_skill_resource_local` | Loads an additional file from a local skill directory |
| `load_skill_resource_remote` | Loads an additional file from a remote skill URL |

> **Security**: All three tools attempt to restrict file and URL access to paths that fall under
> the configured `skill_sources` entries. This helps reduce the risk of SSRF and data
> exfiltration attacks, but should not be relied on as a complete security boundary.

### SKILL.md format

Each skill directory must contain a `SKILL.md` file with a YAML frontmatter block followed by the
skill's full instructions. The frontmatter must include at minimum `name` and `description`:

```markdown
---
name: internal-comms
description: Helps write internal communications such as newsletters and FAQs.
allowed-tools: web_search
compatibility: general
license: Apache-2.0
---

# Internal Communications Skill

... full instructions here ...
```

Frontmatter constraints (per the [Agent Skills spec](https://agentskills.io/specification)):

- `name`: required, 1–64 characters, lowercase alphanumeric and hyphens only, no leading/trailing or consecutive hyphens
- `description`: required, max 1024 characters
- `allowed-tools`: optional, space-delimited or YAML list of recommended tool names
- `compatibility`, `license`: optional free-text fields

### Configuration

Configure `AgentSkillsMiddleware` in the agent's `middleware` list:

```hocon
"middleware": [
    {
        "class": "middleware.agent_skills_middleware.AgentSkillsMiddleware",
        "args": {
            "skill_sources": ["skills/my-skill/"],
            "keep_skill_in_context": false,
            "http_timeout": 30.0
        }
    }
]
```

- `skill_sources` accepts a list of local paths or remote URLs. Each entry must point to a directory
containing a `SKILL.md` file. You can mix local and remote sources in the same list.

    > ⚠️ **Security note**: Be cautious when using skills from the internet. Always review skill
    > contents carefully before use — they may contain malicious scripts or reference tools or
    > resources unavailable in your environment.

<!-- pyml disable line-length -->
- `keep_skill_in_context` argument controls whether full skill content stays in the conversation
history after being loaded:

    | Value | Behaviour | Best for |
    |-------|-----------|----------|
    | `false` (default) | Skill content removed from chat history after use; agent may re-load if needed | Most use cases; token-constrained environments |
    | `true` | Skill content stays in chat history; agent can reference multiple skills simultaneously | Complex tasks requiring cross-skill synthesis |

<!-- pyml enable line-length -->

- `http_timeout` indicates timeout in seconds for HTTP requests. Only used for remote skills.

For working examples, see:
- [job_guessing_skill.hocon](../registries/basic/job_guessing_skill.hocon) — local skill source
- [internal_communication_skill.hocon](../registries/basic/internal_communication_skill.hocon)

## Logging

The client and server logs will be saved to `logs/nsflow.log` and `logs/server.log` respectively.

Note:
- All console logs are color-coded and pretty-formatted using the rich based log bridge plugin.
- Enable or disable rich logs via setting an env variable `LOGBRIDGE_ENABLED` on terminal or in your .env file.
  By default the value is set to `true`.
- Any updates to console logs can be managed via this plugin at `plugins/log_bridge/`.
- Use the `log_cfg` dict located at `plugins/log_bridge/process_log_bridge.py` to configure the formatting of logs.

## Debugging

1. To debug your code, set up your environment per these [instructions](https://github.com/cognizant-ai-lab/neuro-san-studio).
Furthermore, please install the build requirements in your virtual environment via the following commands:

    ```bash
    . ./venv/bin/activate
    pip install -r requirements-build.txt
    ```

2. Suppose you want to debug the coded tool for `music_nerd_pro` agent network. Add the following lines of code to the
`music_nerd_pro`'s coded tool Python file (E.g., to the first line of `invoke` method in `Accountant` [class](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/coded_tools/basic/accountant.py)

    ```python
    import pytest
    pytest.set_trace()
    ```

3. Start the client and server via `python3 -m run`, select `music_nerd_pro` agent network, and ask a question like
`Where was John Lennon born?`. The code execution stops at the line where you added `pytest.set_trace` statement. You
can step through the code, view variable values, etc. by typing commands in the terminal. For all the debugger options,
please refer to pdb [documentation](https://docs.python.org/3/library/pdb.html)

## Advanced

- Tools' arguments can be overidden in the agent network config file using the `args` key.

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

Look at [../registries/basic/smart_home.hocon](../registries/basic/smart_home.hocon) and in particular:

- aaosa_instructions
- aaosa_call
- aaosa_command

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

Look at [Consumer Decision Assistant](examples/industry/consumer_decision_assistant.md) for an example.

### Memory

TBD

## Connect with other agent frameworks

- MCP: [MCP BMI SSE](./examples/tools/mcp_bmi_streamable_http.md) is an example of an agent network that uses [MCP](https://www.anthropic.com/news/model-context-protocol)
to call an agent that calculates the body mass index (BMI).
- A2A: [A2A research report](./examples/tools/a2a_research_report.md) is an example of an agent network that uses
a coded tool as an A2A client to connect to CrewAI agents running in an A2A server to write a report on a provided topic.
- CrewAI: see the A2A example above.
- Agentforce: [Agentforce](./examples/tools/agentforce.md) is an agent network that delegates queries to a [Salesforce Agentforce](https://www.salesforce.com/agentforce/)
agent to interact with a CRM system.
- Agentspace: [Agentspace_adapter](./examples/tools/agentspace_adapter.md) is an agent network adapter that delegates queries
to a [Google Agentspace](https://docs.cloud.google.com/gemini/enterprise/docs/agents-overview) agent to interact with
different data store connectors on google cloud.

## Plugins

Plugins are a way to extend the functionality of a Neuro SAN server largely for
deployment-related use-cases. Note that plugins are never required for Neuro SAN to function.
See [Plugins](./plugins.md) for more information.

## Test

### Unit test

To run the unit test, use the following command:

```bash
make test
```

or

```bash
python -m pytest tests/ -v --cov=coded_tools,run.py -m "not integration"
```

### Integration Test

#### Add test case

Integration tests are data-driven: each test case is a single HOCON file under `tests/fixtures/`.
The full schema is documented in the
[test case HOCON reference](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/test_case_hocon_reference.md).

There are two ways to create a test case: automatically with the
[Agent Network Test Generator](agent_network_test_generator.md),

or manually.

##### Automatic generation

The `agent_network_test_generator` agent network can analyze an existing agent network
and produce test fixtures automatically. Start the server, open the client, select
`agent_network_test_generator`, and type a prompt such as:

```text
Generate test cases for basic/coffee_finder_advanced
```

You can control how many scenarios are generated with the `test_level` parameter:

```text
Generate test cases for basic/coffee_finder_advanced with minimum coverage
Generate test cases for basic/music_nerd_pro with max coverage
```

| Level     | Scenarios | Description                                                        |
|-----------|-----------|--------------------------------------------------------------------|
| `minimum` | 2--3      | One core happy-path and one critical edge case.                    |
| `normal`  | 5--7      | Happy paths, edge cases, and at least one error/boundary scenario. |
| `max`     | 10--15    | Exhaustive coverage of all capabilities and edge cases.            |

The generator saves fixtures under `tests/fixtures/<agent_name>/`. Review the generated
files before committing — you may need to adjust `gist` criteria, `keywords`, `value`
checks, or `sly_data` values. See
[Agent Network Test Generator](agent_network_test_generator.md) for full details.

##### Manual creation

Create a new `.hocon` file under `tests/fixtures/<group>/<agent_name>/`.
For the full schema reference including all supported fields (`agent`, `success_ratio`,
`connections`, `interactions`, `sly_data`, `response`, stock tests, etc.), see the
[Data-Driven Test Case HOCON File Reference](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/test_case_hocon_reference.md)
in the neuro-san repository.

For existing examples, look at the fixtures under `tests/fixtures/` in this repository.

##### Register the fixture

Generated and manually created fixtures are **not** automatically picked up by CI.
To include a fixture in the integration test suite, add its path to the appropriate
`@parameterized.expand` list in
[test\_integration\_test\_hocons.py](../tests/integration/test_integration_test_hocons.py):

```python
@parameterized.expand(
    DynamicHoconUnitTests.from_hocon_list(
        [
            # existing fixtures ...
            "basic/coffee_finder_advanced/coffee_where_sly_data_8am.hocon",
            # add your new fixture here
            "basic/coffee_finder_advanced/your_new_fixture.hocon",
        ]
    ),
    skip_on_empty=True,
)
```

Each test method is tagged with `@pytest.mark` markers that mirror the folder grouping
(e.g. `integration_basic`, `integration_basic_coffee_finder_advanced`). If you are adding
fixtures for a new agent network that does not have an existing test method, create a new
method following the same pattern.

#### Run test

These test cases are organized to mirror the same grouping structure defined in the network prompting logic.
As a result, there are three supported ways to execute the tests,
each corresponding to a specific grouping strategy.

This design ensures the network prompting logic behaves as intended across different execution scopes,
with ongoing additions of test cases to improve coverage.

Please select the execution option that best aligns with the level of validation you want to perform.

`--timer-top-n 100` flag is optional. It shows the top 100 slowest test cases.

- Run all integration test cases:

    Example:

    ```bash
    pytest -s -m "integration" --timer-top-n 100
    ```

- Run by a group or groups of those test cases:

    ```bash
    pytest -s -m "<name of folder>" --timer-top-n 100
    ```

    Example:

    ```bash
    pytest -s -m "integration_basic" --timer-top-n 100
    pytest -s -m "integration_industry" --timer-top-n 100
    ```

- Run by the network agent hocon name of those test cases:

    ```bash
    pytest -s -m "<name of network_agent hocon>" --timer-top-n 100
    ```

    Example:

    ```bash
    pytest -s -m "integration_basic_coffee_finder_advanced" --timer-top-n 100
    pytest -s -m "integration_industry_airline_policy" --timer-top-n 100
    ```

- Run a single test case:

    pytest -s <"relative path to test hocon">::
    <"test class name">::
    <"test function name">_
    <"the order of test start from zero">_
    <"relative path to test case & replace to "_" vs. "/"">

    Example:

    ```bash
    pytest -s ./tests/integration/test_integration_test_hocons.py::TestIntegrationTestHocons::test_hocon_industry_0_industry_airline_policy_basic_eco_carryon_baggage
    ```

## Improving agent networks

<!-- pyml disable line-length -->

Best practices for building and tuning AAOSA-based agent networks.

- Partition knowledge documents cleanly across agents:
   Organize content into per-agent subdirectories, join broken lines, and remove stale or redundant material. Clean, well-scoped inputs improve retrieval accuracy and agent reliability.

- Choose a routing strategy that matches your document layout:
   Use single-agent routing when domains are clearly distinct or when latency and token cost are a concern. Use multi-agent routing when document boundaries are ambiguous or overlap; fan out to all relevant agents and merge their results.

- Add routing instructions to every agent that delegates (not just the frontman):
   Any intermediate agent that calls sub-agents needs explicit routing logic. For simple queries with a clear single owner, instruct each routing agent to match the query to exactly one sub-agent and send it there directly. For anything more complex — queries that span multiple domains, require partial answers from several agents, or are ambiguous up front — **use AAOSA**. AAOSA is the preferred pattern for multi-agent coordination: each sub-agent independently assesses whether and how it can contribute, reports back, and the routing agent synthesizes a unified response. When in doubt, default to AAOSA; the overhead of unnecessary sub-agent calls is lower than the cost of misrouting or incomplete answers.

- Design the agent network structure carefully:
   Parent-child relationships, nesting depth, and peer groupings all affect routing accuracy. If a sub-agent spans multiple parent domains, consider promoting it to a top-level peer to avoid misrouting and reduce ambiguity.

- Write rich function descriptions (they are your routing layer):
   The top-level agent routes queries based on each sub-agent's `name` and `description` in the `function` block. Always override the `description` when extending `${aaosa_call}`. Choose agent names that reflect their full scope. Keep descriptions concise; one line is enough. Avoid putting lengthy descriptions in the prompt itself, as doing so inflates cost without added benefit.

- Prefer negative instructions over positive ones:
   In practice, "NEVER do X" is followed more reliably than "try to do X", especially when combined with capitalized keywords. When a rule is critical, phrase it as a prohibition.

- Use capitalized keywords sparingly but strategically:
   Words like `NEVER`, `ALWAYS`, and `ONLY` in all-caps are strong emphasis markers. Overusing them dilutes their effect — reserve capitalization for 3–5 of your most critical rules. Since LLMs parse instructions in Markdown format, combining caps with bold formatting (e.g., **NEVER**) provides an additional emphasis signal.

- Use numbered lists for agent instructions, not prose:
   Prose is appropriate for descriptions, but agent rules should be expressed as numbered steps (1, 2, 3 …). Structured lists are followed more reliably than dense paragraphs, and numbered ordering helps the LLM process instructions sequentially.

- Repeat critical instructions at the top and bottom of the prompt:
   LLM compliance improves when key rules appear more than once. Define cross-cutting rules in an `instructions_prefix` block (injected at the top) and repeat the most critical constraints at the end of each agent's `instructions`. Keep prompts concise; excess context increases the risk of rules being ignored.

- Avoid the "lost in the middle" problem:
   LLMs attend most strongly to the beginning and end of a prompt; content in the middle is most likely to be overlooked. Place agent identity and the most critical rules at the start, repeat key constraints at the end, and put edge cases and secondary rules in the middle.

- Include explicit tool-call instructions with exact parameter values:
   Spell out the tool name, parameter name, and expected value in the agent's instructions. Without this, agents may skip tool calls entirely and answer from pre-trained knowledge rather than the provided documents.

- Use `aaosa_basic.hocon` over `aaosa.hocon`:
   The basic variant includes only the core AAOSA variables, without additional features that may introduce unintended behavior. It is more refined and produces more reliable results in practice.

- Use prompt optimization tools to iterate faster:
   Feed your current prompt, failing test cases, and expected outputs to a prompt optimizer for the model you are using (e.g., [OpenAI Optimizer](https://platform.openai.com/chat/edit?models=gpt-5&optimize=true) or [Claude Optimizer](https://claude.ai/public/artifacts/422bb5fc-c03e-4488-9e49-9ad4239398fe)) and ask for a targeted rewrite. This is often faster than manual trial and error.

- Structure agents with explicit query-processing pipelines:
   Without step-by-step decomposition instructions, agents tend to call only one sub-agent even for multi-domain questions. Define an explicit processing pipeline (e.g., analyze → decompose → delegate → synthesize) for the frontman and apply similar step-by-step instructions to mid-level and leaf agents.

- Add anti-summarization rules to preserve completeness:
   LLMs default to summarizing responses, which drop important variations, exceptions, and edge cases. If agents must preserve the exact content of source documents, explicitly instruct them not to omit details — for example: "Include ALL details, categories, exceptions, and variations."

- Keep prompts short and focused:
   Every unnecessary sentence increases the probability that a rule will be ignored. Move lengthy explanations and domain knowledge to function descriptions or source documents, and reserve the instructions block for behavioral rules only.

<!-- pyml enable line-length -->
