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

from coded_tools.music_nerd_pro.accounting import Accountant


class TestAccounting(TestCase):
    """
    Unit tests for Accounting class.
    """

    def test_invoke(self):
        """
        Tests the invoke method of the Accountant CodedTool.
        The Accountant CodedTool should increment the passed running cost by 1.0 each time it is invoked,
        and should return a dictionary with the updated running cost.
        """
        accountant = Accountant()
        # Initial running cost
        a_running_cost = 0.0
        response_1 = accountant.invoke(args={"running_cost": a_running_cost}, sly_data={})
        expected_dict_1 = {"running_cost": 3.0}
        self.assertDictEqual(response_1, expected_dict_1)
        updated_running_cost = response_1["running_cost"]
        response_2 = accountant.invoke(args={"running_cost": updated_running_cost}, sly_data={})
        expected_dict_2 = {"running_cost": 6.0}
        self.assertDictEqual(response_2, expected_dict_2)
