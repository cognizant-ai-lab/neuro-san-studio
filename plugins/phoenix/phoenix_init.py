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


def _get_bool_env(var_name: str, default: bool) -> bool:
    val = os.getenv(var_name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _configure_tracer_provider() -> None:
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


def _instrument_sdks() -> None:
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


def _try_phoenix_register() -> bool:
    """Try using phoenix.otel.register for first-class setup. Returns True if successful."""
    try:
        if not _get_bool_env("PHOENIX_OTEL_REGISTER", True):
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
        logging.getLogger("phoenix_init").info("Phoenix register not used: %s", exc)
        return False


# Process-local flag to prevent double initialization within same process
_initialized = False


def initialize_phoenix_if_enabled() -> None:
    global _initialized

    print(f"[Phoenix] initialize_phoenix_if_enabled called, PID={os.getpid()}")
    print(f"[Phoenix] _initialized={_initialized}")
    print(f"[Phoenix] PHOENIX_ENABLED={os.getenv('PHOENIX_ENABLED')}")

    if _initialized:
        print(f"[Phoenix] Already initialized in this process, skipping (PID={os.getpid()})")
        return

    if not _get_bool_env("PHOENIX_ENABLED", True):
        print(f"[Phoenix] Phoenix not enabled, skipping (PID={os.getpid()})")
        return

    try:
        print(f"[Phoenix] Attempting phoenix.otel.register() (PID={os.getpid()})")
        used_phoenix_register = _try_phoenix_register()
        if not used_phoenix_register:
            print(f"[Phoenix] phoenix.otel.register() failed, using manual setup (PID={os.getpid()})")
            _configure_tracer_provider()
            _instrument_sdks()
        else:
            print(f"[Phoenix] phoenix.otel.register() succeeded (PID={os.getpid()})")
        _initialized = True
        print(f"[Phoenix] Initialization complete (PID={os.getpid()})")
    except Exception as exc:  # pragma: no cover
        print(f"[Phoenix] Initialization FAILED: {exc} (PID={os.getpid()})")
        logging.getLogger("phoenix_init").warning("Phoenix initialization failed: %s", exc)


# Eager init on import so that sitecustomize can just import this module
initialize_phoenix_if_enabled()
