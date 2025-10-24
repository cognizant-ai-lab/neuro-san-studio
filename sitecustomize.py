# Auto-initialize Phoenix/OpenInference across all Python entrypoints
try:
    # Importing triggers initialization in plugins.phoenix.phoenix_init
    from plugins.phoenix.phoenix_init import (  # noqa: F401 # pylint: disable=unused-import
        initialize_phoenix_if_enabled,
    )
except Exception:  # pragma: no cover  # pylint: disable=broad-exception-caught
    pass
