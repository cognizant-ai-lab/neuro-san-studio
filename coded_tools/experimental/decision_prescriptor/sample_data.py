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


class SampleData:
    """
    A synthetic dataset so the agent network runs out of the box.

    The scenario is delivery staffing on a portfolio of engagements. It is synthetic
    on purpose: the point of the example is the method, and inventing figures about
    real companies to dress it up would make the output look like evidence when it
    is not.

    The generator builds in two genuine conflicts, because a trade-off front is only
    interesting when the objectives actually disagree:

    * senior staffing lowers delivery risk but costs margin;
    * automation lifts margin but pushes out time to value while it is set up.

    An optimizer that returned a single answer here would be hiding one of those
    exchanges. The Pareto front surfaces both and leaves the choice with a human.
    """

    CONTEXT_FIELDS: tuple[str, ...] = ("account_size", "urgency")
    ACTION_FIELDS: tuple[str, ...] = ("senior_staff_ratio", "automation_investment")
    OUTCOME_FIELDS: tuple[str, ...] = ("margin_pct", "delivery_risk", "time_to_value_weeks")
    OUTCOME_MAXIMIZE: tuple[bool, ...] = (True, False, False)

    @staticmethod
    def generate(num_rows: int = 400, seed: int = 7) -> list[dict[str, float]]:
        """
        Generate historical engagement records.

        :param num_rows: Number of records to produce.
        :param seed: Seed controlling both the sampled decisions and the noise.
        :return: List of dicts holding every context, action and outcome field.
        """
        rng: np.random.Generator = np.random.default_rng(seed)

        account_size: np.ndarray = rng.uniform(0.5, 10.0, num_rows)  # $M of annual revenue
        urgency: np.ndarray = rng.uniform(0.0, 1.0, num_rows)

        # Historical decisions vary widely, which is what gives the surrogate
        # something to learn from across the whole action space.
        senior_staff_ratio: np.ndarray = rng.uniform(0.05, 0.95, num_rows)
        automation_investment: np.ndarray = rng.uniform(0.0, 1.0, num_rows)

        margin_pct: np.ndarray = (
            22.0
            + 6.0 * automation_investment
            - 14.0 * senior_staff_ratio
            + 0.45 * account_size
            + rng.normal(0.0, 0.8, num_rows)
        )
        delivery_risk: np.ndarray = (
            0.55
            - 0.38 * senior_staff_ratio
            - 0.10 * automation_investment
            + 0.22 * urgency
            + rng.normal(0.0, 0.02, num_rows)
        )
        time_to_value_weeks: np.ndarray = (
            14.0
            - 5.0 * senior_staff_ratio
            + 7.0 * automation_investment
            + 0.35 * account_size
            + rng.normal(0.0, 0.5, num_rows)
        )

        return [
            {
                "account_size": float(account_size[i]),
                "urgency": float(urgency[i]),
                "senior_staff_ratio": float(senior_staff_ratio[i]),
                "automation_investment": float(automation_investment[i]),
                "margin_pct": float(margin_pct[i]),
                "delivery_risk": float(delivery_risk[i]),
                "time_to_value_weeks": float(time_to_value_weeks[i]),
            }
            for i in range(num_rows)
        ]

    @staticmethod
    def specification() -> dict[str, Any]:
        """
        Describe the sample problem in the shape LoadDecisionProblem stores.

        :return: Dict naming the context, action and outcome fields plus their direction.
        """
        return {
            "context_fields": list(SampleData.CONTEXT_FIELDS),
            "action_fields": list(SampleData.ACTION_FIELDS),
            "outcome_fields": list(SampleData.OUTCOME_FIELDS),
            "maximize": list(SampleData.OUTCOME_MAXIMIZE),
        }
