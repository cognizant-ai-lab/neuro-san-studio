# Copyright 2025-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Command to initialize a new neuro-san project.
"""

from pathlib import Path

import click

from neuro_san_cli.templates import get_template


# Default models for each provider
DEFAULT_MODELS = {
    "openai": "gpt-4o",
    "anthropic": "claude-3-5-sonnet-20241022",
    "google": "gemini-1.5-pro",
    "azure": "gpt-4o",
    "bedrock": "anthropic.claude-3-5-sonnet-20241022-v2:0",
    "ollama": "llama3.2",
}


def init_project(project_name: str, llm_provider: str, model: str = None):
    """
    Initialize a new neuro-san project with starter files.

    :param project_name: Name of the project directory to create
    :param llm_provider: Default LLM provider (openai, anthropic, etc.)
    :param model: Model name to use (defaults to provider's default)
    """
    project_path = Path(project_name)

    if project_path.exists():
        click.echo(f"Error: Directory '{project_name}' already exists.", err=True)
        raise SystemExit(1)

    # Determine model name
    model_name = model if model else DEFAULT_MODELS.get(llm_provider, "gpt-4o")

    click.echo(f"Creating neuro-san project: {project_name}")

    # Create directory structure
    directories = [
        project_path,
        project_path / "registries",
        project_path / "coded_tools",
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        click.echo(f"  Created: {directory}/")

    # Create files from templates
    template_vars = {
        "project_name": project_name,
        "llm_provider": llm_provider,
        "model_name": model_name,
    }

    files_to_create = [
        ("manifest.hocon", project_path / "registries" / "manifest.hocon"),
        ("llm_config.hocon", project_path / "registries" / "llm_config.hocon"),
        ("hello_world.hocon", project_path / "registries" / "hello_world.hocon"),
        ("env.example", project_path / ".env.example"),
        ("requirements.txt", project_path / "requirements.txt"),
        ("gitignore", project_path / ".gitignore"),
        ("readme.md", project_path / "README.md"),
        ("coded_tool_init.py", project_path / "coded_tools" / "__init__.py"),
    ]

    for template_name, output_path in files_to_create:
        content = get_template(template_name, template_vars)
        output_path.write_text(content, encoding="utf-8")
        click.echo(f"  Created: {output_path}")

    click.echo("")
    click.echo(f"Project '{project_name}' created successfully!")
    click.echo("")
    click.echo("Next steps:")
    click.echo(f"  1. cd {project_name}")
    click.echo("  2. cp .env.example .env")
    click.echo("  3. Edit .env and add your API keys")
    click.echo("  4. pip install -r requirements.txt")
    click.echo("  5. python -m neuro_san.client.agent_cli --agent hello_world")
    click.echo("")
    click.echo("For more information, see the README.md file.")
