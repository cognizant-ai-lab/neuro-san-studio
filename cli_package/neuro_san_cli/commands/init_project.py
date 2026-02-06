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

import shutil
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

# Path to the designer assets (relative to neuro-san-studio root)
DESIGNER_ASSETS_DIR = Path(__file__).parent.parent / "designer_assets"


def init_project(project_name: str, llm_provider: str, model: str = None,
                 include_designer: bool = False):
    """
    Initialize a new neuro-san project with starter files.

    :param project_name: Name of the project directory to create
    :param llm_provider: Default LLM provider (openai, anthropic, etc.)
    :param model: Model name to use (defaults to provider's default)
    :param include_designer: Include the Agent Network Designer
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

    # Build designer manifest entries if needed
    designer_manifest_entries = ""
    if include_designer:
        designer_manifest_entries = """
    # Agent network designer family of agents
    #
    "agent_network_designer.hocon": true,
    "agent_network_editor.hocon": {
        # This is a support network for agent_network_designer
        # We want it served up, but not listed as a public agent network
        "serve": true,
        "public": false
    },
    "agent_network_instructions_editor.hocon": {
        # This is a support network for agent_network_designer
        # We want it served up, but not listed as a public agent network
        "serve": true,
        "public": false
    },
    "agent_network_query_generator.hocon": {
        # This is a support network for agent_network_designer
        # We want it served up, but not listed as a public agent network
        "serve": true,
        "public": false
    },
"""

    # Create files from templates
    template_vars = {
        "project_name": project_name,
        "llm_provider": llm_provider,
        "model_name": model_name,
        "designer_manifest_entries": designer_manifest_entries,
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
        ("run.py", project_path / "run.py"),
    ]

    for template_name, output_path in files_to_create:
        content = get_template(template_name, template_vars)
        output_path.write_text(content, encoding="utf-8")
        click.echo(f"  Created: {output_path}")

    # Copy Agent Network Designer files if requested
    if include_designer:
        _copy_designer_files(project_path)

    click.echo("")
    click.echo(f"Project '{project_name}' created successfully!")
    click.echo("")
    click.echo("Next steps:")
    click.echo(f"  1. cd {project_name}")
    click.echo("  2. cp .env.example .env")
    click.echo("  3. Edit .env and add your API keys")
    click.echo("  4. pip install -r requirements.txt")
    click.echo("  5. python run.py")
    click.echo("")
    click.echo("This will start the neuro-san server and NSFlow UI.")
    click.echo("Open http://localhost:4173 to view your agents in NSFlow.")
    if include_designer:
        click.echo("")
        click.echo("Agent Network Designer included! Use it to create new agent networks:")
        click.echo("  Select 'agent_network_designer' in NSFlow and describe your use case.")
    click.echo("")
    click.echo("For more information, see the README.md file.")


def _copy_designer_files(project_path: Path):
    """
    Copy the Agent Network Designer files to the project.

    :param project_path: Path to the project directory
    """
    click.echo("")
    click.echo("Adding Agent Network Designer...")

    # Copy HOCON files from designer_assets/registries
    registries_src = DESIGNER_ASSETS_DIR / "registries"
    registries_dst = project_path / "registries"

    designer_hocon_files = [
        "agent_network_designer.hocon",
        "agent_network_editor.hocon",
        "agent_network_instructions_editor.hocon",
        "agent_network_query_generator.hocon",
    ]

    for hocon_file in designer_hocon_files:
        src = registries_src / hocon_file
        dst = registries_dst / hocon_file
        if src.exists():
            shutil.copy2(src, dst)
            click.echo(f"  Created: {dst}")

    # Copy coded_tools directories
    coded_tools_src = DESIGNER_ASSETS_DIR / "coded_tools"
    coded_tools_dst = project_path / "coded_tools"

    designer_tool_dirs = [
        "agent_network_designer",
        "agent_network_editor",
        "agent_network_instructions_editor",
    ]

    for tool_dir in designer_tool_dirs:
        src = coded_tools_src / tool_dir
        dst = coded_tools_dst / tool_dir
        if src.exists():
            shutil.copytree(src, dst)
            click.echo(f"  Created: {dst}/")

    # Copy mcp directory
    mcp_src = DESIGNER_ASSETS_DIR / "mcp"
    mcp_dst = project_path / "mcp"
    if mcp_src.exists():
        shutil.copytree(mcp_src, mcp_dst)
        click.echo(f"  Created: {mcp_dst}/")

    # Copy toolbox directory
    toolbox_src = DESIGNER_ASSETS_DIR / "toolbox"
    toolbox_dst = project_path / "toolbox"
    if toolbox_src.exists():
        shutil.copytree(toolbox_src, toolbox_dst)
        click.echo(f"  Created: {toolbox_dst}/")
