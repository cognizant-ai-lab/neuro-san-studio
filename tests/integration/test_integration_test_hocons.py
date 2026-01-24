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
import re
import os
from neuro_san.test.unittest.dynamic_hocon_unit_tests import DynamicHoconUnitTests
from parameterized import parameterized

from coded_tools.kwik_agents.list_topics import MEMORY_DATA_STRUCTURE
from coded_tools.kwik_agents.list_topics import MEMORY_FILE_PATH


class FailFastParamMixin:
    """
    Helper mixin that allows a *single parameterized test group* to fail-fast.

    Meaning:
      - if one parameterized case fails (ex: c.hocon),
      - then all remaining cases in that SAME group (ex: d.hocon) will be skipped.

    IMPORTANT:
      - This is NOT a global "stop pytest" feature.
      - It only affects tests that call _failfast_skip_if_failed().
      - Other test functions will still run normally.
    """

    # Shared state per test class (NOT per instance):
    # key = group name string
    # val = True if any case in that group has failed
    _failfast_flags = {}

    def _failfast_skip_if_failed(self, key: str):
        """
        If a previous case failed for this group, skip this case.
        """
        if self.__class__._failfast_flags.get(key, False):
            pytest.skip(f"Earlier case failed for fail-fast group '{key}'")

    def _failfast_mark_failed(self, key: str):
        """
        Mark a group as having failed so future cases skip.
        """
        self.__class__._failfast_flags[key] = True

    def run_hocon_failfast(self, test_name: str, test_hocon: str):
        """
        Run one HOCON-driven E2E test case with FAIL-FAST behavior for the *parameterized group*.

        This helper is intended for end-to-end (E2E) integration tests where:
        - Each .hocon file represents one full scenario/case.
        - If one scenario fails, running the remaining scenarios is often not useful
            (it usually causes cascading failures and wastes runtime).

        Extra requirement (memory cleanup):
        - Before the first case in a fail-fast group starts, we delete the shared
            TopicMemory.json file to ensure the entire parameterized group starts from
            a clean memory state.
        - Cleanup is performed once per group (not once per case).

        How grouping works:
        - parameterized.expand generates a unique unittest-style method name per case, e.g.
            test_hocon_xxx_e2e_7_some_description
        - We derive the *base* method name by stripping "_<index>_<rest...>"
            so all cases from the same original test method share ONE group key.
        - Once any case in the group fails, remaining cases in that group are skipped.
        """

        # Base method name for the current parameterized group
        group = re.sub(r"_\d+_.*$", "", self._testMethodName)

        # ------------------------------------------------------------
        # One-time cleanup memory file BEFORE first case in this fail-fast group
        # ------------------------------------------------------------
        # We store a cleanup flag per group so we only do it once.
        cleanup_key = f"{group}::cleanup_done"

        if not self.__class__._failfast_flags.get(cleanup_key, False):
            topic_memory_path = MEMORY_FILE_PATH + MEMORY_DATA_STRUCTURE + ".json"

            # Delete file if it exists. Ignore if it's already gone.
            try:
                os.remove(topic_memory_path)
            except FileNotFoundError:
                pass

            # Mark cleanup as done so later param cases don’t repeat it
            self.__class__._failfast_flags[cleanup_key] = True

        # ------------------------------------------------------------
        # Fail-fast gating logic
        # ------------------------------------------------------------
        self._failfast_skip_if_failed(group)

        try:
            # Run your existing dynamic driver
            self.DYNAMIC.one_test_hocon(self, test_name, test_hocon)
        except Exception:
            # Mark group as failed so remaining cases skip
            self._failfast_mark_failed(group)
            raise


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
        self.run_hocon_failfast(test_name, test_hocon)

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
