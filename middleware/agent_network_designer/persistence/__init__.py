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
Old import path for the designer's persistence middleware and its helpers. A network or module that still names a class
here gets the class from its new module, with a deprecation warning logged the first time each name is used.
"""

from typing import Any
from typing import Callable
from typing import Type

from leaf_common.resolution.deprecation_redirect import DeprecationRedirect

# Each old and new class name stays whole on one line, so that it can be searched for.
_DEPRECATION_REDIRECT = DeprecationRedirect(
    __name__,
    {
        "middleware.agent_network_designer.persistence.agent_network_assembler.AgentNetworkAssembler": "neuro_san_studio.agent_network_designer.middleware.persistence.agent_network_assembler.AgentNetworkAssembler",  # noqa: E501
        "middleware.agent_network_designer.persistence.agent_network_metadata_block.AgentNetworkMetadataBlock": "neuro_san_studio.agent_network_designer.middleware.persistence.agent_network_metadata_block.AgentNetworkMetadataBlock",  # noqa: E501
        "middleware.agent_network_designer.persistence.agent_network_persistence_middleware.AgentNetworkPersistenceMiddleware": "neuro_san_studio.agent_network_designer.middleware.persistence.agent_network_persistence_middleware.AgentNetworkPersistenceMiddleware",  # noqa: E501
        "middleware.agent_network_designer.persistence.agent_network_persistor.AgentNetworkPersistor": "neuro_san_studio.agent_network_designer.middleware.persistence.agent_network_persistor.AgentNetworkPersistor",  # noqa: E501
        "middleware.agent_network_designer.persistence.agent_network_persistor_factory.AgentNetworkPersistorFactory": "neuro_san_studio.agent_network_designer.middleware.persistence.agent_network_persistor_factory.AgentNetworkPersistorFactory",  # noqa: E501
        "middleware.agent_network_designer.persistence.common_instruction_stripper.CommonInstructionStripper": "neuro_san_studio.agent_network_designer.middleware.persistence.common_instruction_stripper.CommonInstructionStripper",  # noqa: E501
        "middleware.agent_network_designer.persistence.deployable_agent_network_assembler.DeployableAgentNetworkAssembler": "neuro_san_studio.agent_network_designer.middleware.persistence.deployable_agent_network_assembler.DeployableAgentNetworkAssembler",  # noqa: E501
        "middleware.agent_network_designer.persistence.designer_common_instructions.DesignerCommonInstructions": "neuro_san_studio.agent_network_designer.middleware.persistence.designer_common_instructions.DesignerCommonInstructions",  # noqa: E501
        "middleware.agent_network_designer.persistence.file_system_agent_network_persistor.FileSystemAgentNetworkPersistor": "neuro_san_studio.agent_network_designer.middleware.persistence.file_system_agent_network_persistor.FileSystemAgentNetworkPersistor",  # noqa: E501
        "middleware.agent_network_designer.persistence.hocon_agent_network_assembler.HoconAgentNetworkAssembler": "neuro_san_studio.agent_network_designer.middleware.persistence.hocon_agent_network_assembler.HoconAgentNetworkAssembler",  # noqa: E501
        "middleware.agent_network_designer.persistence.hocon_storability_util.HoconStorabilityUtil": "neuro_san_studio.agent_network_designer.middleware.persistence.hocon_storability_util.HoconStorabilityUtil",  # noqa: E501
        "middleware.agent_network_designer.persistence.reservations_agent_network_persistor.ReservationsAgentNetworkPersistor": "neuro_san_studio.agent_network_designer.middleware.persistence.reservations_agent_network_persistor.ReservationsAgentNetworkPersistor",  # noqa: E501
    },
)

# Python calls a package's __getattr__ for a name the package does not define, which is how an old class name
# reaches the redirect.
__getattr__: Callable[[str], Type[Any]] = _DEPRECATION_REDIRECT.redirect_class
