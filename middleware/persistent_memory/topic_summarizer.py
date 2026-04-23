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

"""
LLM-powered summarizer for one topic at a time. Errors keep the original.
"""

from __future__ import annotations

import logging
from logging import Logger
from typing import Any
from typing import ClassVar

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI


class TopicSummarizer:
    """
    Summarizes a single topic's accumulated content via ChatOpenAI.

    :param model_name:      Which OpenAI model to use.
    :param personalization: Extra sentence appended to the prompt; optional.
    :param max_topic_size:  Size threshold above which summarization kicks in;
                            ``0`` disables it entirely.
    """

    DEFAULT_MODEL: ClassVar[str] = "gpt-5.4-mini"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        personalization: str = "",
        max_topic_size: int = 0,
    ) -> None:
        self.logger: Logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._model_name: str = (model_name or self.DEFAULT_MODEL).strip()
        self._personalization: str = (personalization or "").strip()
        self._max_topic_size: int = max(0, int(max_topic_size))

    def should_summarize(self, content: str) -> bool:
        """
        Whether ``content`` is over the configured size threshold.

        :param content: The topic's current content to check.
        :return: ``True`` if summarization should run, else ``False``.
        """
        if self._max_topic_size <= 0:
            return False
        return len(content) > self._max_topic_size

    async def summarize_topic(self, topic: str, content: str) -> str:
        """
        Ask the LLM to summarize ``content``. Returns the original if anything fails.

        :param topic:   Topic name, used in the prompt for context.
        :param content: Current topic content to compress.
        :return: The summarized content, or the original if summarization fails.
        """
        prompt: str = (
            f"Summarize the following timestamped facts about '{topic}' into a "
            "concise summary. Preserve the most recent and most important details. "
            "Keep names, specific preferences, and key facts. "
            "Drop redundant or outdated entries. "
            "Return ONLY the summary, no preamble."
        )
        if self._personalization:
            prompt = f"Important instructions:\n{self._personalization}\n\n{prompt}"
        prompt = f"{prompt}\n\n{content}"

        try:
            summary: str = await self._invoke_summarizer(prompt)
        # Summarization is best-effort — a failure from the LLM SDK (network,
        # auth, rate limit, bad response shape) must not discard memory.
        except Exception:  # pylint: disable=broad-except
            self.logger.warning(
                "Failed to summarize topic '%s'. Keeping original content.",
                topic,
                exc_info=True,
            )
            return content
        if not summary:
            return content
        self.logger.debug(
            "Summarized topic '%s' from %d to %d chars",
            topic,
            len(content),
            len(summary),
        )
        return summary

    async def _invoke_summarizer(self, prompt: str) -> str:
        """
        Call the LLM. May raise any SDK error — caller handles it.

        :param prompt: Full prompt to send to the chat model.
        :return: The model's text response, stripped.
        """
        llm: Any = ChatOpenAI(model=self._model_name)
        response: Any = await llm.ainvoke([HumanMessage(content=prompt)])
        return self._extract_text(response)

    @staticmethod
    def _extract_text(response: Any) -> str:
        """
        Pull the text out of a chat-model response, stripped.

        :param response: The LangChain chat-model response object.
        :return: The response's text content, stripped.
        """
        content: Any = getattr(response, "content", "") or ""
        return str(content).strip()
