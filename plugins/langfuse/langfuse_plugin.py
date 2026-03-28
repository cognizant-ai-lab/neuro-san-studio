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
from contextvars import ContextVar
from typing import Any
from typing import Type

from langchain_core.tracers.context import register_configure_hook

# Use lazy loading of types to avoid dependency bloat for stuff most people don't need.
from leaf_common.config.resolver_util import ResolverUtil

from plugins.base_plugin import BasePlugin


class LangfusePlugin:
    """
    Manages Langfuse initialization for tracing and observability.

    Handles:
    - LangChain callback handler integration (traces all LLM providers)
    - Process-local initialization state tracking
    - Environment variable management
    """

    def __init__(self) -> None:
        """Initialize the LangfusePlugin."""
        self._initialized = False
        self._logger = logging.getLogger(__name__)
        self._langfuse_client = None
        self._callback_handler = None

    @staticmethod
    def _get_bool_env(var_name: str, default: bool) -> bool:
        """Parse a boolean environment variable.

        Args:
            var_name: Environment variable name
            default: Default value if variable is not set

        Returns:
            Boolean value parsed from environment variable
        """
        val = os.getenv(var_name)
        if val is None:
            return default
        return val.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _is_valid_key() -> bool:
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

            print("[Langfuse] LangChain CallbackHandler registered globally")
            return True
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._logger.error("Failed to create Langfuse client or CallbackHandler: %s", exc)
            return False

    def initialize(self) -> None:
        """Initialize Langfuse observability if enabled.

        Checks:
        - Whether already initialized (prevents double-init)
        - LANGFUSE_ENABLED environment variable

        Attempts LangChain CallbackHandler setup which automatically
        traces all LLM providers.

        This method is idempotent and safe to call multiple times.
        """
        # Do NOTHING, not even log, if the plugin is not enabled.
        # The plugin is NOT enabled, so it should not appear in the logs
        if not self._get_bool_env("LANGFUSE_ENABLED", False):
            return

        print(f"[Langfuse] initialize called, PID={os.getpid()}")
        print(f"[Langfuse] _initialized={self._initialized}")
        print(f"[Langfuse] LANGFUSE_ENABLED={os.getenv('LANGFUSE_ENABLED')}")

        if self._initialized:
            print(f"[Langfuse] Already initialized in this process, skipping (PID={os.getpid()})")
            return

        try:
            print(f"[Langfuse] Attempting Langfuse setup (PID={os.getpid()})")
            setup_successful = self._try_langfuse_setup()
            if setup_successful:
                print(f"[Langfuse] Setup succeeded (PID={os.getpid()})")
                print(f"[Langfuse] Traces will be sent to: {os.getenv('LANGFUSE_HOST', 'https://cloud.langfuse.com')}")
                print(f"[Langfuse] Project: {os.getenv('LANGFUSE_PROJECT_NAME', 'default')}")
                self._initialized = True
                print(f"[Langfuse] Setup successful (PID={os.getpid()})")
            else:
                print(f"[Langfuse] Setup failed (PID={os.getpid()})")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(f"[Langfuse] Initialization FAILED: {exc} (PID={os.getpid()})")
            self._logger.warning("Langfuse initialization failed: %s", exc)

    @property
    def is_initialized(self) -> bool:
        """Check if Langfuse has been initialized.

        Returns:
            True if initialized, False otherwise
        """
        return self._initialized

    def shutdown(self) -> None:
        """Shutdown Langfuse client and flush remaining traces."""
        if not self._initialized:
            return
        print("[Langfuse] Shutting down...")
        try:
            self._langfuse_client.flush()
            self._initialized = False
            self._callback_handler = None
            self._langfuse_client = None
            print("[Langfuse] Shutdown complete")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._logger.warning("Failed to shutdown Langfuse cleanly: %s", exc)


class LangfuseStudioPlugin(LangfusePlugin, BasePlugin):
    """Studio plugin that integrates Langfuse for tracing and monitoring."""

    def __init__(self):
        """Initialize the Langfuse Studio plugin."""
        LangfusePlugin.__init__(self)
        BasePlugin.__init__(self, "LangfuseStudio")

    def cleanup(self):
        """Cleanup and shutdown the Langfuse plugin."""
        return self.shutdown()
