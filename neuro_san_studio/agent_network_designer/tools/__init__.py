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
The designer's coded tools. A network or module that still names a class by an old name in this package gets the
class from its new module, with a deprecation warning logged the first time each name is used.
"""

from typing import Any
from typing import Callable
from typing import Type

from leaf_common.resolution.deprecation_redirect import DeprecationRedirect

# Each old and new class name stays whole on one line, so that it can be searched for.
_DEPRECATION_REDIRECT = DeprecationRedirect(
    __name__,
    {
        "neuro_san_studio.agent_network_designer.tools.get_subnetwork.GetSubnetwork": "neuro_san_studio.agent_network_designer.tools.get_external_network.GetExternalNetwork",  # noqa: E501
    },
)

# Python calls a package's __getattr__ for a name the package does not define, which is how an old class name
# reaches the redirect.
__getattr__: Callable[[str], Type[Any]] = _DEPRECATION_REDIRECT.redirect_class
