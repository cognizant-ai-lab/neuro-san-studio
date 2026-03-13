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

# This file defines everything necessary for a data-driven test.
# The schema specifications for this file are documented here:
# https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/test_case_hocon_reference.md
#
# You can run this test by doing the following:
# https://github.dev/cognizant-ai-lab/neuro-san-studio/blob/355_add_smoke_test_using_music_pro_hocon/CONTRIBUTING.md#testing-guidelines

from unittest import TestCase

import pytest
from neuro_san.test.unittest.dynamic_hocon_unit_tests import DynamicHoconUnitTests
from parameterized import parameterized

from tests.utils.fail_fast_param_mixin import FailFastParamMixin


class TestIntegrationTestHocons(TestCase, FailFastParamMixin):
    """
    Data-driven dynamic test cases where each test case is specified by a single hocon file.
    """

    # A single instance of the DynamicHoconUnitTests helper class.
    # We pass it our source file location and a relative path to the common
    # root of the test hocon files listed in the @parameterized.expand()
    # annotation below so the instance can find the hocon test cases listed.
    DYNAMIC = DynamicHoconUnitTests(__file__, path_to_basis="../fixtures")

    @parameterized.expand(
        DynamicHoconUnitTests.from_hocon_list(
            [
                # These can be in any order.
                # Ideally more basic functionality will come first.
                # Barring that, try to stick to alphabetical order.
                "basic/music_nerd_pro/combination_responses_with_history_direct.hocon",
                "basic/pii_middleware/jenny_phone.hocon",
                # List more hocon files as they become available here.
            ]
        ),
        skip_on_empty=True,
    )
    @pytest.mark.integration
    @pytest.mark.integration_basic
    def test_hocon_basic(self, test_name: str, test_hocon: str):
        """
        Test method for a single parameterized test case specified by a hocon file.
        Arguments to this method are given by the iteration that happens as a result
        of the magic of the @parameterized.expand annotation above.

        :param test_name: The name of a single test.
        :param test_hocon: The hocon file of a single data-driven test case.
        """
        # Call the guts of the dynamic test driver.
        # This will expand the test_hocon file name from the expanded list to
        # include the file basis implied by the __file__ and path_to_basis above.

        self.DYNAMIC.one_test_hocon(self, test_name, test_hocon)

    @parameterized.expand(
        DynamicHoconUnitTests.from_hocon_list(
            [
                # These can be in any order.
                # Ideally more basic functionality will come first.
                # Barring that, try to stick to alphabetical order.
                "basic/coffee_finder_advanced/coffee_what_time_sly_data_1am.hocon",
                "basic/coffee_finder_advanced/coffee_where_sly_data_1am.hocon",
                "basic/coffee_finder_advanced/coffee_where_sly_data_6am.hocon",
                "basic/coffee_finder_advanced/coffee_where_sly_data_8am.hocon",
                # List more hocon files as they become available here.
            ]
        ),
        skip_on_empty=True,
    )
    @pytest.mark.integration
    @pytest.mark.integration_basic
    @pytest.mark.integration_basic_coffee_finder_advanced
    def test_hocon_industry_coffee_finder_advanced(self, test_name: str, test_hocon: str):
        """
        Test method for a single parameterized test case specified by a hocon file.
        Arguments to this method are given by the iteration that happens as a result
        of the magic of the @parameterized.expand annotation above.

        :param test_name: The name of a single test.
        :param test_hocon: The hocon file of a single data-driven test case.
        """
        # Call the guts of the dynamic test driver.
        # This will expand the test_hocon file name from the expanded list to
        # include the file basis implied by the __file__ and path_to_basis above.
        self.DYNAMIC.one_test_hocon(self, test_name, test_hocon)

    # ------------------------------------------------------------
    # FAIL-FAST GROUP KEY (base test method name)
    # ------------------------------------------------------------
    @parameterized.expand(
        DynamicHoconUnitTests.from_hocon_list(
            [
                # These can be in any order.
                # Ideally more basic functionality will come first.
                # Barring that, try to stick to alphabetical order.
                "basic/coffee_finder_advanced/coffee_continue_0_order_sly_data_1am_negative_test.hocon",
                "basic/coffee_finder_advanced/coffee_continue_1_order_sly_data_1am.hocon",
                "basic/coffee_finder_advanced/coffee_continue_2_reorder_sly_data_1am.hocon",
                "basic/coffee_finder_advanced/coffee_continue_3_reorder_sly_data_8am_new_location.hocon",
                "basic/coffee_finder_advanced/coffee_continue_4_reorder_sly_data_8am_from_last_order.hocon",
                "basic/coffee_finder_advanced/coffee_continue_5_reorder_sly_data_8am_from_1st_order.hocon",
                "basic/coffee_finder_advanced/"
                "coffee_continue_reorder_sly_data_8am_negative_test_multi_orders_exist.hocon",
                "basic/coffee_finder_advanced/coffee_continue_reorder_sly_data_1am_negative_test_partial_name.hocon",
                # List more hocon files as they become available here.
            ]
        ),
        skip_on_empty=True,
    )
    @pytest.mark.integration
    @pytest.mark.integration_basic
    @pytest.mark.integration_basic_coffee_finder_advanced
    @pytest.mark.integration_basic_coffee_finder_advanced_e2e
    def test_hocon_industry_coffee_finder_advanced_e2e(self, test_name: str, test_hocon: str):
        self.run_hocon_group_fail_fast_case(test_name, test_hocon)

    @parameterized.expand(
        DynamicHoconUnitTests.from_hocon_list(
            [
                # These can be in any order.
                # Ideally more basic functionality will come first.
                # Barring that, try to stick to alphabetical order.
                "industry/telco_network_support_test.hocon",
                "industry/consumer_decision_assistant_comprehensive.hocon",
                "industry/cpg_agents_test.hocon",
                # List more hocon files as they become available here.
            ]
        ),
        skip_on_empty=True,
    )
    @pytest.mark.integration
    @pytest.mark.integration_industry
    def test_hocon_industry(self, test_name: str, test_hocon: str):
        """
        Test method for a single parameterized test case specified by a hocon file.
        Arguments to this method are given by the iteration that happens as a result
        of the magic of the @parameterized.expand annotation above.

        :param test_name: The name of a single test.
        :param test_hocon: The hocon file of a single data-driven test case.
        """
        # Call the guts of the dynamic test driver.
        # This will expand the test_hocon file name from the expanded list to
        # include the file basis implied by the __file__ and path_to_basis above.
        self.DYNAMIC.one_test_hocon(self, test_name, test_hocon)

    @parameterized.expand(
        DynamicHoconUnitTests.from_hocon_list(
            [
                # These can be in any order.
                # Ideally more basic functionality will come first.
                # Barring that, try to stick to alphabetical order.
                "industry/airline_policy/basic_eco_carryon_baggage.hocon",
                "industry/airline_policy/basic_eco_checkin_baggage_at_gate_fee.hocon",
                "industry/airline_policy/basic_eco_checkin_baggage.hocon",
                "industry/airline_policy/general_baggage_tracker.hocon",
                "industry/airline_policy/general_carryon_baggage_liquid_items.hocon",
                "industry/airline_policy/general_carryon_baggage_overweight_fee.hocon",
                "industry/airline_policy/general_carryon_person_item_size.hocon",
                "industry/airline_policy/general_carryon_other_items.hocon",
                "industry/airline_policy/general_carryon_baggage_size.hocon",
                "industry/airline_policy/general_carryon_person_item.hocon",
                "industry/airline_policy/general_checkin_baggage_liquid_items.hocon",
                "industry/airline_policy/general_checkin_baggage.hocon",
                "industry/airline_policy/general_child_car_seat.hocon",
                "industry/airline_policy/general_child_stroller.hocon",
                "industry/airline_policy/general_children_formula.hocon",
                "industry/airline_policy/general_children_id_domestic_flights.hocon",
                "industry/airline_policy/general_children_id_international_flights.hocon",
                "industry/airline_policy/general_children_seating.hocon",
                "industry/airline_policy/general_family_with_children.hocon",
                "industry/airline_policy/premier_gold_checkin_baggage_weights.hocon",
                "industry/airline_policy/premium_eco_checkin_baggage_weights.hocon",
                # List more hocon files as they become available here.
            ]
        ),
        skip_on_empty=True,
    )
    @pytest.mark.integration
    @pytest.mark.integration_industry
    @pytest.mark.integration_industry_airline_policy
    def test_hocon_industry_airline_policy(self, test_name: str, test_hocon: str):
        """
        Test method for a single parameterized test case specified by a hocon file.
        Arguments to this method are given by the iteration that happens as a result
        of the magic of the @parameterized.expand annotation above.

        :param test_name: The name of a single test.
        :param test_hocon: The hocon file of a single data-driven test case.
        """
        # Call the guts of the dynamic test driver.
        # This will expand the test_hocon file name from the expanded list to
        # include the file basis implied by the __file__ and path_to_basis above.
        self.DYNAMIC.one_test_hocon(self, test_name, test_hocon)

    @parameterized.expand(
        DynamicHoconUnitTests.from_hocon_list(
            [
                # These can be in any order.
                # Ideally more basic functionality will come first.
                # Barring that, try to stick to alphabetical order.
                "experimental/copy_cat/copy_hello_world.hocon",
                "experimental/mdap_decomposer/long_multiplication.hocon",
                "experimental/mdap_decomposer/list_sorting.hocon",
                # List more hocon files as they become available here.
            ]
        ),
        skip_on_empty=True,
    )
    @pytest.mark.integration
    @pytest.mark.integration_experimental
    def test_hocon_experimental(self, test_name: str, test_hocon: str):
        """
        Test method for a single parameterized test case specified by a hocon file.
        Arguments to this method are given by the iteration that happens as a result
        of the magic of the @parameterized.expand annotation above.

        :param test_name: The name of a single test.
        :param test_hocon: The hocon file of a single data-driven test case.
        """
        # Call the guts of the dynamic test driver.
        # This will expand the test_hocon file name from the expanded list to
        # include the file basis implied by the __file__ and path_to_basis above.

        self.DYNAMIC.one_test_hocon(self, test_name, test_hocon)
