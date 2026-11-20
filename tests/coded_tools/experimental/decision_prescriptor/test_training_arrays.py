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

from unittest import TestCase

from coded_tools.experimental.decision_prescriptor.training_arrays import TrainingArrays


class TestTrainingArrays(TestCase):
    """
    Tests for turning records into arrays.
    """

    def test_builds_one_column_per_named_field(self):
        """Each role gets its own array, in the order the fields were named."""
        rows = [{"a": 1.0, "b": 2.0, "c": 3.0}, {"a": 4.0, "b": 5.0, "c": 6.0}]
        arrays = TrainingArrays.build(rows, ["a"], ["b"], ["c"])
        self.assertEqual(arrays.get("context").tolist(), [[1.0], [4.0]])
        self.assertEqual(arrays.get("action").tolist(), [[2.0], [5.0]])
        self.assertEqual(arrays.get("outcome").tolist(), [[3.0], [6.0]])

    def test_names_the_missing_field_and_the_row(self):
        """A vague failure here would be hard to debug from an agent transcript."""
        rows = [{"a": 1.0, "b": 2.0}, {"a": 3.0}]
        with self.assertRaises(ValueError) as caught:
            TrainingArrays.build(rows, ["a"], ["b"], [])
        message = str(caught.exception)
        self.assertIn("row 1", message)
        self.assertIn("b", message)

    def test_names_the_row_with_a_non_numeric_value(self):
        """Text where a number belongs is reported as a ValueError the tools can relay."""
        rows = [{"a": 1.0, "b": 2.0}, {"a": "high", "b": 3.0}]
        with self.assertRaises(ValueError) as caught:
            TrainingArrays.build(rows, ["a"], ["b"], [])
        self.assertIn("row 1", str(caught.exception))

    def test_empty_input_is_refused(self):
        """There is nothing to fit on, so say so rather than failing later."""
        with self.assertRaises(ValueError):
            TrainingArrays.build([], ["a"], ["b"], ["c"])
