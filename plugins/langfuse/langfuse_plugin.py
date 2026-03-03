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
from typing import Optional
from typing import Type

# Use lazy loading of types to avoid dependency bloat for stuff most people don't need.
from leaf_common.config.resolver_util import ResolverUtil


class LangfusePlugin:
    """
    Manages Langfuse initialization for tracing and observability.

    Handles:
    - Langfuse client configuration
    - SDK instrumentation (OpenAI, LangChain, Anthropic, etc.)
    - Process-local initialization state tracking
    - Environment variable management
    """

    def __init__(self, config: Optional[dict] = None) -> None:
        """Initialize the LangfusePlugin with the optional configuration.

        Args:
            config: Optional configuration dictionary with langfuse settings
        """
        self._initialized = False
        self._logger = logging.getLogger(__name__)
        self.config = config or {}
        self.langfuse_client = None

    @staticmethod
    def get_default_config() -> dict:
        """Get default Langfuse configuration from environment variables.

        Returns:
            Dictionary with default Langfuse configuration values
        """
        return {
            # Langfuse defaults
            "langfuse_enabled": os.getenv("LANGFUSE_ENABLED", "false"),
            "langfuse_use_existing": os.getenv("LANGFUSE_USE_EXISTING", "false"),
            "langfuse_secret_key": os.getenv("LANGFUSE_SECRET_KEY", ""),
            "langfuse_public_key": os.getenv("LANGFUSE_PUBLIC_KEY", ""),
            "langfuse_host": os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
            "langfuse_project_name": os.getenv("LANGFUSE_PROJECT_NAME", "default"),
            "langfuse_release": os.getenv("LANGFUSE_RELEASE", "dev"),
            "langfuse_debug": os.getenv("LANGFUSE_DEBUG", "false"),
            "langfuse_sample_rate": float(os.getenv("LANGFUSE_SAMPLE_RATE", "1.0")),
        }

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

    def _configure_langfuse_client(self) -> None:
        """Configure Langfuse client with API keys and settings.

        Sets up:
        - API authentication (public/secret keys)
        - Host endpoint
        - Project/release metadata
        - Debug settings
        """
        # Lazily load Langfuse class
        langfuse_class: Type[Any] = ResolverUtil.create_type(
            "langfuse.Langfuse",
            raise_if_not_found=False,
            install_if_missing="langfuse",
        )

        if langfuse_class is None:  # pragma: no cover
            self._logger.warning("Langfuse package not installed")
            return

        secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY")

        if not secret_key or not public_key:
            self._logger.warning("Langfuse keys not configured. Set LANGFUSE_SECRET_KEY and LANGFUSE_PUBLIC_KEY")
            return

        host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        release = os.getenv("LANGFUSE_RELEASE", "dev")
        debug = self._get_bool_env("LANGFUSE_DEBUG", False)

        try:
            self.langfuse_client = langfuse_class(
                secret_key=secret_key,
                public_key=public_key,
                host=host,
                release=release,
                debug=debug,
            )
            self._logger.info("Langfuse client configured successfully")

            # Patch OpenAI module globally to use Langfuse's instrumented version
            self._patch_openai_module()

        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._logger.error("Failed to configure Langfuse client: %s", exc)

    @staticmethod
    def _patch_openai_module() -> None:
        """Patch the openai module with Langfuse's instrumented version.
        
        This replaces the global openai module so that all OpenAI calls
        are automatically traced by Langfuse.
        """
        try:
            import sys  # pylint: disable=import-outside-toplevel
            import importlib  # pylint: disable=import-outside-toplevel

            # Import langfuse.openai module (not a class, so we use importlib)
            langfuse_openai_module = importlib.import_module('langfuse.openai')

            # The module contains an 'openai' attribute which is the patched openai module
            if hasattr(langfuse_openai_module, 'openai'):
                # Replace the openai module with Langfuse's version
                sys.modules['openai'] = langfuse_openai_module.openai
                print("[Langfuse] OpenAI module globally patched for automatic tracing")
            else:
                print("[Langfuse] Warning: langfuse.openai module structure unexpected")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(f"[Langfuse] Failed to patch OpenAI module: {exc}")

    @staticmethod
    def _instrument_sdks() -> None:
        """Instrument various AI/ML SDKs for tracing.

        Note: Langfuse uses a different instrumentation approach than Phoenix.
        - OpenAI: Patched globally via _patch_openai_module() during client configuration
        - LangChain: Use get_callback_handler() to get callbacks for LangChain chains
        - Custom functions: Use @observe decorator from langfuse.decorators
        
        The OpenAI module patching is done in _patch_openai_module() which is called
        from _configure_langfuse_client() to ensure it happens after the client is set up.
        """
        print("[Langfuse] SDK instrumentation ready")
        print("[Langfuse] - OpenAI calls will be automatically traced")
        print("[Langfuse] - Use get_callback_handler() for LangChain integration")
        print("[Langfuse] - Use @observe decorator for custom function tracing")

    def _try_langfuse_setup(self) -> bool:
        """Try setting up Langfuse with automatic instrumentation.

        Returns:
            True if Langfuse setup was successful, False otherwise
        """
        try:
            self._configure_langfuse_client()
            if self.langfuse_client is None:
                return False

            self._instrument_sdks()
            return True
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._logger.info("Langfuse setup failed: %s", exc)
            return False

    def initialize(self) -> None:
        """Initialize Langfuse observability if enabled.

        Checks:
        - Whether already initialized (prevents double-init)
        - LANGFUSE_ENABLED environment variable
        - LANGFUSE_USE_EXISTING flag (skips setup if using existing instance)

        Attempts:
        1. Langfuse client configuration
        2. SDK instrumentation setup

        This method is idempotent and safe to call multiple times.
        """
        print(f"[Langfuse] initialize called, PID={os.getpid()}")
        print(f"[Langfuse] _initialized={self._initialized}")
        print(f"[Langfuse] LANGFUSE_ENABLED={os.getenv('LANGFUSE_ENABLED')}")
        print(f"[Langfuse] LANGFUSE_USE_EXISTING={os.getenv('LANGFUSE_USE_EXISTING')}")

        if self._initialized:
            print(f"[Langfuse] Already initialized in this process, skipping (PID={os.getpid()})")
            return

        if not self._get_bool_env("LANGFUSE_ENABLED", False):
            print(f"[Langfuse] Langfuse not enabled, skipping (PID={os.getpid()})")
            return

        # If using existing Langfuse instance, just verify keys are set
        if self._get_bool_env("LANGFUSE_USE_EXISTING", False):
            print(f"[Langfuse] Using existing Langfuse instance (PID={os.getpid()})")
            print(f"[Langfuse] Keys configured, skipping initialization (PID={os.getpid()})")
            self._initialized = True
            return

        try:
            print(f"[Langfuse] Attempting Langfuse setup (PID={os.getpid()})")
            setup_successful = self._try_langfuse_setup()
            if setup_successful:
                print(f"[Langfuse] Setup succeeded (PID={os.getpid()})")
                print(f"[Langfuse] Traces will be sent to: {os.getenv('LANGFUSE_HOST', 'https://cloud.langfuse.com')}")
                print(f"[Langfuse] Project: {os.getenv('LANGFUSE_PROJECT_NAME', 'default')}")
                self._initialized = True
            else:
                print(f"[Langfuse] Setup failed (PID={os.getpid()})")
            print(f"[Langfuse] Initialization complete (PID={os.getpid()})")
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

    def set_environment_variables(self) -> None:
        """Set Langfuse environment variables."""
        # Langfuse configuration
        os.environ["LANGFUSE_ENABLED"] = str(self.config.get("langfuse_enabled", "false")).lower()
        os.environ["LANGFUSE_USE_EXISTING"] = str(self.config.get("langfuse_use_existing", "false")).lower()
        os.environ["LANGFUSE_HOST"] = self.config.get("langfuse_host", "https://cloud.langfuse.com")
        os.environ["LANGFUSE_PROJECT_NAME"] = str(self.config.get("langfuse_project_name", "default"))
        os.environ["LANGFUSE_RELEASE"] = self.config.get("langfuse_release", "dev")
        os.environ["LANGFUSE_DEBUG"] = str(self.config.get("langfuse_debug", "false")).lower()
        os.environ["LANGFUSE_SAMPLE_RATE"] = str(self.config.get("langfuse_sample_rate", "1.0"))

        # Only set keys if provided (don't overwrite existing values with empty strings)
        if self.config.get("langfuse_secret_key"):
            os.environ["LANGFUSE_SECRET_KEY"] = self.config.get("langfuse_secret_key", "")
        if self.config.get("langfuse_public_key"):
            os.environ["LANGFUSE_PUBLIC_KEY"] = self.config.get("langfuse_public_key", "")

        print(f"LANGFUSE_ENABLED set to: {os.environ['LANGFUSE_ENABLED']}")
        print(f"LANGFUSE_USE_EXISTING set to: {os.environ['LANGFUSE_USE_EXISTING']}")
        print(f"LANGFUSE_HOST set to: {os.environ['LANGFUSE_HOST']}")
        print(f"LANGFUSE_PROJECT_NAME set to: {os.environ['LANGFUSE_PROJECT_NAME']}")
        print(f"LANGFUSE_RELEASE set to: {os.environ['LANGFUSE_RELEASE']}")
        print(f"LANGFUSE_DEBUG set to: {os.environ['LANGFUSE_DEBUG']}")
        print(f"LANGFUSE_SAMPLE_RATE set to: {os.environ['LANGFUSE_SAMPLE_RATE']}\n")

    def get_callback_handler(self):
        """Get Langfuse callback handler for LangChain integration.

        Returns:
            Langfuse CallbackHandler instance if available, None otherwise
        """
        if not self._initialized or self.langfuse_client is None:
            return None

        try:
            # Lazily load CallbackHandler
            callback_handler_class: Type[Any] = ResolverUtil.create_type(
                "langfuse.callback.CallbackHandler",
                raise_if_not_found=False,
                install_if_missing="langfuse",
            )

            if callback_handler_class is not None:
                return callback_handler_class()
            return None
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._logger.warning("Failed to create Langfuse callback handler: %s", exc)
            return None

    def flush(self) -> None:
        """Flush any pending traces to Langfuse."""
        if self.langfuse_client is not None:
            try:
                self.langfuse_client.flush()
                print("[Langfuse] Flushed pending traces")
            except Exception as exc:  # pylint: disable=broad-exception-caught
                self._logger.warning("Failed to flush Langfuse traces: %s", exc)

    def shutdown(self) -> None:
        """Shutdown Langfuse client and flush remaining traces."""
        if self.langfuse_client is not None:
            print("[Langfuse] Shutting down...")
            try:
                self.langfuse_client.flush()
                self._initialized = False
                print("[Langfuse] Shutdown complete")
            except Exception as exc:  # pylint: disable=broad-exception-caught
                self._logger.warning("Failed to shutdown Langfuse cleanly: %s", exc)
