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

# The network's top-level "metadata" block, exactly as written into the saved network and as
# connectivity() serves it, minus the reservation/stored_at keys neuro-san's reservation storage adds
# to a temporary network. The designer is stateless, so the client owns this block the way it owns
# the definition and the name: AgentNetworkPersistenceMiddleware returns it after every save and reads
# it back from the next request, adding only the sample queries and (file mode) timestamps the server
# produced itself (issue #1398).
AGENT_NETWORK_METADATA: str = "agent_network_metadata"

# Name of the agent network, used as the persistence file path or reservation identifier.
AGENT_NETWORK_NAME: str = "agent_network_name"

# Cached ProgressHandler instance controls AGENT_PROGRESS reporting throttling
PROGRESS_HANDLER: str = "progress_handler"

# Name of the sly_data lock (see SlyDataLock.get_lock) guarding the entry above.
# Defined here because SlyDataLock creates a fresh lock for any unknown name —
# a typo'd literal would silently hand out a second, independent lock.
PROGRESS_HANDLER_LOCK: str = "progress_handler_lock"
