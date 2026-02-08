# Copyright © 2025-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
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
#
# END COPYRIGHT

import asyncio
import json
from typing import Any
from typing import Dict

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.cruse_theme_agent.cruse_theme_constants import COLOR_PALETTES
from coded_tools.cruse_theme_agent.cruse_theme_constants import CSS_DOODLE_TEMPLATES
from coded_tools.cruse_theme_agent.cruse_theme_constants import GRADIENT_TEMPLATES


class ThemeTemplateProvider(CodedTool):
    """
    CodedTool implementation which provides comprehensive background schema templates
    for generating dynamic (css-doodle) and static (Gradient) backgrounds based on agent context.
    """

    COLOR_PALETTES = COLOR_PALETTES
    CSS_DOODLE_TEMPLATES = CSS_DOODLE_TEMPLATES
    GRADIENT_TEMPLATES = GRADIENT_TEMPLATES

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        Provides background schema templates, css-doodle patterns,
        gradient templates, and color guidance.

        :param args: An argument dictionary whose keys are the parameters
            to the coded tool and whose values are the values passed for
            them by the calling agent. This dictionary is to be treated as
            read-only.

            The argument dictionary can contain:
                "request_type": "css-doodle" | "gradient" | "colors" | "full"

        :param sly_data: A dictionary whose keys are defined by the agent
            hierarchy, but whose values are meant to be kept out of the
            chat stream.

        :return: JSON string containing requested information
        """
        request_type = args.get("request_type", "full")

        result = {}

        if request_type in ["css-doodle", "full"]:
            result["css_doodle_templates"] = self.CSS_DOODLE_TEMPLATES
            result["css_doodle_patterns"] = list(self.CSS_DOODLE_TEMPLATES.keys())

        if request_type in ["gradient", "full"]:
            result["gradient_templates"] = self.GRADIENT_TEMPLATES

        if request_type in ["colors", "full"]:
            result["color_palettes"] = self.COLOR_PALETTES

        return json.dumps(result, indent=2)

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """Run invoke asynchronously."""
        return await asyncio.to_thread(self.invoke, args, sly_data)
