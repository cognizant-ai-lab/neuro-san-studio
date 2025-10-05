# Auto-initialize Phoenix/OpenInference for all Python processes
# This file is automatically imported by Python on startup
import os

if os.getenv("PHOENIX_ENABLED", "false").lower() in ("true", "1", "yes", "on"):
    try:
        from plugins.phoenix import initialize_phoenix_if_enabled
    except Exception:
        # Phoenix plugin not installed or failed to import
        pass
