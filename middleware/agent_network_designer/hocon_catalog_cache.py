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
The one copy of the resolve/load/validate/fingerprint discipline for the
designer's env-var-pathed HOCON catalogs (the external-agents catalog and the
middleware-info catalog).

The two consuming middlewares keep only their failure POLICY — the external
agents gate fails closed with a client-safe error, the info injector warns and
skips — while everything they must otherwise keep in lockstep lives here once:
path resolution, empty-path and root-shape rejection, the empty-catalog
breadcrumb, load-failure normalization, and the freshness fingerprint.

The designer's other shared loads — GetToolbox, GetSubnetwork, and GetMcpTool
in coded_tools/agent_network_editor, candidates for recasting as middlewares
like the two above — sit on the same SharedProcessCache but are NOT tenants of
this class: each deliberately differs in a policy this class fixes.

* Parse: they use special-purpose restorers (ToolboxInfoRestorer, the manifest
  filter chain, McpServersInfoRestorer) where this class does a raw HOCON read.
* Empty results: the toolbox treats an empty mapping as a failed read and
  raises; MCP treats a missing file as an authoritative empty and publishes
  it; this class publishes empty with a warning breadcrumb.
* Freshness: the toolbox cache is deliberately immortal (lockstep with the
  shared ToolboxFactory); the manifest and MCP fingerprints carry time-bucket
  components that this class's (path, size, mtime) probe does not.

Recasting those tools as middlewares reuses the SHAPE of the two consumers
here (a class-level cache, prompt injection in awrap_model_call, an explicit
degrade policy — see MiddlewareInfoMiddleware for the template); hosting their
file loads in this class would mean growing the three policy knobs above.
Their network fan-out halves (subnetwork description fetches, MCP tool
listings) are not file catalogs at all and stay on SharedProcessCache directly.
"""

import logging
import os
from typing import Any
from typing import Callable

from neuro_san.internals.persistence.abstract_async_config_restorer import AbstractAsyncConfigRestorer
from pyparsing.exceptions import ParseException

from coded_tools.agent_network_editor.and_logger import AndLogger
from coded_tools.agent_network_editor.shared_process_cache import SharedProcessCache
from middleware.agent_network_designer.catalog_load_error import CatalogLoadError


# One attribute over pylint's cap of 7: six configuration knobs (each consumed
# in a different place, so grouping any two would be an arbitrary pairing) plus
# the logger and the wrapped cache.
# pylint: disable-next=too-many-instance-attributes
class HoconCatalogCache:
    """
    Process-wide cache of one env-var-pathed HOCON catalog.

    Wraps SharedProcessCache with the discipline both designer catalog
    middlewares need:

    * Path resolution: an explicit env var always wins (including an explicitly
      empty one, rejected below rather than silently yielding an empty catalog);
      otherwise the working-directory repo/project layout, falling back to the
      copy bundled beside the consuming module so scaffolded projects and
      installed wheels work without configuration.
    * Rejection of empty paths (restore() returns None for them BEFORE its
      must_exist check ever runs) and of non-mapping roots (a root-level array
      parses fine but is not a catalog) — both raise instead of publishing, so
      recovery needs only a file fix, never a restart.
    * A warning breadcrumb for an empty catalog: legitimate config, but
      indistinguishable from an accidentally truncated file.
    * Load failures normalized into CatalogLoadError; nothing is published on a
      raise, so the next call retries.
    * A (path, size, modification-time) fingerprint, so an edited file, a
      changed env var, and a same-clock-tick truncate-then-write all register
      as a miss and trigger a reload.
    """

    # pylint: disable-next=too-many-arguments
    def __init__(
        self,
        *,
        env_var: str,
        default_file: str,
        bundled_file: str,
        file_purpose: str,
        empty_effect: str,
        transform: Callable[[dict[str, Any]], Any] | None = None,
    ):
        """
        :param env_var: Name of the environment variable that overrides the path.
        :param default_file: Working-directory-relative path used when the env
                var is unset (the repo / `ns init` project layout).
        :param bundled_file: The copy shipped beside the consuming module; the
                fallback when the working directory has no layout copy.
        :param file_purpose: AbstractAsyncConfigRestorer purpose string.
        :param empty_effect: One clause describing what an empty catalog means,
                spliced into the breadcrumb warning (e.g. "no external-agent
                tools will be gated").
        :param transform: Optional post-parse projection of the catalog dict
                into the cached value (e.g. pre-rendering a prompt section), run
                once per load instead of once per model call. Must not return
                None — that is the cache's miss sentinel.
        """
        self.env_var = env_var
        self.default_file = default_file
        self.bundled_file = bundled_file
        self.file_purpose = file_purpose
        self.empty_effect = empty_effect
        self.transform = transform
        self.logger = AndLogger(logging.getLogger(f"{self.__class__.__name__}({env_var})"))
        self._cache: SharedProcessCache[Any] = SharedProcessCache(
            loader=self._load,
            fingerprint=self._fingerprint,
        )

    def resolve_file(self) -> str:
        """
        :return: The catalog path per the resolution order in the class docstring.
        """
        env_path: str | None = os.getenv(self.env_var)
        if env_path is not None:
            return env_path
        if os.path.isfile(self.default_file):
            return self.default_file
        return self.bundled_file

    def _load(self) -> Any:
        """
        SharedProcessCache loader: read, parse, validate, and transform the catalog.

        Runs in a worker thread (reached through aget()), so the blocking file
        read and HOCON parse stay off the event loop.

        :return: transform(catalog) when a transform was given, else the catalog
                dict ({} for an empty file — loaders must never return None).
        :raises CatalogLoadError: when the catalog cannot be read or parsed.
        """
        catalog_file: str = self.resolve_file()
        try:
            if not catalog_file:
                raise ValueError(f"{self.env_var} is set to an empty string")
            restorer = AbstractAsyncConfigRestorer(file_purpose=self.file_purpose, must_exist=True)
            catalog: dict[str, Any] = restorer.restore(file_reference=catalog_file)
            if catalog is not None and not isinstance(catalog, dict):
                raise ValueError(f"catalog root must be a mapping, got {type(catalog).__name__}")
        except (OSError, ValueError, ParseException) as error:
            # OSError covers FileNotFoundError / PermissionError / IsADirectoryError;
            # ValueError is raised for unsupported file extensions and is what current
            # neuro-san re-wraps HOCON/JSON parse failures into; ParseException stays
            # in the tuple defensively for neuro-san versions that surface its own
            # ParseException wrapper directly.
            raise CatalogLoadError(
                f"Catalog for {self.env_var} could not be loaded from '{catalog_file}': {error}"
            ) from error

        if not catalog:
            self.logger.warning("Catalog '%s' is empty: %s.", catalog_file, self.empty_effect)
            catalog = {}
        if self.transform is not None:
            return self.transform(catalog)
        return catalog

    def _fingerprint(self) -> tuple[str, tuple[int, int] | None]:
        """
        SharedProcessCache fingerprint: the resolved path plus its (size,
        modification time). Cheap and never raises, per the fingerprint contract.
        """
        catalog_file: str = self.resolve_file()
        return catalog_file, SharedProcessCache.stat_size_and_modification_time_ns(catalog_file)

    async def aget(self) -> Any:
        """
        :return: The cached (or freshly loaded) catalog value; see _load().
        :raises CatalogLoadError: when the catalog cannot be read or parsed.
        """
        return await self._cache.aget()

    def clear_for_testing(self):
        """
        Reset the process-wide cache. For test isolation only — production code
        relies on the load-once-with-fingerprint semantics.
        """
        self._cache.clear_for_testing()
