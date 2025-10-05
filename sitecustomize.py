# Auto-initialize Phoenix/OpenInference for all Python processes
# This file is automatically imported by Python on startup when in PYTHONPATH
import os
import sys

# Ensure project root is in path (derive from PYTHONPATH env var)
_project_root = os.getenv("PYTHONPATH")
if _project_root and _project_root not in sys.path:
    sys.path.insert(0, _project_root)

if os.getenv("PHOENIX_ENABLED", "false").lower() in ("true", "1", "yes", "on"):
    try:
        from plugins.phoenix import initialize_phoenix_if_enabled
    except Exception as e:
        # Phoenix plugin not installed or failed to import
        import warnings
        warnings.warn(f"Failed to initialize Phoenix: {e}")
