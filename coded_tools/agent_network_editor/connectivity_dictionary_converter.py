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
from copy import deepcopy
from typing import Any

from leaf_common.serialization.interface.dictionary_converter import DictionaryConverter

# Reaching into neuro_san internals because we expect to know the gory details here because
# we are building agent networks.  This is not normally a recommended practice.
from neuro_san.internals.chat.connectivity_reporter import ConnectivityReporter
from neuro_san.internals.interfaces.context_type_toolbox_factory import ContextTypeToolboxFactory
from neuro_san.internals.run_context.factory.master_toolbox_factory import MasterToolboxFactory
from neuro_san.internals.run_context.interfaces.agent_network_inspector import AgentNetworkInspector
from neuro_san.internals.validation.network.url_network_validator import UrlNetworkValidator

from coded_tools.agent_network_editor.designer_network_inspector import DesignerNetworkInspector
from coded_tools.agent_network_editor.shared_process_cache import SharedProcessCache

# Type definition for sanity
Connectivity = list[dict[str, Any]]


class ConnectivityDictionaryConverter(DictionaryConverter):
    """
    DictionaryConverter implementation for conversion back and forth from the
    Connectivity-style list of dictionaries to the internal dictionary for the
    network_definition that the internals of the  agent_network_editor uses.

    The idea here is that a client only needs to worry about the connectivity style
    of reporting in order to display/edit the agent network definition and not
    yet-another format.
    """

    @staticmethod
    def _load_shared_toolbox_factory() -> ContextTypeToolboxFactory:
        """
        Loader for the shared ToolboxFactory (runs inside SharedProcessCache).

        The empty config dict is equivalent to the None that
        DesignerNetworkInspector.get_config() returns: the context type defaults
        to "langchain" and any AGENT_TOOLBOX_INFO_FILE env var override is still
        honored inside ToolboxFactory.

        Returning only after load() succeeds matters twice over (the cache
        publishes nothing when this raises): on failure (e.g. a bad
        AGENT_TOOLBOX_INFO_FILE) the next call retries instead of serving a
        half-initialized factory, and — because neuro-san 0.6.83's
        ToolboxFactory.load() guards itself with a plain `loaded` flag and no
        lock — publishing a fully load()-ed instance is what makes
        ConnectivityReporter's unconditional per-report load() call a safe no-op
        on every thread that can see this factory.

        :return: A fully load()-ed ContextTypeToolboxFactory.
        """
        factory: ContextTypeToolboxFactory = MasterToolboxFactory.create_toolbox_factory({})
        factory.load()
        return factory

    # Process-wide cache of the loaded ToolboxFactory used by from_dict() when
    # no factory is passed to the constructor. The toolbox info
    # is loaded lazily on the first use in the process — the default file
    # ships inside the neuro-san package and the optional override comes from
    # the AGENT_TOOLBOX_INFO_FILE env var, both read at that first use — and
    # with no fingerprint it is deliberately never refreshed: picking up an
    # edited toolbox info file requires a process restart. (The pre-cache
    # behavior of re-loading per conversation was an accident of sly_data
    # scoping, not a supported hot-reload feature.) Locking, publish ordering,
    # and the async once-gate live in SharedProcessCache; access goes through
    # the class by name (not cls) so a hypothetical subclass shares the one
    # cache instead of splitting it.
    _shared_toolbox_factory_cache: SharedProcessCache[ContextTypeToolboxFactory] = SharedProcessCache(
        loader=_load_shared_toolbox_factory
    )

    def __init__(
        self, include_keys: list[str] | None = None, toolbox_factory: ContextTypeToolboxFactory | None = None
    ):
        """
        Constructor
        :param include_keys: A list of keys to include in the conversion
        :param toolbox_factory: An optional pre-load()-ed ContextTypeToolboxFactory
                to use for connectivity reporting. When None, from_dict() falls
                back to the process-wide shared factory (see
                get_shared_toolbox_factory()), so no caller pays the toolbox
                file read + HOCON parse more than once per process.
        """
        self.include_keys = include_keys
        if include_keys is None:
            self.include_keys = ["tools", "instructions", "description"]
        self.toolbox_factory: ContextTypeToolboxFactory | None = toolbox_factory

    @classmethod
    async def get_shared_toolbox_factory(cls) -> ContextTypeToolboxFactory:
        """
        Get the process-wide ToolboxFactory, creating and load()-ing it on
        the first call in the process: that one cold load (file I/O + HOCON
        parse) runs off the event loop, shared by concurrent cold callers;
        warm calls resolve via the lock-free peek without suspending the
        caller (the await completes immediately).

        This is the accessor call sites should use — hand-rolling the
        peek-then-to_thread dance per caller is how a caller forgets the
        pre-warm and silently blocks the event loop on a cold process. (The
        synchronous from_dict() is the one exception: it reads the
        underlying cache directly.)

        :return: The shared, already-load()-ed ToolboxFactory instance.
        """
        return await ConnectivityDictionaryConverter._shared_toolbox_factory_cache.aget()

    @classmethod
    def clear_shared_toolbox_factory_for_testing(cls):
        """
        Reset the process-wide ToolboxFactory cache. For test isolation only.

        Production code must never call this: the cache is deliberately
        load-once-per-process (see the class comment above). Tests call it
        (via tests/conftest.py) so a factory loaded under one test's
        AGENT_TOOLBOX_INFO_FILE state cannot leak into later tests. Living
        here rather than in conftest keeps all the singleton policy in this
        one class.
        """
        ConnectivityDictionaryConverter._shared_toolbox_factory_cache.clear_for_testing()

    def to_dict(self, obj: Connectivity) -> dict[str, Any]:
        """
        :param obj: The object to be converted into a dictionary
        :return: A data-only dictionary that represents all the data for
                the given object, either in primitives
                (booleans, ints, floats, strings), arrays, or dictionaries.
                If obj is None, then the returned dictionary should also be
                None.  If obj is not the correct type, it is also reasonable
                to return None.
        """
        if obj is None:
            return None

        result_dict: dict[str, Any] = {}

        connectivity: Connectivity = obj
        for connectivity_entry in connectivity:
            # The origin is the name of the agent node.
            name: str = connectivity_entry.get("origin")

            # Copy any keys that are not already in the connectivity report
            value: dict[str, Any] = {}
            self.copy_keys_not_found(connectivity_entry, value)

            # Don't include agents starting with "/", "http://", or "https://" since those are external agents.
            if not UrlNetworkValidator.is_url_or_path(name):
                result_dict[name] = value

        return result_dict

    def from_dict(self, obj_dict: dict[str, Any]) -> Connectivity:
        """
        :param obj_dict: The data-only dictionary to be converted into an object
        :return: An object instance created from the given dictionary.
                If obj_dict is None, the returned object should also be None.
                If obj_dict is not the correct type, it is also reasonable
                to return None.
        """
        if obj_dict is None:
            return None

        # Add toolbox key for toolbox agents so that connectivity reporter can set display correctly.
        obj_dict_copy: dict[str, Any] = deepcopy(obj_dict)
        for name, entry in obj_dict_copy.items():
            if not entry:
                entry["toolbox"] = name

        connectivity: Connectivity = []

        inspector: AgentNetworkInspector = DesignerNetworkInspector(obj_dict_copy)

        # Fall back to the process-wide shared factory so every from_dict()
        # caller benefits from the cache without having to pass one in.
        toolbox_factory: ContextTypeToolboxFactory | None = self.toolbox_factory
        if toolbox_factory is None:
            # from_dict() is synchronous (DictionaryConverter interface), so
            # it reads the shared cache directly — a lock-free hit once warm.
            # Async call sites pre-warm via get_shared_toolbox_factory(), so
            # in practice the blocking first load has already happened off
            # the event loop by the time this line runs.
            toolbox_factory = ConnectivityDictionaryConverter._shared_toolbox_factory_cache.get()

        reporter: ConnectivityReporter = ConnectivityReporter(inspector, toolbox_factory)
        connectivity = reporter.report_network_connectivity()

        # Add any keys that are not already in the connectivity report
        for name, internal_entry in obj_dict_copy.items():
            # Find the corresponding entry in the connectivity list.
            found_entry: dict[str, Any] = None
            for connectivity_entry in connectivity:
                if connectivity_entry.get("origin") == name:
                    found_entry = connectivity_entry
                    break

            if found_entry is None:
                # Not reachable from the front man — or there is no front man at
                # all, e.g. right after create_network when no agent has tools
                # yet, in which case the reporter walk above yields an empty
                # list. Emit the agent as an isolated node so clients can still
                # render every defined agent.
                found_entry = {"origin": name, "tools": internal_entry.get("tools", [])}
                connectivity.append(found_entry)

            # Copy any keys that are not already in the connectivity report
            self.copy_keys_not_found(internal_entry, found_entry)

        return connectivity

    def copy_keys_not_found(self, source: dict[str, Any], dest: dict[str, Any]):
        """
        :param source: The source dictionary to copy key/value pairs from
        :param dest: The destination dictionary to copy key/value pairs to
        """
        for key in self.include_keys:
            # Don't add stuff that doesn't exist in source or stuff that already exists in dest.
            if key in source and key not in dest:
                # Only put the key in dest if it has a value in source.  Don't put keys with None or empty values.
                if source.get(key):
                    dest[key] = source.get(key)
