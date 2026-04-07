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
Phoenix plugin for OpenTelemetry tracing and observability.

Handles:
- OpenTelemetry tracer provider configuration
- SDK instrumentation (OpenAI, LangChain, Anthropic, etc.)
- Phoenix integration via phoenix.otel.register()
- Process-local initialization state tracking
- Phoenix server process management (start/stop)
"""

import os
import signal
import socket
import subprocess
import sys
import time
from types import ModuleType
from typing import Any
from typing import Optional
from typing import Type

# Use lazy loading of types to avoid dependency bloat for stuff most people don't need.
from leaf_common.config.resolver_util import ResolverUtil

from neuro_san_studio.interfaces.plugins import BasePlugin


class PhoenixPlugin(BasePlugin):
    """Plugin for Phoenix/OpenTelemetry observability in Neuro-San Studio."""

    def __init__(self, args: dict = None):
        """Initialize the Phoenix plugin.

        Args:
            args: Optional dictionary of arguments for the plugin.
        """
        super().__init__(plugin_name="Phoenix", args=args)
        self._initialized = False
        self.config = self.get_default_config()
        self.phoenix_process = None
        self.is_windows = os.name == "nt"
        self.set_environment_variables()

    @staticmethod
    def get_default_config() -> dict:
        """Get default Phoenix configuration from environment variables.

        Returns:
            Dictionary with default Phoenix configuration values
        """
        return {
            # Phoenix / OpenTelemetry defaults
            "otel_service_name": os.getenv("OTEL_SERVICE_NAME", "neuro-san-demos"),
            "otel_service_version": os.getenv("OTEL_SERVICE_VERSION", "dev"),
            "otel_exporter_otlp_traces_endpoint": os.getenv(
                "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
                os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:6006/v1/traces"),
            ),
            # Phoenix UI/collector configuration
            "phoenix_host": os.getenv("PHOENIX_HOST", "127.0.0.1"),
            "phoenix_port": int(os.getenv("PHOENIX_PORT", "6006")),
            "phoenix_autostart": os.getenv("PHOENIX_AUTOSTART", "false"),
            "phoenix_project_name": os.getenv("PHOENIX_PROJECT_NAME", "default"),
            "phoenix_otel_register": os.getenv("PHOENIX_OTEL_REGISTER", "true"),
        }

    def _configure_tracer_provider(self) -> None:
        """Configure OpenTelemetry tracer provider with OTLP exporter.

        Sets up:
        - Service name and version from environment
        - OTLP span exporter with batch processor
        - Fallback to Phoenix default endpoint if not specified
        """
        # pylint: disable=invalid-name
        TracerProvider: Type[Any] = ResolverUtil.create_type(
            "opentelemetry.sdk.trace.TracerProvider",
            raise_if_not_found=False,
            install_if_missing="opentelemetry-sdk",
        )

        trace: ModuleType = ResolverUtil.create_type(
            "opentelemetry.trace",
            raise_if_not_found=False,
            install_if_missing="opentelemetry-sdk",
        )

        if trace is None or TracerProvider is None:  # pragma: no cover
            self._logger.info("Skipping OpenTelemetry TracerProvider configuration")
            return

        # Avoid double-initialization if a provider already exists
        if isinstance(trace.get_tracer_provider(), TracerProvider):  # type: ignore[arg-type]
            # Already configured by us or someone else
            return

        service_name = os.getenv("OTEL_SERVICE_NAME", "neuro-san-demos")
        service_version = os.getenv("OTEL_SERVICE_VERSION", "dev")

        # pylint: disable=invalid-name
        Resource: Type[Any] = ResolverUtil.create_type(
            "opentelemetry.sdk.resources.Resource",
            install_if_missing="opentelemetry-sdk",
        )
        resource = Resource.create(
            {
                "service.name": service_name,
                "service.version": service_version,
            }
        )

        provider = TracerProvider(resource=resource)

        # pylint: disable=invalid-name
        OTLPSpanExporter: Type[Any] = ResolverUtil.create_type(
            "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
            raise_if_not_found=False,
            install_if_missing="opentelemetry-exporter-otlp",
        )
        if OTLPSpanExporter is not None:
            self._logger.info("Configuring OTLPSpanExporter")
            # Prefer explicit traces endpoint if provided; fallback to Phoenix default
            endpoint: Optional[str] = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") or os.getenv(
                "OTEL_EXPORTER_OTLP_ENDPOINT"
            )
            if not endpoint:
                endpoint = "http://localhost:6006/v1/traces"

            exporter = OTLPSpanExporter(endpoint=endpoint)

            # pylint: disable=invalid-name
            BatchSpanProcessor: Type[Any] = ResolverUtil.create_type(
                "opentelemetry.sdk.trace.export.BatchSpanProcessor",
                install_if_missing="opentelemetry-sdk",
            )
            processor = BatchSpanProcessor(exporter)
            provider.add_span_processor(processor)

        trace.set_tracer_provider(provider)

    def _instrument_sdks(self) -> None:
        """Instrument various AI/ML SDKs for tracing.

        Instruments:
        - OpenAI
        - LangChain
        - LiteLLM
        - Anthropic
        - MCP

        Failures are silently ignored to allow partial instrumentation.
        """
        instrumentors = [
            ("openinference.instrumentation.openai.OpenAIInstrumentor", "openinference-instrumentation-openai"),
            (
                "openinference.instrumentation.langchain.LangChainInstrumentor",
                "openinference-instrumentation-langchain",
            ),
            ("openinference.instrumentation.litellm.LiteLLMInstrumentor", "openinference-instrumentation-litellm"),
            (
                "openinference.instrumentation.anthropic.AnthropicInstrumentor",
                "openinference-instrumentation-anthropic",
            ),
            ("openinference.instrumentation.mcp.MCPInstrumentor", "openinference-instrumentation-mcp"),
        ]

        for class_path, install_pkg in instrumentors:
            # pylint: disable=invalid-name
            InstrumentorClass: Type[Any] = ResolverUtil.create_type(
                class_path,
                raise_if_not_found=False,
                install_if_missing=install_pkg,
            )
            if InstrumentorClass is not None:
                short_name = class_path.rsplit(".", maxsplit=1)[-1]
                self._logger.info("Using %s", short_name)
                InstrumentorClass().instrument()

    def _try_phoenix_register(self) -> bool:
        """Try using phoenix.otel.register for first-class setup.

        Returns:
            True if phoenix.otel.register() was successful, False otherwise
        """
        try:
            if not self._get_bool_env("PHOENIX_OTEL_REGISTER", True):
                return False

            # Lazily load the method
            register: Type[Any] = ResolverUtil.create_type(
                "phoenix.otel.register",
                install_if_missing="arize-phoenix-otel",
            )

            project_name = os.getenv("PHOENIX_PROJECT_NAME", "default")
            endpoint = (
                os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
                or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
                or "http://localhost:6006/v1/traces"
            )
            # Auto-instrument supported libs (OpenAI, LangChain, etc.)
            register(
                project_name=project_name,
                endpoint=endpoint,
                auto_instrument=True,
            )
            return True
        except Exception as exc:  # pylint: disable=broad-except
            self._logger.info("Phoenix register not used: %s", exc)
            return False

    def _do_initialize(self) -> None:
        """Initialize Phoenix observability if enabled.

        Checks whether already initialized (prevents double-init).

        Attempts:
        1. phoenix.otel.register() for automatic setup
        2. Manual tracer provider and SDK instrumentation if register fails

        This method is idempotent and safe to call multiple times.
        """
        if self._initialized:
            self._logger.info("Already initialized, skipping (PID=%s)", os.getpid())
            return

        try:
            self._logger.info("Attempting phoenix.otel.register() (PID=%s)", os.getpid())
            used_phoenix_register = self._try_phoenix_register()
            if not used_phoenix_register:
                self._logger.info("phoenix.otel.register() not available, using manual setup (PID=%s)", os.getpid())
                self._configure_tracer_provider()
                self._instrument_sdks()
            else:
                self._logger.info("phoenix.otel.register() succeeded (PID=%s)", os.getpid())
            self._initialized = True
        except Exception as exc:  # pylint: disable=broad-except
            self._logger.warning("Initialization failed: %s (PID=%s)", exc, os.getpid())

    @property
    def is_initialized(self) -> bool:
        """Check if Phoenix has been initialized.

        Returns:
            True if initialized, False otherwise
        """
        return self._initialized

    def set_environment_variables(self) -> None:
        """Set Phoenix and OpenTelemetry environment variables."""
        # Phoenix / OpenTelemetry envs
        os.environ["OTEL_SERVICE_NAME"] = self.config.get("otel_service_name", "neuro-san-demos")
        os.environ["OTEL_SERVICE_VERSION"] = self.config.get("otel_service_version", "dev")
        os.environ["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] = self.config.get(
            "otel_exporter_otlp_traces_endpoint", "http://localhost:6006/v1/traces"
        )

        self._logger.info("OTEL_SERVICE_NAME set to: %s", os.environ["OTEL_SERVICE_NAME"])
        self._logger.info("OTEL_SERVICE_VERSION set to: %s", os.environ["OTEL_SERVICE_VERSION"])
        self._logger.info(
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT set to: %s", os.environ["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"]
        )

        # Phoenix register settings
        os.environ["PHOENIX_PROJECT_NAME"] = str(self.config.get("phoenix_project_name", "default"))
        os.environ["PHOENIX_OTEL_REGISTER"] = str(self.config.get("phoenix_otel_register", "true")).lower()

        self._logger.info("PHOENIX_PROJECT_NAME set to: %s", os.environ["PHOENIX_PROJECT_NAME"])
        self._logger.info("PHOENIX_OTEL_REGISTER set to: %s", os.environ["PHOENIX_OTEL_REGISTER"])

    @staticmethod
    def _is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
        """Check if a port is open on a given host.

        Args:
            host: Host address to check
            port: Port number to check
            timeout: Connection timeout in seconds

        Returns:
            True if the port is open, False otherwise.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            try:
                sock.connect((host, port))
                return True
            except (ConnectionRefusedError, TimeoutError, OSError):
                return False

    def _start_process(self, command: list, log_file: str):
        """Start a subprocess and return the process object.

        Args:
            command: Command to execute
            log_file: Path to log file

        Returns:
            subprocess.Popen object
        """
        # Initialize/clear the log file before starting
        with open(log_file, "w", encoding="utf-8") as log:
            log.write("Starting Phoenix...\n")

        # pylint: disable=consider-using-with
        if self.is_windows:
            # On Windows, don't use CREATE_NEW_PROCESS_GROUP to allow Ctrl+C propagation
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )
        else:
            # On Unix, use start_new_session for proper process group management
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
                start_new_session=True,
            )

        self._logger.info("Started Phoenix with PID %s", process.pid)
        return process

    def start_phoenix_server(self) -> None:
        """Start Phoenix server (UI + OTLP HTTP collector) if autostart is configured."""
        if str(self.config.get("phoenix_autostart", "false")).lower() not in ("true", "1", "yes", "on"):
            return

        self._logger.info("Starting Phoenix (AI observability)...")
        phoenix_host = self.config.get("phoenix_host", "127.0.0.1")
        phoenix_port = self.config.get("phoenix_port", 6006)

        # If something is already listening on PHOENIX_PORT, assume Phoenix is running and skip autostart
        if self._is_port_open(phoenix_host, phoenix_port):
            phoenix_url = f"http://{phoenix_host}:{phoenix_port}"
            self._logger.info("Phoenix detected at %s — skipping autostart.", phoenix_url)
        else:
            # Disable gRPC on Windows (port binding issues)
            os.environ["PHOENIX_GRPC_PORT"] = "0"

            # Use python -m form for better compatibility
            try:
                self.phoenix_process = self._start_process(
                    [sys.executable, "-m", "phoenix.server.main", "serve"], "logs/phoenix.log"
                )

                # Wait for Phoenix to bind to port (with retry)
                phoenix_ready = False
                for _ in range(10):  # Try for up to 10 seconds
                    time.sleep(1)
                    if self._is_port_open(phoenix_host, phoenix_port):
                        phoenix_ready = True
                        break

                if phoenix_ready:
                    self._logger.info("Phoenix started successfully.")
                else:
                    self._logger.warning("Failed to start Phoenix automatically. Check logs/phoenix.log")
            except Exception as exc:  # pylint: disable=broad-exception-caught
                self._logger.warning("Failed to start Phoenix automatically: %s", exc)

        # Update OTLP endpoint env to point to this phoenix instance if not explicitly overridden
        default_otlp = f"http://{phoenix_host}:{phoenix_port}/v1/traces"
        if os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") in (None, "", "http://localhost:6006/v1/traces"):
            os.environ["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] = default_otlp
            self._logger.info("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT updated to: %s", default_otlp)

    def stop_phoenix_server(self) -> None:
        """Stop the Phoenix process if it's running."""
        if self.phoenix_process:
            self._logger.info("Stopping Phoenix (PID %s)...", self.phoenix_process.pid)
            if self.is_windows:
                self.phoenix_process.terminate()
            else:
                os.killpg(os.getpgid(self.phoenix_process.pid), signal.SIGKILL)

    def pre_server_start_action(self):
        """Start Phoenix server if enabled."""
        self.start_phoenix_server()

    @staticmethod
    def update_args_dict(args_dict: dict):
        """Update the args with additional args needed for Phoenix configuration.

        Args:
            args_dict: Dictionary of arguments to update.
        """
        args_dict.update(PhoenixPlugin.get_default_config())

    def _do_cleanup(self):
        """Stop Phoenix server if it was started by this plugin."""
        self.stop_phoenix_server()
