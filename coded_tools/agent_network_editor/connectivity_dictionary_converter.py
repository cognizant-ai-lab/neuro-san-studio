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
from typing import Any

from leaf_common.serialization.interface.dictionary_converter import DictionaryConverter

# Reaching into neuro_san internals because we expect to know the gory details here because
# we are building agent networks.  This is not normally a recommended practice.
from neuro_san.internals.chat.connectivity_reporter import ConnectivityReporter
from neuro_san.internals.run_context.interfaces.agent_network_inspector import AgentNetworkInspector

from coded_tools.agent_network_editor.designer_network_inspector import DesignerNetworkInspector


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

    def __init__(self, include_keys: list[str] = None):
        """
        Constructor
        :param include_keys: A list of keys to include in the conversion
        """
        self.include_keys = include_keys
        if include_keys is None:
            self.include_keys = ["tools", "instructions"]

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
        connectivity: Connectivity = []

        inspector: AgentNetworkInspector = DesignerNetworkInspector(obj_dict)

        reporter: ConnectivityReporter = ConnectivityReporter(inspector)
        connectivity = reporter.report_network_connectivity()

        # Add any keys that are not already in the connectivity report
        for name, internal_entry in obj_dict.items():
            # Find the corresponding entry in the connectivity list.
            found_entry: dict[str, Any] = None
            for connectivity_entry in connectivity:
                if connectivity_entry.get("origin") == name:
                    found_entry = connectivity_entry
                    break

            if found_entry is None:
                continue

            # Copy any keys that are not already in the connectivity report
            self.copy_keys_not_found(internal_entry, found_entry)

        return connectivity

    def copy_keys_not_found(self, source: dict[str, Any], dest: dict[str, Any]):
        """
        :param source: The source dictionary to copy key/value pairs from
        :param dest: The destination dictionary to copy key/value paris to
        """
        for key in self.include_keys:
            # Don't add stuff that doesn't exist in source or stuff that already exists in dest.
            if key in source and key not in dest:
                dest[key] = source.get(key)
