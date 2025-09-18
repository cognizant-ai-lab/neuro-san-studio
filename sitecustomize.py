# Auto-initialize Phoenix/OpenInference across all Python entrypoints
try:
    # Importing triggers initialization in observability.phoenix_init
    from observability.phoenix_init import initialize_phoenix_if_enabled  # noqa: F401
except Exception:  # pragma: no cover
    pass


