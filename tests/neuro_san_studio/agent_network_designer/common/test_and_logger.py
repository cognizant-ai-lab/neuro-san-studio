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
from logging import WARNING
from logging import Logger
from unittest import TestCase
from unittest.mock import MagicMock
from unittest.mock import patch

from neuro_san_studio.agent_network_designer.common.and_logger import AndLogger


class TestAndLogger(TestCase):
    """
    Tests for AndLogger, which always logs and sends info() to INFO or DEBUG based on an environment variable.
    Each test wraps a mock Logger and checks which of its methods AndLogger called.
    """

    ENV_VAR: str = "AGENT_NETWORK_DESIGNER_VERBOSE"

    def make_logger(self, verbose: str | None) -> tuple[AndLogger, MagicMock]:
        """
        Build an AndLogger around a mock Logger with the environment variable set or unset.

        :param verbose: The value for the environment variable, or None to leave it unset
        :return: The AndLogger and the mock Logger it wraps
        """
        wrapped: MagicMock = MagicMock(spec=Logger)
        # AndLogger reads the environment variable once, in its constructor.
        with patch.dict(os.environ):
            os.environ.pop(self.ENV_VAR, None)
            if verbose is not None:
                os.environ[self.ENV_VAR] = verbose
            and_logger: AndLogger = AndLogger(wrapped)
        return and_logger, wrapped

    def test_should_log_accepts_message_and_level(self) -> None:
        """
        should_log() takes the message and level the base class passes, and always says yes.
        """
        and_logger: AndLogger
        and_logger, _ = self.make_logger("false")

        self.assertTrue(and_logger.should_log("hello", WARNING))
        self.assertTrue(and_logger.should_log())

    def test_info_logs_at_info_when_verbose(self) -> None:
        """
        info() logs at INFO when the environment variable is "true".
        """
        and_logger: AndLogger
        wrapped: MagicMock
        and_logger, wrapped = self.make_logger("true")

        and_logger.info("hello %s", "x")

        wrapped.info.assert_called_once_with("hello %s", "x")
        wrapped.debug.assert_not_called()

    def test_info_logs_at_info_when_unset(self) -> None:
        """
        info() logs at INFO when the environment variable is unset.
        """
        and_logger: AndLogger
        wrapped: MagicMock
        and_logger, wrapped = self.make_logger(None)

        and_logger.info("hello %s", "x")

        wrapped.info.assert_called_once_with("hello %s", "x")
        wrapped.debug.assert_not_called()

    def test_info_logs_at_debug_when_not_verbose(self) -> None:
        """
        info() logs at DEBUG when the environment variable is "false".
        """
        and_logger: AndLogger
        wrapped: MagicMock
        and_logger, wrapped = self.make_logger("false")

        and_logger.info("hello %s", "x")

        wrapped.debug.assert_called_once_with("hello %s", "x")
        wrapped.info.assert_not_called()

    def test_always_info_logs_at_info_when_not_verbose(self) -> None:
        """
        always_info() logs at INFO even when the environment variable is "false".
        """
        and_logger: AndLogger
        wrapped: MagicMock
        and_logger, wrapped = self.make_logger("false")

        and_logger.always_info("hello %s", "x")

        wrapped.info.assert_called_once_with("hello %s", "x")
        wrapped.debug.assert_not_called()

    def test_other_levels_log_when_not_verbose(self) -> None:
        """
        debug(), warning(), error(), exception(), critical() and log() reach the wrapped Logger
        even when the environment variable is "false".
        """
        and_logger: AndLogger
        wrapped: MagicMock
        and_logger, wrapped = self.make_logger("false")

        and_logger.debug("debug %s", "x")
        and_logger.warning("warning %s", "x")
        and_logger.error("error %s", "x")
        and_logger.exception("exception %s", "x")
        and_logger.critical("critical %s", "x")
        and_logger.log(WARNING, "log %s", "x")

        wrapped.debug.assert_called_once_with("debug %s", "x")
        wrapped.warning.assert_called_once_with("warning %s", "x")
        wrapped.error.assert_called_once_with("error %s", "x")
        wrapped.exception.assert_called_once_with("exception %s", "x", exc_info=True)
        wrapped.critical.assert_called_once_with("critical %s", "x")
        wrapped.log.assert_called_once_with(WARNING, "log %s", "x")
