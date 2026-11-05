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

from typing import Any

import numpy as np


# One conversion with one entry point; splitting it further would not help a reader.
# pylint: disable=too-few-public-methods
class TrainingArrays:
    """
    Turns a list of record dicts into the arrays the surrogate and the search need.
    """

    @staticmethod
    def build(
        rows: list[dict[str, Any]],
        context_names: list[str],
        action_names: list[str],
        outcome_names: list[str],
    ) -> dict[str, np.ndarray]:
        """
        :param rows: Historical records, each holding every named field.
        :param context_names: Fields describing the situation, which cannot be chosen.
        :param action_names: Fields describing the decision, which can be chosen.
        :param outcome_names: Fields describing what happened, to be predicted.
        :return: Dict with the "context", "action" and "outcome" arrays.
        :raises ValueError: If no rows are given, a named field is missing from a row,
            or a value is not a number.
        """
        if not rows:
            raise ValueError("no rows supplied")

        return {
            "context": TrainingArrays._column(rows, context_names),
            "action": TrainingArrays._column(rows, action_names),
            "outcome": TrainingArrays._column(rows, outcome_names),
        }

    @staticmethod
    def _column(rows: list[dict[str, Any]], names: list[str]) -> np.ndarray:
        """
        Gather the named fields of every row into one array.

        :param rows: Historical records.
        :param names: Fields to gather, in column order.
        :return: Array of shape (num_rows, len(names)).
        :raises ValueError: Naming the row and field when a field is missing or not a number.
        """
        table: list[list[float]] = []
        for index, row in enumerate(rows):
            missing: list[str] = [name for name in names if name not in row]
            if missing:
                raise ValueError(f"row {index} is missing field(s): {', '.join(missing)}")
            try:
                table.append([float(row.get(name)) for name in names])
            except (TypeError, ValueError) as error:
                raise ValueError(f"row {index} has a non-numeric value: {error}") from error
        return np.array(table, dtype=float)
