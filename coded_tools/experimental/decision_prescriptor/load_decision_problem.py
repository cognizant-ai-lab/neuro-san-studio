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
import logging
from typing import Any

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.experimental.decision_prescriptor.decision_keys import DecisionKeys
from coded_tools.experimental.decision_prescriptor.sample_data import SampleData
from coded_tools.experimental.decision_prescriptor.training_arrays import TrainingArrays

logger = logging.getLogger(__name__)


class LoadDecisionProblem(CodedTool):
    """
    Stage 1 of registries/experimental/decision_prescriptor.hocon: load historical
    records plus which fields play which role into sly_data.

    Everything numeric in this network happens in deterministic Python; the agents
    decide what to model and explain the result, and are never asked for a number.
    """

    def invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> str:
        """
        Put a dataset and its field specification into sly_data.

        Supplying no rows loads the bundled synthetic delivery-staffing example,
        so the network is runnable without any data preparation.

        :param args: May contain "rows" (list of record dicts), "context_fields",
            "action_fields", "outcome_fields" and "maximize" (list of booleans).
        :param sly_data: Out-of-band channel; the dataset and spec are written here.
        :return: A short human-readable confirmation, or a message starting with "Error:".
        """
        rows: list[dict[str, Any]] | None = args.get("rows")

        if not rows:
            rows = SampleData.generate()
            spec: dict[str, Any] = SampleData.specification()
        else:
            spec = {
                "context_fields": args.get("context_fields") or [],
                "action_fields": args.get("action_fields") or [],
                "outcome_fields": args.get("outcome_fields") or [],
                "maximize": args.get("maximize") or [],
            }
            missing: list[str] = [
                name for name in ("context_fields", "action_fields", "outcome_fields") if not spec.get(name)
            ]
            if missing:
                return self._error(f"must name {', '.join(missing)} when supplying your own rows.")
            if len(spec.get("maximize")) != len(spec.get("outcome_fields")):
                return self._error(
                    f"'maximize' has {len(spec.get('maximize'))} entries but there are "
                    f"{len(spec.get('outcome_fields'))} outcome fields; one direction is needed per outcome."
                )

        try:
            TrainingArrays.build(
                rows, spec.get("context_fields"), spec.get("action_fields"), spec.get("outcome_fields")
            )
        except ValueError as error:
            return self._error(str(error))

        sly_data[DecisionKeys.DATASET] = rows
        sly_data[DecisionKeys.SPEC] = spec

        directions: str = ", ".join(
            f"{name} ({'maximize' if flag else 'minimize'})"
            for name, flag in zip(spec.get("outcome_fields"), spec.get("maximize"))
        )
        logger.info("Loaded %d decision records", len(rows))
        return (
            f"Loaded {len(rows)} records. "
            f"Context: {', '.join(spec.get('context_fields'))}. "
            f"Decisions: {', '.join(spec.get('action_fields'))}. "
            f"Outcomes: {directions}."
        )

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> str:
        """
        Run invoke in a worker thread, because validating the records is blocking work.

        :param args: See invoke.
        :param sly_data: See invoke.
        :return: See invoke.
        """
        return await asyncio.to_thread(self.invoke, args, sly_data)

    @staticmethod
    def _error(message: str) -> str:
        """
        Log a refused request and phrase it for the agent that called the tool.

        :param message: What was wrong with the request.
        :return: The message prefixed with "Error:", which the front man relays and stops on.
        """
        logger.warning("LoadDecisionProblem refused the request: %s", message)
        return f"Error: {message}"
