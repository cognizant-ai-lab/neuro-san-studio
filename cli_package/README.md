# neuro-san-cli

A CLI tool for scaffolding and managing neuro-san projects.

## Installation

```bash
pip install neuro-san-cli
```

Or install from source:

```bash
cd cli_package
pip install --editable .
```

## Quick Start

```bash
# Create a new project
neuro-san init my-project

# Navigate to the project
cd my-project

# Set up environment
cp .env.example .env
# Edit .env and add your API keys

# Install dependencies
pip install --requirement requirements.txt

# Run the project
python run.py
```

Open http://localhost:4173 to view your agents in NSFlow.

## Commands

### Help

View all available commands and options:

```bash
neuro-san --help
```

View help for a specific command:

```bash
neuro-san init --help
neuro-san new --help
neuro-san new agent --help
neuro-san new tool --help
```

### Initialize a new project

Create a new neuro-san project with starter files:

```bash
neuro-san init <project-name> [OPTIONS]
```

Options:

| Option | Description | Default |
|--------|-------------|---------|
| `--llm-provider` | Default LLM provider (openai, anthropic, google, azure, bedrock, ollama) | openai |
| `--model` | Default model name (e.g., gpt-4o, claude-3-5-sonnet) | Provider default |
| `--include-designer` | Include the Agent Network Designer for creating agent networks via natural language | False |

Examples:

```bash
# Basic project with OpenAI
neuro-san init my-project

# Project with Anthropic Claude
neuro-san init my-project --llm-provider anthropic --model claude-3-5-sonnet-20241022

# Project with Agent Network Designer
neuro-san init my-project --include-designer
```

This creates:

| File/Directory | Description |
|----------------|-------------|
| `registries/manifest.hocon` | Agent manifest listing which agents to serve |
| `registries/llm_config.hocon` | LLM configuration (provider, model, temperature) |
| `registries/hello_world.hocon` | Example "Hello World" agent |
| `coded_tools/` | Directory for custom Python tools |
| `run.py` | Script to start the server and NSFlow UI |
| `.env.example` | Template for API keys |
| `requirements.txt` | Python dependencies |
| `README.md` | Project documentation |
| `.gitignore` | Git ignore file |

When using `--include-designer`, additional files are created:

| File/Directory | Description |
|----------------|-------------|
| `registries/agent_network_designer.hocon` | Main designer agent |
| `registries/agent_network_editor.hocon` | Support network for editing |
| `registries/agent_network_instructions_editor.hocon` | Support network for instructions |
| `registries/agent_network_query_generator.hocon` | Support network for queries |
| `coded_tools/agent_network_designer/` | Designer coded tools |
| `coded_tools/agent_network_editor/` | Editor coded tools |
| `coded_tools/agent_network_instructions_editor/` | Instructions editor coded tools |
| `mcp/mcp_info.hocon` | MCP server configuration |
| `toolbox/toolbox_info.hocon` | Toolbox configuration |

### Create a new agent

Scaffold a new agent HOCON file:

```bash
neuro-san new agent <agent-name> [OPTIONS]
```

Options:

| Option | Description | Default |
|--------|-------------|---------|
| `--output-dir`, `-o` | Output directory for the agent HOCON file | registries |
| `--description`, `-d` | Description of what the agent does | None |

Examples:

```bash
# Create agent in default location
neuro-san new agent my_agent

# Create agent with description
neuro-san new agent my_agent --description "An agent that helps with data analysis"

# Create agent in custom directory
neuro-san new agent my_agent --output-dir registries/custom
```

### Create a new coded tool

Scaffold a new CodedTool Python file:

```bash
neuro-san new tool <tool-name> [OPTIONS]
```

Options:

| Option | Description | Default |
|--------|-------------|---------|
| `--output-dir`, `-o` | Output directory for the coded tool Python file | coded_tools |
| `--description`, `-d` | Description of what the tool does | None |

Examples:

```bash
# Create tool in default location
neuro-san new tool my_tool

# Create tool with description
neuro-san new tool my_tool --description "A tool that fetches weather data"

# Create tool in custom directory
neuro-san new tool my_tool --output-dir coded_tools/utilities
```

## Development

```bash
# Install in development mode
pip install --editable ".[dev]"

# Run tests
pytest

# Run linting
flake8 neuro_san_cli
pylint neuro_san_cli
```

## License

Apache License 2.0 - See LICENSE.txt for details.
