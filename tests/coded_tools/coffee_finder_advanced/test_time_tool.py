# Copyright (C) 2023-2025 Cognizant Digital Business, Evolutionary AI.
# All Rights Reserved.
# Issued under the Academic Public License.
#
# You can be released from the terms, and requirements of the Academic Public
# License by purchasing a commercial license.
# Purchase of a commercial license is mandatory for any use of the
# neuro-san-studio SDK Software in commercial settings.
#
from unittest import TestCase

from datetime import datetime
from coded_tools.coffee_finder_advanced.time_tool import TimeTool


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