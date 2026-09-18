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
import os
from unittest import TestCase
from unittest.mock import patch

from neuro_san_studio.coded_tools.utils.byok_api_key import LLM_CONFIG_KEY
from neuro_san_studio.coded_tools.utils.byok_api_key import ByokApiKey

KEY_NAME = "openai_api_key"
# A private env var name so a real provider key in the developer's shell can never leak
# into these assertions.
ENV_VAR = "TEST_BYOK_API_KEY"
LOGGER_NAME = "neuro_san_studio.coded_tools.utils.byok_api_key"


class TestByokApiKey(TestCase):
    """
    Unit tests for ByokApiKey.resolve.

    Pins the precedence rule shared by every coded tool that calls an LLM provider directly:
    a usable key in sly_data["llm_config"] wins, the environment variable is the fallback, and
    anything malformed in sly_data degrades to the fallback instead of raising.
    """

    def test_sly_data_key_wins_over_env(self) -> None:
        """
        A key in sly_data is returned even when the environment variable is also set.
        """
        sly_data: dict = {LLM_CONFIG_KEY: {KEY_NAME: "sly-key"}}
        with patch.dict(os.environ, {ENV_VAR: "env-key"}):
            self.assertEqual(ByokApiKey.resolve(sly_data, KEY_NAME, ENV_VAR), "sly-key")

    def test_env_used_when_llm_config_absent(self) -> None:
        """
        Without an llm_config entry in sly_data the environment variable is used.
        """
        with patch.dict(os.environ, {ENV_VAR: "env-key"}):
            self.assertEqual(ByokApiKey.resolve({}, KEY_NAME, ENV_VAR), "env-key")

    def test_env_used_when_key_absent_in_llm_config(self) -> None:
        """
        An llm_config that only carries another provider's key falls back to the environment.
        """
        sly_data: dict = {LLM_CONFIG_KEY: {"anthropic_api_key": "other-key"}}
        with patch.dict(os.environ, {ENV_VAR: "env-key"}):
            self.assertEqual(ByokApiKey.resolve(sly_data, KEY_NAME, ENV_VAR), "env-key")

    def test_none_sly_data_uses_env(self) -> None:
        """
        A None sly_data (tool invoked outside a network) falls back to the environment.
        """
        with patch.dict(os.environ, {ENV_VAR: "env-key"}):
            self.assertEqual(ByokApiKey.resolve(None, KEY_NAME, ENV_VAR), "env-key")

    def test_non_dict_sly_data_uses_env(self) -> None:
        """
        A sly_data that is not a dict is treated as "no key provided".
        """
        with patch.dict(os.environ, {ENV_VAR: "env-key"}):
            self.assertEqual(ByokApiKey.resolve("not a dict", KEY_NAME, ENV_VAR), "env-key")

    def test_non_dict_llm_config_uses_env(self) -> None:
        """
        An llm_config that is a bare string instead of a dict is treated as "no key provided".
        """
        sly_data: dict = {LLM_CONFIG_KEY: "sk-raw-string"}
        with patch.dict(os.environ, {ENV_VAR: "env-key"}):
            self.assertEqual(ByokApiKey.resolve(sly_data, KEY_NAME, ENV_VAR), "env-key")

    def test_whitespace_is_stripped(self) -> None:
        """
        Surrounding whitespace is removed so the key is safe to put in an HTTP header.
        """
        sly_data: dict = {LLM_CONFIG_KEY: {KEY_NAME: "  sly-key\n"}}
        with patch.dict(os.environ, {ENV_VAR: "env-key"}):
            self.assertEqual(ByokApiKey.resolve(sly_data, KEY_NAME, ENV_VAR), "sly-key")

    def test_blank_string_uses_env(self) -> None:
        """
        A whitespace-only key counts as "not provided" and falls back to the environment.
        """
        sly_data: dict = {LLM_CONFIG_KEY: {KEY_NAME: "   "}}
        with patch.dict(os.environ, {ENV_VAR: "env-key"}):
            self.assertEqual(ByokApiKey.resolve(sly_data, KEY_NAME, ENV_VAR), "env-key")

    def test_non_string_value_is_ignored_with_warning(self) -> None:
        """
        A non-string key (a client bug) is ignored with a warning and the environment is used.
        """
        sly_data: dict = {LLM_CONFIG_KEY: {KEY_NAME: ["not", "a", "string"]}}
        with patch.dict(os.environ, {ENV_VAR: "env-key"}), self.assertLogs(LOGGER_NAME, level="WARNING") as logs:
            result: str | None = ByokApiKey.resolve(sly_data, KEY_NAME, ENV_VAR)
        self.assertEqual(result, "env-key")
        self.assertEqual(len(logs.output), 1)
        self.assertIn("Ignoring non-string llm_config.openai_api_key", logs.output[0])
        self.assertIn("list", logs.output[0])

    def test_returns_none_when_no_source(self) -> None:
        """
        With neither a sly_data key nor the environment variable set, None is returned.
        """
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(ByokApiKey.resolve({}, KEY_NAME, ENV_VAR))
