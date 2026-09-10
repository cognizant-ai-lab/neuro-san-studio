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

import logging
import os
from typing import Any

# The sly_data key under which a Bring-Your-Own-Key (BYOK) client sends its provider
# API keys. This is the same convention neuro-san uses for agents whose llm_config says
# "<provider>_api_key": "sly_data" -- see config/byok_llm_config.hocon.
LLM_CONFIG_KEY = "llm_config"


# pylint: disable=too-few-public-methods
class ByokApiKey:
    """
    Resolves a provider API key for coded tools that call an LLM provider directly.

    neuro-san's BYOK support only covers the agents' own llm_config: the client sends its
    keys in sly_data["llm_config"] and the LLM factory substitutes them into the agent's
    config before the chat model is built. Coded tools that instantiate their own provider
    clients (OpenAI and Anthropic built-in tools, Gemini image generation, OpenAI video
    generation, ...) never went through that path, so they authenticated from environment
    variables only and either failed on a key-less BYOK deployment or silently billed the
    platform's key. This class gives those tools the same precedence rule as agents: the
    user's key from sly_data wins and the server's environment variable is the fallback.
    """

    logger = logging.getLogger(__name__)

    @staticmethod
    def resolve(sly_data: dict[str, Any] | None, key_name: str, env_var: str) -> str | None:
        """
        Look up a provider API key, preferring the BYOK value in sly_data over the environment.

        :param sly_data: The sly_data dictionary handed to the coded tool. May be None or
                malformed; anything that is not a dict holding a dict under "llm_config" is
                treated as "no key provided" so the environment fallback still applies.
        :param key_name: The entry to read inside sly_data["llm_config"], using the names
                neuro-san uses for agents: "openai_api_key", "anthropic_api_key" or
                "google_api_key".
        :param env_var: The environment variable to fall back to when sly_data has no usable
                value, e.g. "OPENAI_API_KEY".
        :return: The resolved key, or None when neither source provides one.
        """
        llm_config: Any = None
        if isinstance(sly_data, dict):
            llm_config = sly_data.get(LLM_CONFIG_KEY)

        value: Any = None
        if isinstance(llm_config, dict):
            value = llm_config.get(key_name)

        if isinstance(value, str):
            # Keys end up in HTTP headers, which reject surrounding whitespace, so strip
            # exactly like neuro-san does for agent keys. A blank string is "not provided".
            stripped: str = value.strip()
            if stripped:
                return stripped
        elif value is not None:
            # A list/dict/number here is a client-side bug. Fall back rather than send
            # something the provider will reject with a confusing error, and say why.
            ByokApiKey.logger.warning(
                "Ignoring non-string %s.%s in sly_data (got %s); falling back to %s",
                LLM_CONFIG_KEY,
                key_name,
                type(value).__name__,
                env_var,
            )

        return os.getenv(env_var)
