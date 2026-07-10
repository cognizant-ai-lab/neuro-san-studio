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
Root conftest.py — applied to all tests in this project.

Sets the AGENT_MANIFEST_FILE environment variable to the project's manifest
so direct-mode integration tests can resolve agent networks without needing
the env var set manually in the shell.

Azure OpenAI environment variables required for the default llm_config:
    AZURE_OPENAI_API_KEY        — API key for your Azure OpenAI resource
    AZURE_OPENAI_ENDPOINT       — e.g. https://<your-resource>.openai.azure.com/
    AZURE_OPENAI_DEPLOYMENT_NAME — deployment name (e.g. gpt-4o-mini)
    OPENAI_API_VERSION          — API version (e.g. 2025-01-01-preview)

These can be set in the shell before running pytest, or placed in a .env file
and loaded with a tool such as python-dotenv.  They are never hard-coded here.
"""

import os
from pathlib import Path

# Ensure AGENT_MANIFEST_FILE points to this project's manifest if not already
# overridden by the caller (e.g., CI pipelines that set it explicitly).
if not os.environ.get("AGENT_MANIFEST_FILE"):
    _manifest = Path(__file__).parent / "registries" / "manifest.hocon"
    os.environ["AGENT_MANIFEST_FILE"] = str(_manifest)

# ---------------------------------------------------------------------------
# Optional: load a .env file from the project root so developers can store
# API keys locally without setting shell variables manually.
# The file is gitignored and never committed.
# ---------------------------------------------------------------------------
_dotenv_path = Path(__file__).parent / ".env"
if _dotenv_path.exists():
    try:
        from dotenv import load_dotenv  # pip install python-dotenv
        load_dotenv(_dotenv_path, override=False)  # shell vars take precedence
    except ImportError:
        pass  # python-dotenv not installed — silently skip

# ---------------------------------------------------------------------------
# Redirect the gist discriminator agent to the project-local gist.hocon so
# the evaluator uses the same LLM provider (azure-openai) as the agents under
# test.  The library's default gist.hocon uses class="openai" (gpt-5.2) which
# requires a separate OPENAI_API_KEY; our override uses class="azure-openai"
# which reads the AZURE_OPENAI_* variables already present in .env.
# ---------------------------------------------------------------------------
_local_registries = Path(__file__).parent / "registries"
_local_gist = _local_registries / "gist.hocon"
if _local_gist.exists():
    try:
        from leaf_common.config.file_of_class import FileOfClass
        import neuro_san.test.evaluators.gist_agent_evaluator as _gist_module
        _gist_module.REGISTRIES_DIR = FileOfClass(str(_local_gist), ".")
    except Exception:
        pass  # silently skip if the module layout changes in a future version
