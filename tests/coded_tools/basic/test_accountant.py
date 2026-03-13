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
from typing import Any
from typing import Dict
from typing import cast
from unittest import TestCase

import pytest

from coded_tools.basic.accountant import Accountant


class TestAccountant(TestCase):
    """
    Unit tests for Accountant class.
    """

    @pytest.mark.asyncio
    async def test_async_invoke(self):
        """
        Tests the invoke method of the Accountant CodedTool.
        The Accountant CodedTool should increment the passed running cost by 3.0 each time it is invoked,
        and should return a dictionary with the updated running cost.
        """
        accountant = Accountant()
        # Initial running cost
        a_running_cost = 0.0
        response_1 = cast(
            Dict[str, Any], asyncio.run(accountant.async_invoke(args={"running_cost": a_running_cost}, sly_data={}))
        )
        expected_dict_1 = {"running_cost": 3.0}
        self.assertDictEqual(response_1, expected_dict_1)
        updated_running_cost = response_1["running_cost"]
        response_2 = cast(
            Dict[str, Any],
            asyncio.run(accountant.async_invoke(args={"running_cost": updated_running_cost}, sly_data={})),
        )
        expected_dict_2 = {"running_cost": 6.0}
        self.assertDictEqual(response_2, expected_dict_2)
