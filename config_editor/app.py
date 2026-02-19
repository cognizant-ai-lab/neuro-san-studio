# Copyright (C) 2025-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
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
HOCON Config Editor — FastAPI application for managing agent network
configuration files (registries/*.hocon) via a web UI and REST API.
"""

import os
import re
from pathlib import Path
from typing import Dict
from typing import List
from typing import Optional

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pyhocon import ConfigFactory
from pyhocon.exceptions import ConfigException

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
REGISTRIES_PATH = Path(os.environ.get("CONFIG_EDITOR_REGISTRIES_PATH", "registries")).resolve()

_THIS_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(_THIS_DIR / "templates"))

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="HOCON Config Editor", docs_url="/api/docs", redoc_url=None)
app.mount("/static", StaticFiles(directory=str(_THIS_DIR / "static")), name="static")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class FileContent(BaseModel):
    """Request body containing HOCON file content."""

    content: str


class ValidationResult(BaseModel):
    """Response for HOCON validation results."""

    valid: bool
    error: Optional[str] = None


class ManifestEntry(BaseModel):
    """Request body for toggling a manifest entry."""

    enabled: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _safe_path(relative: str) -> Path:
    """Resolve a user-supplied relative path and ensure it stays within REGISTRIES_PATH."""
    resolved = (REGISTRIES_PATH / relative).resolve()
    if not str(resolved).startswith(str(REGISTRIES_PATH)):
        raise HTTPException(status_code=400, detail="Path traversal not allowed")
    return resolved


def _walk_hocon_files() -> List[Dict]:
    """Return a flat list of all .hocon files relative to REGISTRIES_PATH."""
    files: List[Dict] = []
    if not REGISTRIES_PATH.is_dir():
        return files
    for path in sorted(REGISTRIES_PATH.rglob("*.hocon")):
        files.append(
            {
                "path": str(path.relative_to(REGISTRIES_PATH)),
                "name": path.name,
                "directory": str(path.parent.relative_to(REGISTRIES_PATH)),
            }
        )
    return files


def _read_manifest() -> Dict[str, object]:
    """Parse the main manifest.hocon and return its top-level entries."""
    manifest_path = REGISTRIES_PATH / "manifest.hocon"
    if not manifest_path.is_file():
        return {}
    try:
        conf = ConfigFactory.parse_file(str(manifest_path))
        # Strip surrounding quotes from keys — pyhocon may preserve them
        # for keys containing dots (e.g. "my_network.hocon")
        return {k.strip('"'): conf[k] for k in conf}
    except Exception:
        return {}


def _toggle_manifest_entry(network: str, enabled: bool) -> None:
    """Toggle a network entry in manifest.hocon between true and false.

    Uses regex matching to find the entry regardless of whitespace variations.
    Only modifies entries in the root manifest — entries from included
    sub-manifests cannot be toggled here.
    """
    manifest_path = REGISTRIES_PATH / "manifest.hocon"
    if not manifest_path.is_file():
        raise HTTPException(status_code=404, detail="manifest.hocon not found")

    content = manifest_path.read_text(encoding="utf-8")
    new_bool = "true" if enabled else "false"

    # Strip any surrounding quotes from the network key (prevent double-quoting)
    network = network.strip('"')

    # Regex: match "network.hocon" : true/false with flexible whitespace
    pattern = re.compile(
        r'("' + re.escape(network) + r'")\s*:\s*(true|false)',
        re.IGNORECASE,
    )
    match = pattern.search(content)

    if match:
        # Replace only the boolean value, preserve the key and spacing
        start, end = match.start(2), match.end(2)
        content = content[:start] + new_bool + content[end:]
    else:
        # Entry not found in root manifest — add before the closing brace
        insert_pos = content.rfind("}")
        if insert_pos == -1:
            raise HTTPException(status_code=500, detail="Malformed manifest.hocon")
        entry = f'    "{network}": {new_bool},\n'
        content = content[:insert_pos] + "\n" + entry + content[insert_pos:]

    manifest_path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Routes — UI
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def editor_ui(request: Request):
    """Serve the config editor single-page UI."""
    return templates.TemplateResponse("index.html", {"request": request})


# ---------------------------------------------------------------------------
# Routes — File CRUD API
# ---------------------------------------------------------------------------
@app.get("/api/files")
async def list_files():
    """List all .hocon files in the registries directory."""
    return {"files": _walk_hocon_files()}


@app.get("/api/files/{file_path:path}")
async def read_file(file_path: str):
    """Read the content of a specific HOCON file."""
    path = _safe_path(file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    return {"path": file_path, "content": path.read_text(encoding="utf-8")}


@app.post("/api/files/{file_path:path}", status_code=201)
async def create_file(file_path: str, body: FileContent):
    """Create a new HOCON file."""
    if not file_path.endswith(".hocon"):
        raise HTTPException(status_code=400, detail="File must have .hocon extension")
    path = _safe_path(file_path)
    if path.exists():
        raise HTTPException(status_code=409, detail=f"File already exists: {file_path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.content, encoding="utf-8")
    return {"path": file_path, "created": True}


@app.put("/api/files/{file_path:path}")
async def update_file(file_path: str, body: FileContent):
    """Update an existing HOCON file."""
    path = _safe_path(file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    path.write_text(body.content, encoding="utf-8")
    return {"path": file_path, "updated": True}


@app.delete("/api/files/{file_path:path}")
async def delete_file(file_path: str):
    """Delete a HOCON file."""
    path = _safe_path(file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    path.unlink()
    return {"path": file_path, "deleted": True}


# ---------------------------------------------------------------------------
# Routes — Validation
# ---------------------------------------------------------------------------
def _clean_parse_error(raw: str) -> str:
    """Extract human-readable location info from verbose pyparsing errors."""
    # pyparsing errors end with: found 'X' (at char N), (line:L, col:C)
    match = re.search(r"found\s+(.+?)\s*\(at char \d+\),\s*\(line:(\d+),\s*col:(\d+)\)", raw)
    if match:
        found, line, col = match.group(1), match.group(2), match.group(3)
        return f"Syntax error at line {line}, col {col}: unexpected {found}"
    # ConfigException messages are usually already clean
    # Truncate if still too long
    if len(raw) > 200:
        return raw[:200] + "..."
    return raw


@app.post("/api/validate")
async def validate_hocon(body: FileContent) -> ValidationResult:
    """Validate HOCON syntax and return any parse errors."""
    try:
        ConfigFactory.parse_string(body.content)
        return ValidationResult(valid=True)
    except (ConfigException, Exception) as exc:
        return ValidationResult(valid=False, error=_clean_parse_error(str(exc)))


# ---------------------------------------------------------------------------
# Routes — Manifest management
# ---------------------------------------------------------------------------
@app.get("/api/manifest")
async def get_manifest():
    """Return manifest entries with their enabled/disabled status."""
    entries = _read_manifest()
    result = {}
    for key, value in entries.items():
        if isinstance(value, bool):
            result[key] = {"enabled": value}
        elif isinstance(value, dict):
            result[key] = {"enabled": value.get("serve", True), "public": value.get("public", True)}
        elif isinstance(value, str) and key == "include":
            continue
        else:
            result[key] = {"enabled": bool(value)}
    return {"entries": result}


@app.put("/api/manifest/{network:path}")
async def toggle_manifest(network: str, body: ManifestEntry):
    """Toggle a network entry on/off in manifest.hocon."""
    _toggle_manifest_entry(network, body.enabled)
    return {"network": network, "enabled": body.enabled}
