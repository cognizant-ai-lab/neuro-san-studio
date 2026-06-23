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
"""
Grounded coded-tool package for the rule_based_ai_underwriting_system network
(Experiment 2). The single grounded data tool reads the three real source files
in this folder and exposes them to the agent network.
"""

from .underwriting_data_tool import UnderwritingDataTool
from .underwriting_data_tool import get_case
from .underwriting_data_tool import get_wording
from .underwriting_data_tool import list_cases
from .underwriting_data_tool import load_rules
from .underwriting_data_tool import unmatched_line_names

__all__ = [
    "UnderwritingDataTool",
    "get_case",
    "get_wording",
    "list_cases",
    "load_rules",
    "unmatched_line_names",
]

__version__ = "1.0.0"
