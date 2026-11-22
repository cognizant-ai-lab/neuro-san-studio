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

import json
import re
from datetime import date
from logging import Logger
from logging import getLogger
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage
from task_verification.pto_provenance.turn_checker import TurnChecker


class TurnExtractor:
    """
    Turns free text into the small structured fields TurnChecker compares. This is the only place an LLM is used.

    Two separate, narrow calls, so neither can be swayed by the thing it is being checked against:
      intent()  reads only the user's messages (never the agent's answer, which may restate the request wrongly)
      claim()   reads only the agent's final message (never the database evidence)
    Both ask for JSON and fall back to "unknown" when the reply cannot be read. Unknown fields make TurnChecker
    answer "unclear", never "consistent", so a confused extractor cannot hide a problem; at worst it raises a
    false alarm.

    Each call's raw reply (or the error, if the call failed) is kept in self.raw, keyed "intent" and "claim", and
    the model in self.model, so the caller can record them next to the verdict. A wrong verdict can then be traced
    to the extraction (the raw reply already says the wrong thing) or to the graph (the reply is right, the evidence
    disagrees) without re-running anything.
    """

    INTENT_PROMPT: str = """
You extract what an employee asked an HR assistant to do. Today is {today}.
Read only the employee's messages below and reply with one JSON object, nothing else:
{{"action": "schedule_pto" or "other",
  "employee_id": the employee ID they gave (e.g. "E-1042") or null,
  "start_date": "YYYY-MM-DD" or null,
  "end_date": "YYYY-MM-DD" or null}}
Use "schedule_pto" only if they asked to book or schedule time off (PTO, vacation, leave, a day off).
Resolve relative dates ("tomorrow", "next Friday") against today. For a single day, give it as start_date and leave
end_date null. Use null for anything they did not state clearly; never guess.
"""

    CLAIM_PROMPT: str = """
You read one message an HR assistant sent to an employee and classify what it says about a time-off request.
Reply with one JSON object, nothing else: {"claim": one of "success", "failure", "question", "none"}
  success   the message says the time off was booked, scheduled, submitted or confirmed
  failure   the message says it could not be done or was not done
  question  the message asks the employee for more information before doing it
  none      the message says nothing about booking time off
Judge only what the message tells the employee, not whether it is true.
"""

    def __init__(self, llm: BaseChatModel) -> None:
        """:param llm: Any langchain chat model. Use temperature 0 so the same text gives the same fields."""
        self.llm: BaseChatModel = llm
        self.logger: Logger = getLogger(__name__)
        # The model's name, as the chat model class reports it (ChatAnthropic and ChatGoogleGenerativeAI: "model").
        self.model: str = str(getattr(llm, "model", None) or getattr(llm, "model_name", None) or type(llm).__name__)
        self.raw: dict[str, str | None] = {"intent": None, "claim": None}

    async def intent(self, user_messages: list[str], today: date | None = None) -> dict[str, Any]:
        """
        :param user_messages: Everything the user said this session, oldest first (later turns may add details).
        :param today: The date to resolve "tomorrow" against; defaults to today.
        :return: {"action", "employee_id", "start_date", "end_date"}, with None for anything unknown.
        """
        unknown: dict[str, Any] = {"action": None, "employee_id": None, "start_date": None, "end_date": None}
        self.raw["intent"] = None
        if not user_messages:
            return unknown
        prompt: str = self.INTENT_PROMPT.format(today=(today or date.today()).isoformat())
        transcript: str = "\n".join(f"Employee: {text}" for text in user_messages)
        parsed: dict[str, Any] | None = await self._ask("intent", prompt, transcript)
        if parsed is None:
            return unknown

        result: dict[str, Any] = dict(unknown)
        if parsed.get("action") in (TurnChecker.ACTION, "other"):
            result["action"] = parsed["action"]
        for field in TurnChecker.FIELDS:
            value: Any = parsed.get(field)
            if isinstance(value, str) and value.strip():
                result[field] = value.strip()
        # A date the model did not write as YYYY-MM-DD is treated as unknown rather than compared as text.
        for field in ("start_date", "end_date"):
            if result[field] is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", result[field]):
                result[field] = None
        return result

    async def claim(self, final_message: str) -> str:
        """
        :param final_message: The agent's last message to the user this turn.
        :return: success | failure | question | none, or "unknown" if the reply could not be read.
        """
        self.raw["claim"] = None
        if not final_message.strip():
            return "none"
        parsed: dict[str, Any] | None = await self._ask("claim", self.CLAIM_PROMPT, final_message)
        value: Any = (parsed or {}).get("claim")
        return value if value in TurnChecker.CLAIMS else "unknown"

    async def _ask(self, which: str, instructions: str, text: str) -> dict[str, Any] | None:
        """
        Send one prompt, keep the raw reply in self.raw[which], and return the first JSON object in the reply,
        or None if there is none.
        """
        try:
            reply: Any = await self.llm.ainvoke([SystemMessage(instructions), HumanMessage(text)])
        except Exception as error:  # pylint: disable=broad-exception-caught
            # A failed check must not break the user's chat; it is recorded as unknown, which TurnChecker flags.
            self.logger.warning("Turn extractor call failed: %s", error)
            self.raw[which] = f"call failed: {type(error).__name__}: {error}"
            return None
        content: Any = reply.content
        if isinstance(content, list):  # providers may return a list of content blocks
            content = "".join(block.get("text", "") if isinstance(block, dict) else str(block) for block in content)
        self.raw[which] = str(content)
        match: re.Match[str] | None = re.search(r"\{.*\}", str(content), re.DOTALL)
        if match is None:
            return None
        try:
            parsed: Any = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
