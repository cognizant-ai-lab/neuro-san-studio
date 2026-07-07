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

import os
from pathlib import Path
from typing import Any

from neuro_san.interfaces.coded_tool import CodedTool

# Base output directory relative to the project root.
# Resolved at runtime via _resolve_output_base() so it works whether the server
# is run from the project root or from inside a container.
_DEFAULT_OUTPUT_BASE = "outputs/enterprise_architect_advisor"

# sly_data key used to share the session folder across multiple tool calls
# within the same network turn.
_SLY_SESSION_KEY = "ea_session_id"

# Files that are permitted to be written by this tool (whitelist).
_ALLOWED_FILENAMES = {
    "executive_summary.md",
    "architecture_decision_matrix.md",
    "detailed_findings.md",
    "roadmap.md",
}


def _resolve_output_base() -> Path:
    """
    Resolve the output base directory.

    Preference order:
      1. EA_OUTPUT_DIR environment variable (absolute path, for container deployments)
      2. <cwd>/outputs/enterprise_architect_advisor  (standard local-run layout)
    """
    env_override = os.environ.get("EA_OUTPUT_DIR")
    if env_override:
        return Path(env_override)
    return Path.cwd() / _DEFAULT_OUTPUT_BASE


class DocumentWriter(CodedTool):
    """
    CodedTool that writes the four Enterprise Architect Advisor output documents
    to a per-session subfolder on the local filesystem.

    Session management
    ------------------
    The first call within a neuro-san turn generates a UUID session ID, stores
    it in sly_data["ea_session_id"], and creates the session directory.
    Subsequent calls within the same turn (e.g., the other three deliverables)
    reuse the same session ID from sly_data, so all four files land in the same
    folder.

    Cross-turn persistence (Phase 3 doc updates)
    ---------------------------------------------
    When chief_enterprise_architect calls this tool in Phase 3, it must pass
    the session_id it received in the Phase 2 response.  This is the only
    reliable mechanism because sly_data does not automatically persist across
    HTTP requests — it must be threaded through the agent's conversation context
    and supplied as an argument.

    Allowed filenames: executive_summary.md, architecture_decision_matrix.md,
                       detailed_findings.md, roadmap.md
    """

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any]:
        """
        Write a deliverable file to the session output directory.

        :param args: Dictionary with the following keys:
            "filename" (str, required):
                One of the four permitted filenames.
            "content" (str, required):
                Full markdown content to write.
            "mode" (str, required):
                "create" — write a new file; error if it already exists.
                "update" — overwrite an existing file (Phase 3 amendments).
            "session_id" (str, optional):
                Reuse a previously created session folder.  When present,
                takes precedence over sly_data["ea_session_id"].  The chief
                should always supply this in Phase 3 calls.

        :param sly_data: Shared low-level data bulletin board.  The tool reads
            and writes "ea_session_id" to share the session folder across calls
            within the same turn.

        :return: Dict with keys:
            "file_path"  — absolute path of the written file.
            "session_id" — the session ID used (new or reused).
            "status"     — "created" or "updated".
        """
        # ── Validate required inputs ──────────────────────────────────────────
        filename: str = args.get("filename", "").strip()
        content: str = args.get("content", "")
        mode: str = args.get("mode", "").strip().lower()
        provided_session_id: str = args.get("session_id", "").strip()

        if not filename:
            return {"error": "invalid_input: 'filename' is required."}
        if filename not in _ALLOWED_FILENAMES:
            return {
                "error": (
                    f"invalid_input: '{filename}' is not an allowed filename. "
                    f"Permitted values: {sorted(_ALLOWED_FILENAMES)}"
                )
            }
        if not content:
            return {"error": "invalid_input: 'content' is required and must not be empty."}
        if mode not in ("create", "update"):
            return {"error": "invalid_input: 'mode' must be 'create' or 'update'."}

        # ── Resolve session ID (project name) ────────────────────────────────
        # Priority: explicit arg > sly_data > sanitised timestamp fallback.
        # The chief always passes the project name it generated in Phase 1,
        # so the fallback should rarely trigger in practice.
        session_id: str = (
            provided_session_id
            or sly_data.get(_SLY_SESSION_KEY, "")
        )
        if not session_id:
            # Last-resort fallback: timestamp-based slug so files are never
            # silently lost under a random UUID that the chief can't reconstruct.
            import datetime
            session_id = "project-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
        # Sanitise: lowercase, replace spaces/underscores with hyphens,
        # strip anything that isn't alphanumeric or a hyphen.
        import re as _re
        session_id = _re.sub(r"[^a-z0-9-]", "", session_id.lower().replace(" ", "-").replace("_", "-"))
        session_id = _re.sub(r"-{2,}", "-", session_id).strip("-") or "project"
        # Persist into sly_data so sibling tool calls in the same turn reuse it
        sly_data[_SLY_SESSION_KEY] = session_id

        # ── Build file path ───────────────────────────────────────────────────
        output_base = _resolve_output_base()
        session_dir = output_base / session_id
        try:
            session_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return {"error": f"write_error: could not create session directory '{session_dir}': {exc}"}

        file_path = session_dir / filename

        # ── Mode-specific guards ──────────────────────────────────────────────
        if mode == "create" and file_path.exists():
            # Treat as an implicit update so Phase 2 re-runs don't fail.
            # The chief's instructions already gate this correctly, but
            # being lenient here prevents a hard error on retry.
            mode = "update"

        if mode == "update" and not file_path.exists():
            # If the file doesn't exist yet (e.g., session_id mismatch),
            # create it rather than erroring — the content is still valid.
            mode = "create"

        # ── Write file ────────────────────────────────────────────────────────
        try:
            file_path.write_text(content, encoding="utf-8")
        except OSError as exc:
            return {"error": f"write_error: could not write '{file_path}': {exc}"}

        status = "created" if mode == "create" else "updated"
        return {
            "file_path": str(file_path.resolve()),
            "session_id": session_id,
            "status": status,
        }
