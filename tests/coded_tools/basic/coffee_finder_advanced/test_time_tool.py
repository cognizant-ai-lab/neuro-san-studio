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

from datetime import datetime
from unittest import TestCase

from coded_tools.basic.coffee_finder_advanced.time_tool import TimeTool


class TestTimeTool(TestCase):
    """
    Unit tests for the TimeTool class.
    """

    def test_invoke_no_sly_data(self):
        """
        Tests the invoke method of the TimeTool CodedTool when no time is specified in the sly_data.
        """
        sly_data = {}
        time_tool = TimeTool()
        response = time_tool.invoke(args={}, sly_data=sly_data)
        self.assertTrue(TestTimeTool._is_valid_time_format(response), "Invalid time format")

    def test_invoke_sly_data(self):
        """
        Tests the invoke method of the TimeTool CodedTool when a time is specified in the sly_data.
        """
        sly_data = {"time": "8 am"}
        time_tool = TimeTool()
        response = time_tool.invoke(args={}, sly_data=sly_data)
        expected_response = "8 am"
        self.assertEqual(expected_response, response)

    @staticmethod
    def _is_valid_time_format(time_str: str) -> bool:
        try:
            datetime.strptime(time_str, "%I:%M %p")
            return True
        except ValueError:
            return False
