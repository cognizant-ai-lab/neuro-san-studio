# neuro-san-cli

A CLI tool for scaffolding and managing neuro-san projects.

## Installation

```bash
pip install neuro-san-cli
```

Or install from source:

```bash
cd cli_package
pip install -e .
```

## Usage

### Initialize a new project

Create a new neuro-san project with starter files:

```bash
neuro-san init my-project
```

This creates:
- `my-project/registries/manifest.hocon` - Agent manifest
- `my-project/registries/hello_world.hocon` - Example agent
- `my-project/coded_tools/` - Directory for custom tools
- `my-project/.env.example` - Template for API keys
- `my-project/requirements.txt` - Python dependencies

### Create a new agent

Scaffold a new agent HOCON file:

```bash
neuro-san new agent my_agent
```

Options:
- `--output-dir` / `-o`: Output directory (default: `registries/`)

### Create a new coded tool

Scaffold a new CodedTool Python file:

```bash
neuro-san new tool my_tool
```

Options:
- `--output-dir` / `-o`: Output directory (default: `coded_tools/`)

## Development

```bash
# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
flake8 neuro_san_cli
pylint neuro_san_cli
```

## License

Apache License 2.0 - See LICENSE.txt for details.
