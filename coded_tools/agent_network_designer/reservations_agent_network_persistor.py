# Copyright (C) 2023-2025 Cognizant Digital Business, Evolutionary AI.
# All Rights Reserved.
# Issued under the Academic Public License.
#
# You can be released from the terms, and requirements of the Academic Public
# License by purchasing a commercial license.
# Purchase of a commercial license is mandatory for any use of the
# neuro-san-studio SDK Software in commercial settings.
#
from typing import Any

from neuro_san.interfaces.reservation import Reservation
from neuro_san.internals.reservations.reservation_util import ReservationUtil

from coded_tools.agent_network_designer.agent_network_persistor import AgentNetworkPersistor


# pylint: disable=too-few-public-methods
class ReservationsAgentNetworkPersistor(AgentNetworkPersistor):
    """
    AgentNetworkPersistor implementation that saves a temporary network
    using the neuro-san Reservations API
    """

    def __init__(self, args: dict[str, Any]):
        """
        Creates a new persistor of the specified type.

        :param args: The arguments from the calling CodedTool.
                    It should contain a Reservationist instance.
        """
        self.args: dict[str, Any] = args

    async def async_persist(self, obj: dict[str, Any], file_reference: str = None) -> str | list[dict[str, Any]]:
        """
        Persists the object passed in.

        :param obj: an object to persist.
                In this case this is the agent network dictionary spec.
        :param file_reference: The file reference to use when persisting.
                Default is None, implying the file reference is up to the
                implementation.
        :return an object describing the location to which the object was persisted
                If the return value is a string, an error has occurred.
                Otherwise, it is a list of agent reservation dictionaries.
        """
        agent_spec: dict[str, Any] = obj
        agent_prefix: str = file_reference
        lifetime_in_seconds: float = 60.0 * 60.0    # For now

        reservation: Reservation = None
        error: str = None
        reservation, error = await ReservationUtil.wait_for_one(
            self.args, agent_spec, lifetime_in_seconds, agent_prefix
        )

        if error is not None:
            return error

        agent_reservations: list[dict[str, Any]] = [{
            "reservation_id": reservation.get_reservation_id(),
            "lifetime_in_seconds": reservation.get_lifetime_in_seconds(),
            "expiration_time_in_seconds": reservation.get_expiration_time_in_seconds(),
        }]

        return agent_reservations
