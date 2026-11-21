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

from contextvars import ContextVar


class IdempotencyContext:  # pylint: disable=too-few-public-methods
    """
    Carries the idempotency key from ProvenanceMiddleware to the tool, outside the LLM-visible arguments.

    Not an argument because neuro-san drops arguments the HOCON schema does not declare (tested), and declaring one
    would show it to the LLM. The middleware sets KEY just before awaiting the tool; the value is visible only inside
    that call's async context.
    """

    KEY: ContextVar[str | None] = ContextVar("idempotency_key", default=None)
