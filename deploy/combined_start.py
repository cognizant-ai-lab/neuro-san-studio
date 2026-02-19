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

The HTML injection middleware adds a "Config Editor" button next to the
existing OEM "Editor" button in nsflow's toolbar. Clicking it opens the
config editor in a slide-in iframe overlay.

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
from nsflow.backend.main import initialize_ns_config_from_env  # noqa: E402

# ---------------------------------------------------------------------------
# Initialize nsflow config registry manually.
# When mounted as a sub-app via Starlette.Mount(), nsflow's lifespan event
# does not fire, so NsConfigsRegistry never gets initialized. Calling this
# here ensures the config is set before any requests arrive.
# ---------------------------------------------------------------------------
initialize_ns_config_from_env()


# ---------------------------------------------------------------------------
# HTML injection snippet — floating Editor button + iframe overlay
# ---------------------------------------------------------------------------
_INJECTION_SNIPPET = """
<!-- NSS Config Editor Integration -->
<style>
  #nss-editor-overlay {
    position: fixed; top: 0; right: -62%; bottom: 0; width: 60%;
    z-index: 9998; background: #fff;
    box-shadow: -4px 0 20px rgba(0,0,0,0.15);
    transition: right 0.3s ease;
    display: flex; flex-direction: column;
  }
  #nss-editor-overlay.open { right: 0; }
  #nss-editor-toolbar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 12px; height: 36px; min-height: 36px;
    background: #f5f5f5; border-bottom: 1px solid #ddd;
  }
  #nss-editor-toolbar span {
    font-weight: 600; font-size: 13px; color: #3553ad;
  }
  #nss-editor-close {
    background: #d94444; color: #fff; border: none;
    border-radius: 4px; width: 28px; height: 28px;
    font-size: 16px; cursor: pointer; display: flex;
    align-items: center; justify-content: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.2);
  }
  #nss-editor-close:hover { background: #b71c1c; }
  #nss-editor-overlay iframe {
    flex: 1; width: 100%; border: none;
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
  <div id="nss-editor-toolbar">
    <span>Config Editor</span>
    <button id="nss-editor-close" title="Close editor">&times;</button>
  </div>
  <iframe src="/editor/" title="HOCON Config Editor"></iframe>
</div>
<script>
(function() {
  var overlay = document.getElementById('nss-editor-overlay');
  var scrim = document.getElementById('nss-editor-scrim');
  var closeBtn = document.getElementById('nss-editor-close');
  var isOpen = false;
  var injectedBtn = null;

  var editorIframe = overlay.querySelector('iframe');

  function openPanel() {
    isOpen = true;
    overlay.classList.add('open');
    scrim.classList.add('open');
  }
  function closePanel() {
    isOpen = false;
    overlay.classList.remove('open');
    scrim.classList.remove('open');
  }
  function toggle() {
    if (isOpen) { tryClose(); } else { openPanel(); }
  }
  function tryClose() {
    /* Ask the iframe if there are unsaved changes before closing */
    try {
      var iframeWin = editorIframe.contentWindow;
      if (iframeWin && typeof iframeWin.hasUnsavedChanges === 'function'
          && iframeWin.hasUnsavedChanges()) {
        var action = confirm(
          'You have unsaved changes in the Config Editor.\\n\\n'
          + 'Press OK to save, or Cancel to discard changes.'
        );
        if (action && typeof iframeWin.saveCurrentFile === 'function') {
          iframeWin.saveCurrentFile();
        }
      }
    } catch(e) { /* cross-origin — just close */ }
    closePanel();
  }
  closeBtn.addEventListener('click', tryClose);
  scrim.addEventListener('click', tryClose);

  /* ---- Find OEM Editor button and inject CONFIG EDITOR next to it ---- */
  /* SVG icon: Description/document icon (config files) — copies class structure from OEM button */
  function buildIconSvg(oemBtn) {
    /* Try to copy class names from the OEM button's icon span and svg */
    var oemIcon = oemBtn.querySelector('span[class*="MuiButton-startIcon"], span[class*="icon"]');
    var oemSvg = oemBtn.querySelector('svg');
    var spanCls = oemIcon ? oemIcon.className : '';
    var svgCls = oemSvg ? oemSvg.className.baseVal || oemSvg.getAttribute('class') || '' : '';
    return '<span class="' + spanCls + '">'
      + '<svg class="' + svgCls + '" focusable="false" aria-hidden="true" viewBox="0 0 24 24">'
      + '<path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6z'
      + 'm2 16H8v-2h8v2zm0-4H8v-2h8v2zM13 9V3.5L18.5 9H13z"></path>'
      + '</svg></span>';
  }

  function findOemEditorButton() {
    /* Search all MUI buttons first, then fall back to any button with text "Editor" */
    var selectors = ['button[class*="MuiButton"]', 'button'];
    for (var s = 0; s < selectors.length; s++) {
      var buttons = document.querySelectorAll(selectors[s]);
      for (var i = 0; i < buttons.length; i++) {
        var txt = buttons[i].textContent.trim();
        if (txt === 'Editor' && buttons[i].id !== 'nss-config-editor-btn') {
          return buttons[i];
        }
      }
    }
    return null;
  }

  function injectButton() {
    if (injectedBtn && document.body.contains(injectedBtn)) return true;
    var oemBtn = findOemEditorButton();
    if (!oemBtn) return false;

    /* Clone the OEM button (shallow) to inherit all MUI classes */
    injectedBtn = oemBtn.cloneNode(false);
    injectedBtn.id = 'nss-config-editor-btn';
    injectedBtn.title = 'Open HOCON Config Editor';
    /* Build inner HTML: copy icon class structure from OEM, add our SVG path + label */
    var ripple = oemBtn.querySelector('span[class*="MuiTouchRipple"]');
    var rippleHtml = ripple ? ripple.outerHTML : '';
    injectedBtn.innerHTML = buildIconSvg(oemBtn) + 'Config Editor' + rippleHtml;
    injectedBtn.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      toggle();
    });
    /* Insert right after the OEM Editor button */
    oemBtn.parentNode.insertBefore(injectedBtn, oemBtn.nextSibling);
    return true;
  }

  /* Poll until the React SPA renders the toolbar, then observe for re-renders */
  var pollInterval = setInterval(function() {
    if (injectButton()) {
      clearInterval(pollInterval);
      /* Observe DOM changes in case React re-renders the toolbar */
      var observer = new MutationObserver(function() {
        injectButton();
      });
      observer.observe(document.body, { childList: true, subtree: true });
    }
  }, 300);

  /* ---- Theme sync: detect parent theme and postMessage to iframe ---- */
  function detectParentTheme() {
    var bg = getComputedStyle(document.body).backgroundColor;
    var match = bg.match(/\\d+/g);
    if (match) {
      var lum = 0.299 * parseInt(match[0]) + 0.587 * parseInt(match[1])
                + 0.114 * parseInt(match[2]);
      return lum < 128 ? 'dark' : 'light';
    }
    return 'light';
  }
  function sendThemeToEditor() {
    var theme = detectParentTheme();
    try {
      if (editorIframe && editorIframe.contentWindow) {
        editorIframe.contentWindow.postMessage(
          { type: 'nss-theme', theme: theme }, '*'
        );
      }
    } catch(e) {}
    /* Also style the toolbar to match */
    var tb = document.getElementById('nss-editor-toolbar');
    if (tb) {
      tb.style.background = theme === 'dark' ? '#1e1e2f' : '#f5f5f5';
      tb.style.borderBottomColor = theme === 'dark' ? '#2a2a3e' : '#ddd';
      tb.querySelector('span').style.color = theme === 'dark' ? '#7ca1f7' : '#3553ad';
    }
  }
  /* Send theme on open and poll for changes */
  var _lastParentTheme = detectParentTheme();
  setInterval(function() {
    var t = detectParentTheme();
    if (t !== _lastParentTheme) {
      _lastParentTheme = t;
      sendThemeToEditor();
    }
  }, 500);
  /* Also send theme whenever the panel opens (iframe may have just loaded) */
  var _origOpen = openPanel;
  openPanel = function() {
    _origOpen();
    setTimeout(sendThemeToEditor, 200);
  };
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
