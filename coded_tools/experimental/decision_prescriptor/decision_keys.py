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


# A data-only holder for the names the tools in this network share.
# pylint: disable=too-few-public-methods
class DecisionKeys:
    """
    The sly_data keys under which the Decision Prescriptor tools hand state to one another.

    State moves between stages through sly_data, neuro-san's channel for values that
    must never enter an LLM prompt. A fitted model and a few hundred candidate
    strategies belong there: they are large, they are exact, and passing them as chat
    text would both blow the context window and risk mangling them.
    """

    # Historical records, written by LoadDecisionProblem.
    DATASET: str = "decision_dataset"
    # Which fields are context, action and outcome, written by LoadDecisionProblem.
    SPEC: str = "decision_spec"
    # The fitted RidgeSurrogate, written by FitSurrogate.
    SURROGATE: str = "decision_surrogate"
    # The evolved front and its history, written by EvolvePrescriptors.
    RESULT: str = "decision_result"
