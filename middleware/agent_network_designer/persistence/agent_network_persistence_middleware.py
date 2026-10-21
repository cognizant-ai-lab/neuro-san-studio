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
The old path of a module that moved, kept so that networks and code that name the old path keep working.
"""

from neuro_san_studio.utils.module_alias import ModuleAlias

ModuleAlias.alias(
    __name__, "neuro_san_studio.agent_network_designer.middleware.persistence.agent_network_persistence_middleware"
)
