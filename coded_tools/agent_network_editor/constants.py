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

# Common sly_data dictionary key constants used by the agent network designer.

# Agent network structure — dict mapping agent name to its definition (instructions, description, tools),
# or the connectivity-list form used by the native Neuro-San representation.
AGENT_NETWORK_DEFINITION: str = "agent_network_definition"

# Assembled HOCON file content of the agent network, produced for client consumption.
AGENT_NETWORK_HOCON_TEXT: str = "agent_network_hocon_text"

# Name of the agent network, used as the persistence file path or reservation identifier.
AGENT_NETWORK_NAME: str = "agent_network_name"

# Cached ProgressHandler instance controls AGENT_PROGRESS reporting throttling
PROGRESS_HANDLER: str = "progress_handler"

# Name of the sly_data lock (see SlyDataLock.get_lock) guarding the entry above.
# Defined here because SlyDataLock creates a fresh lock for any unknown name —
# a typo'd literal would silently hand out a second, independent lock.
PROGRESS_HANDLER_LOCK: str = "progress_handler_lock"
