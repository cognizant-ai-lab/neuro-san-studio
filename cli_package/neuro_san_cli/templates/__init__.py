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
Template management for neuro-san-cli.
"""

from pathlib import Path
from string import Template
from typing import Dict


TEMPLATES_DIR = Path(__file__).parent


def get_template(template_name: str, variables: Dict[str, str]) -> str:
    """
    Load a template file and substitute variables.

    :param template_name: Name of the template file (without .template extension)
    :param variables: Dictionary of variables to substitute
    :return: Rendered template content
    """
    template_path = TEMPLATES_DIR / f"{template_name}.template"

    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    template_content = template_path.read_text(encoding="utf-8")

    # Use safe_substitute to avoid KeyError for missing variables
    template = Template(template_content)
    return template.safe_substitute(variables)
