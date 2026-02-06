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
Main entry point for the neuro-san CLI.
"""

import click

from neuro_san_cli import __version__
from neuro_san_cli.commands.init_project import init_project
from neuro_san_cli.commands.new_agent import new_agent
from neuro_san_cli.commands.new_tool import new_tool


@click.group()
@click.version_option(version=__version__, prog_name="neuro-san")
def cli():
    """
    neuro-san CLI - Scaffold and manage neuro-san projects.

    Use 'neuro-san init' to create a new project, or 'neuro-san new' to
    create new agents and tools within an existing project.
    """
    pass


@cli.command("init")
@click.argument("project_name")
@click.option(
    "--llm-provider",
    type=click.Choice(["openai", "anthropic", "google", "azure", "bedrock", "ollama"]),
    default="openai",
    help="Default LLM provider for the project.",
)
@click.option(
    "--model",
    default=None,
    help="Default model name (e.g., gpt-4o, claude-3-5-sonnet). If not specified, uses provider default.",
)
def init_command(project_name: str, llm_provider: str, model: str):
    """
    Initialize a new neuro-san project.

    Creates a new directory with the project name containing starter files
    for building a neuro-san multi-agent application.
    """
    init_project(project_name, llm_provider, model)


@cli.group("new")
def new():
    """Create new agents or tools."""
    pass


@new.command("agent")
@click.argument("agent_name")
@click.option(
    "--output-dir",
    "-o",
    default="registries",
    help="Output directory for the agent HOCON file.",
)
@click.option(
    "--description",
    "-d",
    default=None,
    help="Description of what the agent does.",
)
def new_agent_command(agent_name: str, output_dir: str, description: str):
    """
    Create a new agent HOCON file.

    Scaffolds a new agent configuration file with boilerplate structure.
    """
    new_agent(agent_name, output_dir, description)


@new.command("tool")
@click.argument("tool_name")
@click.option(
    "--output-dir",
    "-o",
    default="coded_tools",
    help="Output directory for the coded tool Python file.",
)
@click.option(
    "--description",
    "-d",
    default=None,
    help="Description of what the tool does.",
)
def new_tool_command(tool_name: str, output_dir: str, description: str):
    """
    Create a new CodedTool Python file.

    Scaffolds a new Python file implementing the CodedTool interface.
    """
    new_tool(tool_name, output_dir, description)


if __name__ == "__main__":
    cli()
