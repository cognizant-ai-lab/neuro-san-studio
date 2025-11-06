import logging
import os
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


class PhoenixInitializer:
    """
    Manages Phoenix/OpenTelemetry initialization for tracing and observability.

    Handles:
    - OpenTelemetry tracer provider configuration
    - SDK instrumentation (OpenAI, LangChain, Anthropic, etc.)
    - Phoenix integration via phoenix.otel.register()
    - Process-local initialization state tracking
    """

    def __init__(self) -> None:
        """Initialize the PhoenixInitializer with uninitialized state."""
        self._initialized = False
        self._logger = logging.getLogger(__name__)

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

    def _configure_tracer_provider(self) -> None:
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

