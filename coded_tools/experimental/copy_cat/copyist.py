# Copyright © 2023-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
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
from typing import Dict

from neuro_san import REGISTRIES_DIR
from neuro_san.interfaces.coded_tool import CodedTool
from neuro_san.interfaces.reservation import Reservation
from neuro_san.internals.graph.activations.branch_activation import BranchActivation
from neuro_san.internals.graph.persistence.agent_network_restorer import AgentNetworkRestorer
from neuro_san.internals.graph.registry.agent_network import AgentNetwork
from neuro_san.internals.reservations.reservation_util import ReservationUtil


class Copyist(BranchActivation, CodedTool):
    """
    CodedTool implementation of a copyist for the copy_cat reservations example.

    The copyist needs at least a single argument, which is an existing "agent_name",
    reads that hocon file in and makes a temporary agent out of it.

    Optionally, there might be a "call_text" argument. If that is there, then immediately
    invoke the reservation's network with that input.

    The idea is merely to have a proof of concept surrounding the Reservations infrastructure.

    ---

    Upon activation by the agent hierarchy, a CodedTool will have its
    invoke() call called by the system.

    Implementations are expected to clean up after themselves.
    """

    # pylint: disable=too-many-locals
    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Any:
        """
        Called when the coded tool is invoked asynchronously by the agent hierarchy.
        Strongly consider overriding this method instead of the "easier" synchronous
        version above when the possibility of making any kind of call that could block
        (like sleep() or a socket read/write out to a web service) is within the
        scope of your CodedTool.

        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.
        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                This dictionary is largely to be treated as read-only.
                It is possible to add key/value pairs to this dict that do not
                yet exist as a bulletin board, as long as the responsibility
                for which coded_tool publishes new entries is well understood
                by the agent chain implementation and the coded_tool implementation
                adding the data is not invoke()-ed more than once.
        :return: A return value that goes into the chat stream.
        """
        copy_agent: str = args.get("agent_name")
        if copy_agent is None or len(copy_agent) == 0:
            return "Need a non-empty value for copy_agent"

        # Make sure we have a hocon file reference
        if not copy_agent.endswith(".hocon"):
            copy_agent = f"{copy_agent}.hocon"

        # Remove the .hocon suffix for this string
        use_agent_name: str = copy_agent[:-6]

        # Restore the given agent network to find its spec dictionary
        copy_file: str = REGISTRIES_DIR.get_file_in_basis(copy_agent)
        restorer = AgentNetworkRestorer()
        network: AgentNetwork = restorer.restore(file_reference=copy_file)
        my_agent_spec: Dict[str, Any] = network.get_config()

        # Creating Reservations can be done outside the with-statement
        lifetime_in_seconds: float = 5 * 60.0

        reservation: Reservation = None
        error: str = None
        reservation, error = await ReservationUtil.wait_for_one(
            sly_data, args, my_agent_spec, lifetime_in_seconds, prefix=f"copy_cat-{use_agent_name}"
        )

        if error is not None:
            return error

        # Get info from the reservation
        reservation_id: str = reservation.get_reservation_id()
        lifetime_in_seconds: float = reservation.get_lifetime_in_seconds()

        # Put the output in sly_data for less LLM "telephone" interference
        sly_data["agent_reservations"] = [
            {
                "reservation_id": reservation_id,
                "lifetime_in_seconds": lifetime_in_seconds,
                "expiration_time_in_seconds": reservation.get_expiration_time_in_seconds()
            }
        ]

        if args.get("call_text") is None:
            # Don't call the agent we just created as a tool
            return (
                f"The temporary agent name is {reservation_id}."
                + f"Hurry, it's only available for {lifetime_in_seconds} seconds."
            )

        # Call the agent we just created for our reservation
        res_args: Dict[str, Any] = {"input": args.get("call_text")}
        res_return: str = await self.use_reservation(reservation_id, res_args, sly_data)
        return res_return
