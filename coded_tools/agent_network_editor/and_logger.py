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

from logging import Logger
from os import environ

from leaf_common.logging.conditional_logger import ConditionalLogger


class AndLogger(ConditionalLogger):
    """
    A logger that is always enabled which can redirect INFO logs to DEBUG upon
    an environment variable setting. The idea is to get rid of most of the INFO chatter
    in production logs.
    """

    def __init__(self, logger: Logger):
        """
        Constructor

        :param logger: The wrapped logger to redirect write() calls to.
        """
        env_var: str = "AGENT_NETWORK_DESIGNER_LOG_LEVEL"
        super().__init__(logger, env_var)

        log_level: str = environ.get(env_var, "INFO").strip().upper()
        self.use_info: bool = log_level == "INFO"

    def should_log(self) -> bool:
        """
        :return: True if this logger should log
        """
        # We're always going to log. It's a matter of what level.
        return True

    def info(self, msg, *args, **kwargs):
        """
        Log 'msg % args' with severity 'INFO'.

        To pass exception information, use the keyword argument exc_info with
        a true value, e.g.

        logger.info("Houston, we have a %s", "notable problem", exc_info=True)
        """
        if self.use_info:
            super().info(msg, *args, **kwargs)
        else:
            super().debug(msg, *args, **kwargs)
