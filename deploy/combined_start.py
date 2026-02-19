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
Combined ASGI application that serves nsflow + config_editor on a single port.

Routes:
    /editor/*  -> config_editor FastAPI app (Starlette Mount strips prefix)
    /*         -> nsflow FastAPI app (with HTML injection middleware)

The HTML injection middleware adds a floating "Editor" button to nsflow's
HTML pages that opens the config editor in a slide-in iframe overlay.

Configurable via environment variables:
    NSFLOW_HOST              (default: 0.0.0.0)
    NSFLOW_PORT              (default: 4173)
    CONFIG_EDITOR_ENABLED    (default: true)
"""

import os

# ---------------------------------------------------------------------------
# Critical: monkey-patch hvac BEFORE any nsflow import.
# The nsflow import chain triggers leaf_common which accesses hvac.VaultClient,
# but the correct attribute is hvac.Client.
# ---------------------------------------------------------------------------
import hvac  # noqa: E402

hvac.VaultClient = hvac.Client

import uvicorn  # noqa: E402
from starlette.applications import Starlette  # noqa: E402
from starlette.routing import Mount  # noqa: E402
from starlette.types import ASGIApp  # noqa: E402
from starlette.types import Receive  # noqa: E402
from starlette.types import Scope  # noqa: E402
from starlette.types import Send  # noqa: E402

from config_editor.app import app as editor_app  # noqa: E402
from nsflow.backend.main import app as nsflow_app  # noqa: E402


# ---------------------------------------------------------------------------
# HTML injection snippet — floating Editor button + iframe overlay
# ---------------------------------------------------------------------------
_INJECTION_SNIPPET = """
<!-- NSS Config Editor Integration -->
<style>
  #nss-editor-toggle {
    position: fixed; top: 12px; right: 12px; z-index: 9999;
    background: linear-gradient(90deg, #507be8, #233a66);
    color: #fff; border: none; border-radius: 8px;
    padding: 10px 18px; font-size: 14px; font-weight: 600;
    cursor: pointer; box-shadow: 0 2px 8px rgba(80,123,232,0.3);
    font-family: Inter, sans-serif;
    transition: transform 0.15s, box-shadow 0.15s;
  }
  #nss-editor-toggle:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(80,123,232,0.4);
  }
  #nss-editor-overlay {
    position: fixed; top: 0; right: -62%; bottom: 0; width: 60%;
    z-index: 9998; background: #fff;
    box-shadow: -4px 0 20px rgba(0,0,0,0.15);
    transition: right 0.3s ease;
  }
  #nss-editor-overlay.open { right: 0; }
  #nss-editor-overlay iframe {
    width: 100%; height: 100%; border: none;
  }
  #nss-editor-close {
    position: absolute; top: 8px; left: -36px; z-index: 10000;
    background: #d94444; color: #fff; border: none;
    border-radius: 50%; width: 28px; height: 28px;
    font-size: 16px; cursor: pointer; display: flex;
    align-items: center; justify-content: center;
    box-shadow: 0 2px 6px rgba(0,0,0,0.2);
  }
  #nss-editor-scrim {
    position: fixed; top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.2); z-index: 9997;
    display: none; transition: opacity 0.3s;
  }
  #nss-editor-scrim.open { display: block; }
</style>
<div id="nss-editor-scrim"></div>
<div id="nss-editor-overlay">
  <button id="nss-editor-close" title="Close editor">&times;</button>
  <iframe src="/editor/" title="HOCON Config Editor"></iframe>
</div>
<button id="nss-editor-toggle" title="Open HOCON Config Editor">Editor</button>
<script>
(function() {
  var btn = document.getElementById('nss-editor-toggle');
  var overlay = document.getElementById('nss-editor-overlay');
  var scrim = document.getElementById('nss-editor-scrim');
  var closeBtn = document.getElementById('nss-editor-close');
  var isOpen = false;
  function toggle() {
    isOpen = !isOpen;
    overlay.classList.toggle('open', isOpen);
    scrim.classList.toggle('open', isOpen);
    btn.textContent = isOpen ? 'Close Editor' : 'Editor';
  }
  btn.addEventListener('click', toggle);
  closeBtn.addEventListener('click', toggle);
  scrim.addEventListener('click', toggle);
})();
</script>
<!-- /NSS Config Editor Integration -->
"""


# ---------------------------------------------------------------------------
# ASGI middleware: inject editor button into nsflow HTML responses
# ---------------------------------------------------------------------------
class HTMLInjectionMiddleware:
    """Raw ASGI middleware that injects the editor button/iframe into HTML responses.

    Uses raw ASGI protocol (not BaseHTTPMiddleware) to correctly handle
    WebSocket pass-through and streaming responses.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            # WebSocket and other non-HTTP scopes pass through untouched
            await self.app(scope, receive, send)
            return

        # Buffer HTTP responses to check content-type and inject HTML
        start_message = None
        body_parts: list[bytes] = []
        is_html = False

        async def buffered_send(message: dict) -> None:
            nonlocal start_message, is_html

            if message["type"] == "http.response.start":
                headers = dict(
                    (k.lower(), v)
                    for k, v in message.get("headers", [])
                )
                content_type = headers.get(b"content-type", b"")
                is_html = b"text/html" in content_type

                if not is_html:
                    await send(message)
                else:
                    start_message = message
                return

            if message["type"] == "http.response.body":
                if not is_html:
                    await send(message)
                    return

                body_parts.append(message.get("body", b""))
                more_body = message.get("more_body", False)

                if not more_body:
                    full_body = b"".join(body_parts)
                    full_body = _inject_into_html(full_body)

                    # Update content-length in the start message
                    new_headers = [
                        (k, v)
                        for k, v in start_message.get("headers", [])
                        if k.lower() != b"content-length"
                    ]
                    new_headers.append(
                        (b"content-length", str(len(full_body)).encode())
                    )
                    start_message["headers"] = new_headers
                    await send(start_message)
                    await send(
                        {
                            "type": "http.response.body",
                            "body": full_body,
                            "more_body": False,
                        }
                    )

        await self.app(scope, receive, buffered_send)


def _inject_into_html(body: bytes) -> bytes:
    """Insert the editor snippet before </body> in an HTML document."""
    html = body.decode("utf-8", errors="replace")
    marker = "</body>"
    idx = html.lower().rfind(marker.lower())
    if idx == -1:
        return body
    return (html[:idx] + _INJECTION_SNIPPET + html[idx:]).encode("utf-8")


# ---------------------------------------------------------------------------
# Build the combined ASGI application
# ---------------------------------------------------------------------------
config_editor_enabled = os.environ.get("CONFIG_EDITOR_ENABLED", "true").lower() == "true"

if config_editor_enabled:
    injected_nsflow = HTMLInjectionMiddleware(nsflow_app)
    combined_app = Starlette(
        routes=[
            Mount("/editor", app=editor_app),
            Mount("/", app=injected_nsflow),
        ]
    )
else:
    combined_app = nsflow_app


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    host = os.environ.get("NSFLOW_HOST", "0.0.0.0")
    port = int(os.environ.get("NSFLOW_PORT", "4173"))
    uvicorn.run(combined_app, host=host, port=port)
