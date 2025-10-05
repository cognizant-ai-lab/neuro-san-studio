# Auto-initialize Phoenix/OpenInference across all Python entrypoints
try:
    # Importing triggers initialization in plugins.phoenix.phoenix_init
    from plugins.phoenix.phoenix_init import initialize_phoenix_if_enabled  # noqa: F401 # pylint: disable=unused-import
except Exception:  # pragma: no cover  # pylint: disable=broad-exception-caught
    pass
