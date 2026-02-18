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
import signal
import socket
import subprocess
import sys
import time
from typing import Optional

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
except Exception:  # pragma: no cover
    trace = None  # type: ignore
    TracerProvider = None  # type: ignore
    BatchSpanProcessor = None  # type: ignore
    OTLPSpanExporter = None  # type: ignore


class PhoenixPlugin:
    """
    Manages Phoenix/OpenTelemetry initialization for tracing and observability.

    Handles:
    - OpenTelemetry tracer provider configuration
    - SDK instrumentation (OpenAI, LangChain, Anthropic, etc.)
    - Phoenix integration via phoenix.otel.register()
    - Process-local initialization state tracking
    - Phoenix server process management (start/stop)
    """

    def __init__(self, config: Optional[dict] = None) -> None:
        """Initialize the PhoenixPlugin with the optional configuration.

        Args:
            config: Optional configuration dictionary with phoenix settings
        """
        self._initialized = False
        self._logger = logging.getLogger(__name__)
        self.config = config or {}
        self.phoenix_process = None
        self.is_windows = os.name == "nt"

    @staticmethod
    def get_default_config() -> dict:
        """Get default Phoenix configuration from environment variables.

        Returns:
            Dictionary with default Phoenix configuration values
        """
        return {
            # Phoenix / OpenTelemetry defaults
            "phoenix_enabled": os.getenv("PHOENIX_ENABLED", "false"),
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
    def _configure_tracer_provider() -> None:
        """Configure OpenTelemetry tracer provider with OTLP exporter.

        Sets up:
        - Service name and version from environment
        - OTLP span exporter with batch processor
        - Fallback to Phoenix default endpoint if not specified
        """
        if trace is None or TracerProvider is None:  # pragma: no cover
            return

        # Avoid double-initialization if a provider already exists
        if isinstance(trace.get_tracer_provider(), TracerProvider):  # type: ignore[arg-type]
            # Already configured by us or someone else
            return

        service_name = os.getenv("OTEL_SERVICE_NAME", "neuro-san-demos")
        service_version = os.getenv("OTEL_SERVICE_VERSION", "dev")

        resource = Resource.create(
            {
                "service.name": service_name,
                "service.version": service_version,
            }
        )

        provider = TracerProvider(resource=resource)

        if OTLPSpanExporter is not None:
            # Prefer explicit traces endpoint if provided; fallback to Phoenix default
            endpoint: Optional[str] = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") or os.getenv(
                "OTEL_EXPORTER_OTLP_ENDPOINT"
            )
            if not endpoint:
                endpoint = "http://localhost:6006/v1/traces"

            exporter = OTLPSpanExporter(endpoint=endpoint)
            processor = BatchSpanProcessor(exporter)
            provider.add_span_processor(processor)

        trace.set_tracer_provider(provider)

    @staticmethod
    def _instrument_sdks() -> None:
        """Instrument various AI/ML SDKs for tracing.

        Instruments:
        - OpenAI
        - LangChain
        - LiteLLM
        - Anthropic
        - MCP

        Failures are silently ignored to allow partial instrumentation.
        """
        # Instrument OpenAI
        try:
            from openinference.instrumentation.openai import OpenAIInstrumentor

            OpenAIInstrumentor().instrument()
        except Exception:  # pragma: no cover
            pass

        # Instrument LangChain
        try:
            from openinference.instrumentation.langchain import LangChainInstrumentor

            LangChainInstrumentor().instrument()
        except Exception:  # pragma: no cover
            pass

        # Instrument LiteLLM (common in orchestration libs)
        try:
            from openinference.instrumentation.litellm import LiteLLMInstrumentor

            LiteLLMInstrumentor().instrument()
        except Exception:  # pragma: no cover
            pass

        # Instrument Anthropic
        try:
            from openinference.instrumentation.anthropic import AnthropicInstrumentor

            AnthropicInstrumentor().instrument()
        except Exception:  # pragma: no cover
            pass

        # Instrument MCP
        try:
            from openinference.instrumentation.mcp import MCPInstrumentor

            MCPInstrumentor().instrument()
        except Exception:  # pragma: no cover
            pass

    def _try_phoenix_register(self) -> bool:
        """Try using phoenix.otel.register for first-class setup.

        Returns:
            True if phoenix.otel.register() was successful, False otherwise
        """
        try:
            if not self._get_bool_env("PHOENIX_OTEL_REGISTER", True):
                return False
            from phoenix.otel import register  # type: ignore

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
        except Exception as exc:  # pragma: no cover
            self._logger.info("Phoenix register not used: %s", exc)
            return False

    def initialize(self) -> None:
        """Initialize Phoenix observability if enabled.

        Checks:
        - Whether already initialized (prevents double-init)
        - PHOENIX_ENABLED environment variable

        Attempts:
        1. phoenix.otel.register() for automatic setup
        2. Manual tracer provider and SDK instrumentation if register fails

        This method is idempotent and safe to call multiple times.
        """
        print(f"[Phoenix] initialize called, PID={os.getpid()}")
        print(f"[Phoenix] _initialized={self._initialized}")
        print(f"[Phoenix] PHOENIX_ENABLED={os.getenv('PHOENIX_ENABLED')}")

        if self._initialized:
            print(f"[Phoenix] Already initialized in this process, skipping (PID={os.getpid()})")
            return

        if not self._get_bool_env("PHOENIX_ENABLED", True):
            print(f"[Phoenix] Phoenix not enabled, skipping (PID={os.getpid()})")
            return

        try:
            print(f"[Phoenix] Attempting phoenix.otel.register() (PID={os.getpid()})")
            used_phoenix_register = self._try_phoenix_register()
            if not used_phoenix_register:
                print(f"[Phoenix] phoenix.otel.register() failed, using manual setup (PID={os.getpid()})")
                self._configure_tracer_provider()
                self._instrument_sdks()
            else:
                print(f"[Phoenix] phoenix.otel.register() succeeded (PID={os.getpid()})")
            self._initialized = True
            print(f"[Phoenix] Initialization complete (PID={os.getpid()})")
        except Exception as exc:  # pragma: no cover
            print(f"[Phoenix] Initialization FAILED: {exc} (PID={os.getpid()})")
            self._logger.warning("Phoenix initialization failed: %s", exc)

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
        os.environ["PHOENIX_ENABLED"] = str(self.config.get("phoenix_enabled", "false")).lower()
        os.environ["OTEL_SERVICE_NAME"] = self.config.get("otel_service_name", "neuro-san-demos")
        os.environ["OTEL_SERVICE_VERSION"] = self.config.get("otel_service_version", "dev")
        os.environ["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] = self.config.get(
            "otel_exporter_otlp_traces_endpoint", "http://localhost:6006/v1/traces"
        )

        print(f"PHOENIX_ENABLED set to: {os.environ['PHOENIX_ENABLED']}")
        print(f"OTEL_SERVICE_NAME set to: {os.environ['OTEL_SERVICE_NAME']}")
        print(f"OTEL_SERVICE_VERSION set to: {os.environ['OTEL_SERVICE_VERSION']}")
        print(f"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT set to: {os.environ['OTEL_EXPORTER_OTLP_TRACES_ENDPOINT']}\n")

        # Phoenix register settings
        os.environ["PHOENIX_PROJECT_NAME"] = str(self.config.get("phoenix_project_name", "default"))
        os.environ["PHOENIX_OTEL_REGISTER"] = str(self.config.get("phoenix_otel_register", "true")).lower()

        print(f"PHOENIX_PROJECT_NAME set to: {os.environ['PHOENIX_PROJECT_NAME']}")
        print(f"PHOENIX_OTEL_REGISTER set to: {os.environ['PHOENIX_OTEL_REGISTER']}\n")

    @staticmethod
    def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
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

    def start_process(self, command: list, log_file: str):
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

        print(f"Started Phoenix with PID {process.pid}")
        return process

    def start_phoenix_server(self) -> None:
        """Start Phoenix server (UI + OTLP HTTP collector) if enabled."""
        if str(self.config.get("phoenix_autostart", "false")).lower() not in ("true", "1", "yes", "on"):
            return
        if str(self.config.get("phoenix_enabled", "false")).lower() not in ("true", "1", "yes", "on"):
            return

        print("Starting Phoenix (AI observability)...")
        phoenix_host = self.config.get("phoenix_host", "127.0.0.1")
        phoenix_port = self.config.get("phoenix_port", 6006)

        # If something is already listening on PHOENIX_PORT, assume Phoenix is running and skip autostart
        if self.is_port_open(phoenix_host, phoenix_port):
            phoenix_url = f"http://{phoenix_host}:{phoenix_port}"
            print(f"Phoenix detected at {phoenix_url} — skipping autostart.")
        else:
            # Disable gRPC on Windows (port binding issues)
            os.environ["PHOENIX_GRPC_PORT"] = "0"

            # Use python -m form for better compatibility
            try:
                self.phoenix_process = self.start_process(
                    [sys.executable, "-m", "phoenix.server.main", "serve"], "logs/phoenix.log"
                )

                # Wait for Phoenix to bind to port (with retry)
                phoenix_ready = False
                for _ in range(10):  # Try for up to 10 seconds
                    time.sleep(1)
                    if self.is_port_open(phoenix_host, phoenix_port):
                        phoenix_ready = True
                        break

                if phoenix_ready:
                    print("Phoenix started successfully.")
                else:
                    print("Failed to start Phoenix automatically. Check logs/phoenix.log")
            except Exception as exc:  # pylint: disable=broad-exception-caught
                print(f"Failed to start Phoenix automatically: {exc}")

        # Update OTLP endpoint env to point to this phoenix instance if not explicitly overridden
        default_otlp = f"http://{phoenix_host}:{phoenix_port}/v1/traces"
        if os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") in (None, "", "http://localhost:6006/v1/traces"):
            os.environ["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] = default_otlp
            print(f"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT updated to: {default_otlp}")

    def stop_phoenix_server(self) -> None:
        """Stop the Phoenix process if it's running."""
        if self.phoenix_process:
            print(f"Stopping PHOENIX (PID {self.phoenix_process.pid})...")
            if self.is_windows:
                self.phoenix_process.terminate()
            else:
                os.killpg(os.getpgid(self.phoenix_process.pid), signal.SIGKILL)
