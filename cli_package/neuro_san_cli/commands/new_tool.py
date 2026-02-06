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
Command to create a new CodedTool Python file.
"""

from pathlib import Path

import click

from neuro_san_cli.templates import get_template


def to_pascal_case(name: str) -> str:
    """Convert a snake_case or kebab-case name to PascalCase."""
    parts = name.replace("-", "_").split("_")
    return "".join(part.capitalize() for part in parts)


def new_tool(tool_name: str, output_dir: str, description: str = None):
    """
    Create a new CodedTool Python file with boilerplate structure.

    :param tool_name: Name of the tool (used for filename and class name)
    :param output_dir: Directory to create the tool file in
    :param description: Optional description of what the tool does
    """
    output_path = Path(output_dir)

    if not output_path.exists():
        click.echo(f"Error: Directory '{output_dir}' does not exist.", err=True)
        click.echo("Hint: Run this command from your project root directory.", err=True)
        raise SystemExit(1)

    # Sanitize tool name
    safe_name = tool_name.lower().replace("-", "_").replace(" ", "_")
    class_name = to_pascal_case(safe_name)
    filename = f"{safe_name}.py"
    file_path = output_path / filename

    if file_path.exists():
        click.echo(f"Error: File '{file_path}' already exists.", err=True)
        raise SystemExit(1)

    # Generate description if not provided
    if not description:
        description = f"A coded tool that performs {tool_name.replace('_', ' ')} operations."

    template_vars = {
        "tool_name": safe_name,
        "class_name": class_name,
        "description": description,
    }

    content = get_template("coded_tool.py", template_vars)
    file_path.write_text(content, encoding="utf-8")

    click.echo(f"Created coded tool: {file_path}")
    click.echo("")
    click.echo("Next steps:")
    click.echo(f"  1. Edit {file_path} to implement your tool logic")
    click.echo("  2. Add the tool to your toolbox_info.hocon (if using toolbox)")
    click.echo("  3. Reference the tool in your agent's HOCON file")
    click.echo("")
    click.echo("Example toolbox_info.hocon entry:")
    click.echo(f'  "{safe_name}": {{')
    click.echo(f'    "class": "{safe_name}.{class_name}"')
    click.echo("  }")
