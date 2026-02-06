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
Command to create a new agent HOCON file.
"""

from pathlib import Path

import click

from neuro_san_cli.templates import get_template


def new_agent(agent_name: str, output_dir: str, description: str = None):
    """
    Create a new agent HOCON file with boilerplate structure.

    :param agent_name: Name of the agent (used for filename and agent name)
    :param output_dir: Directory to create the agent file in
    :param description: Optional description of what the agent does
    """
    output_path = Path(output_dir)

    if not output_path.exists():
        click.echo(f"Error: Directory '{output_dir}' does not exist.", err=True)
        click.echo("Hint: Run this command from your project root directory.", err=True)
        raise SystemExit(1)

    # Sanitize agent name (convert to snake_case if needed)
    safe_name = agent_name.lower().replace("-", "_").replace(" ", "_")
    filename = f"{safe_name}.hocon"
    file_path = output_path / filename

    if file_path.exists():
        click.echo(f"Error: File '{file_path}' already exists.", err=True)
        raise SystemExit(1)

    # Generate description if not provided
    if not description:
        description = f"A multi-agent network for {agent_name.replace('_', ' ')}."

    template_vars = {
        "agent_name": safe_name,
        "description": description,
    }

    content = get_template("agent.hocon", template_vars)
    file_path.write_text(content, encoding="utf-8")

    click.echo(f"Created agent: {file_path}")
    click.echo("")
    click.echo("Next steps:")
    click.echo(f"  1. Edit {file_path} to customize your agent")
    click.echo(f"  2. Add \"{safe_name}.hocon\": true to your manifest.hocon")
    click.echo(f"  3. Test with: python -m neuro_san.client.agent_cli --agent {safe_name}")
