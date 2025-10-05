import os
import logging
from typing import Optional

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
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

    resource = Resource.create({
        "service.name": service_name,
        "service.version": service_version,
    })

    provider = TracerProvider(resource=resource)

    if OTLPSpanExporter is not None:
        # Prefer explicit traces endpoint if provided; fallback to Phoenix default
        endpoint: Optional[str] = (
            os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
            or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
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


def initialize_phoenix_if_enabled() -> None:
    if os.getenv("PHOENIX_INITIALIZED") == "1":
        return

    if not _get_bool_env("PHOENIX_ENABLED", True):
        return

    try:
        used_phoenix_register = _try_phoenix_register()
        if not used_phoenix_register:
            _configure_tracer_provider()
            _instrument_sdks()
        os.environ["PHOENIX_INITIALIZED"] = "1"
    except Exception as exc:  # pragma: no cover
        logging.getLogger("phoenix_init").warning("Phoenix initialization failed: %s", exc)


# Eager init on import so that sitecustomize can just import this module
initialize_phoenix_if_enabled()


