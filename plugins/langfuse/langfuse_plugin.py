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
Langfuse plugin for tracing and observability.

Handles:
- LangChain callback handler integration (traces all LLM providers)
- Process-local initialization state tracking
- Environment variable management
"""

import os
from contextvars import ContextVar
from typing import Any
from typing import Type

from langchain_core.tracers.context import register_configure_hook

# Use lazy loading of types to avoid dependency bloat for stuff most people don't need.
from leaf_common.config.resolver_util import ResolverUtil

from neuro_san_studio.interfaces.plugins import BasePlugin


class LangfusePlugin(BasePlugin):
    """Plugin that integrates Langfuse for tracing and monitoring."""

    def __init__(self, args: dict = None):
        """Initialize the Langfuse plugin.

        Args:
            args: Optional dictionary of arguments for the plugin.
        """
        super().__init__("Langfuse", args)
        self._initialized = False
        self._langfuse_client = None
        self._callback_handler = None

    @staticmethod
    def _is_valid_key() -> bool:
        """Check if Langfuse API keys are configured.

        Returns:
            True if both secret and public keys are set, False otherwise
        """
        secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY")

        if not secret_key or not public_key:
            return False
        return True

    def _try_langfuse_setup(self) -> bool:
        """Try setting up Langfuse via LangChain CallbackHandler.

        The CallbackHandler reads LANGFUSE_SECRET_KEY, LANGFUSE_PUBLIC_KEY,
        and LANGFUSE_HOST from environment variables automatically and
        traces all LLM providers through LangChain's callback system.

        Returns:
            True if Langfuse setup was successful, False otherwise
        """

        # Lazily load get_client and CallbackHandler
        get_client_fn = ResolverUtil.create_type(
            "langfuse.get_client",
            raise_if_not_found=False,
            install_if_missing="langfuse",
        )
        callback_handler_class: Type[Any] = ResolverUtil.create_type(
            "langfuse.langchain.CallbackHandler",
            raise_if_not_found=False,
            install_if_missing="langfuse",
        )

        if get_client_fn is None or callback_handler_class is None:  # pragma: no cover
            self._logger.error("Langfuse package not installed")
            return False

        if not self._is_valid_key():
            self._logger.error("Langfuse keys not configured. Set LANGFUSE_SECRET_KEY and LANGFUSE_PUBLIC_KEY")
            return False

        try:
            self._langfuse_client = get_client_fn()
            self._callback_handler = callback_handler_class()

            # Use LangChain's register_configure_hook to register the Langfuse
            # CallbackHandler globally with inheritable=True. This hooks into
            # LangChain's internal callback configuration system — whenever any
            # Runnable.ainvoke() or .invoke() is called (including inside
            # neuro_san's RunContextRunnable), LangChain automatically includes
            # the Langfuse handler in the callbacks list. No explicit
            # config={"callbacks": [handler]} needed.
            langfuse_ctx_var = ContextVar("langfuse_handler", default=None)
            langfuse_ctx_var.set(self._callback_handler)
            register_configure_hook(langfuse_ctx_var, inheritable=True)

            self._logger.info("LangChain CallbackHandler registered globally")
            return True
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._logger.error("Failed to create Langfuse client or CallbackHandler: %s", exc)
            return False

    def _do_initialize(self) -> None:
        """Initialize Langfuse observability.

        Checks whether already initialized (prevents double-init).

        Attempts LangChain CallbackHandler setup which automatically
        traces all LLM providers.

        This method is idempotent and safe to call multiple times.
        """
        if self._initialized:
            self._logger.info("Already initialized, skipping (PID=%s)", os.getpid())
            return

        try:
            setup_successful = self._try_langfuse_setup()
            if setup_successful:
                self._logger.info(
                    "Traces will be sent to: %s", os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
                )
                self._logger.info("Project: %s", os.getenv("LANGFUSE_PROJECT_NAME", "default"))
                self._initialized = True
            else:
                self._logger.warning("Setup failed (PID=%s)", os.getpid())
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._logger.warning("Initialization failed: %s", exc)

    @property
    def is_initialized(self) -> bool:
        """Check if Langfuse has been initialized.

        Returns:
            True if initialized, False otherwise
        """
        return self._initialized

    def _do_cleanup(self) -> None:
        """Shutdown Langfuse client and flush remaining traces."""
        if not self._initialized:
            return
        try:
            self._langfuse_client.flush()
            self._initialized = False
            self._callback_handler = None
            self._langfuse_client = None
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._logger.warning("Failed to shutdown cleanly: %s", exc)
