# Copyright © 2026 Cognizant Technology Solutions Corp, www.cognizant.com.
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
Tests that Copyist calls its temporary agent network through the ActivationCapsule handed to it in its args.
"""

from typing import Any
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import call
from unittest.mock import patch

from neuro_san.interfaces.activation_capsule import ActivationCapsule
from neuro_san.interfaces.reservation import Reservation
from neuro_san.internals.graph.persistence.agent_network_restorer import AgentNetworkRestorer
from neuro_san.internals.graph.registry.agent_network import AgentNetwork
from neuro_san.internals.reservations.reservation_util import ReservationUtil

from coded_tools.experimental.copy_cat.copyist import Copyist


class TestCopyist(IsolatedAsyncioTestCase):
    """
    Tests for Copyist's use of the ActivationCapsule.

    The network file and the reservation are stubbed, so no file is read and no temporary network is deployed.
    """

    async def test_call_text_goes_to_the_reservation_through_the_capsule(self) -> None:
        """
        The temporary network is called via the capsule's use_reservation(), given the Reservation itself.
        """
        capsule: MagicMock = MagicMock(spec=ActivationCapsule)
        capsule.use_reservation = AsyncMock(return_value="Hallo, globe.")
        reservation: MagicMock = MagicMock(spec=Reservation)
        reservation.get_reservation_id.return_value = "copy_cat-hello_world-1234"
        reservation.get_lifetime_in_seconds.return_value = 300.0
        reservation.get_expiration_time_in_seconds.return_value = 1000.0
        network: MagicMock = MagicMock(spec=AgentNetwork)
        network.get_config.return_value = {"tools": []}
        sly_data: dict[str, Any] = {}
        args: dict[str, Any] = {
            "agent_name": "basic/hello_world",
            "call_text": "Hello, world.",
            "activation_capsule": capsule,
        }

        with (
            patch.object(AgentNetworkRestorer, "restore", return_value=network),
            patch.object(ReservationUtil, "wait_for_one", new=AsyncMock(return_value=(reservation, None))),
        ):
            result: str = await Copyist().async_invoke(args, sly_data)

        self.assertEqual(result, "Hallo, globe.")
        self.assertEqual(
            capsule.use_reservation.await_args_list,
            [call(reservation, {"input": "Hello, world."}, sly_data)],
        )

    async def test_missing_activation_capsule_returns_before_reserving(self) -> None:
        """
        With call_text but no ActivationCapsule, a message comes back and no reservation is made.
        """
        wait_for_one: AsyncMock = AsyncMock()
        args: dict[str, Any] = {
            "agent_name": "basic/hello_world",
            "call_text": "Hello, world.",
        }

        with (
            patch.object(ReservationUtil, "wait_for_one", new=wait_for_one),
            self.assertLogs("Copyist", level="ERROR"),
        ):
            result: str = await Copyist().async_invoke(args, {})

        self.assertEqual(result, "No activation_capsule available to call the temporary agent.")
        self.assertEqual(wait_for_one.await_count, 0)
