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

import logging
from typing import Any
from typing import Dict
from typing import Union

from neuro_san.interfaces.coded_tool import CodedTool

logger = logging.getLogger(__name__)


class OrderAPI(CodedTool):
    """
    Places an order with a shop.
    """

    SHOP_1 = "Bob's Coffee Shop"
    SHOP_2 = "Henry's Fast Food"
    SHOP_3 = "Joe's Gas Station"
    SHOP_4 = "Jack's Liquor Store"
    SHOPS = [SHOP_1, SHOP_2, SHOP_3, SHOP_4]
    # First id handed out per shop on a fresh run; treated as read-only.
    FIRST_ORDER_ID = {SHOP_1: 101, SHOP_2: 201, SHOP_3: 301, SHOP_4: 401}
    # Per-shop running counter. Each successful order bumps the entry for the
    # shop, so consecutive orders in the same process get distinct ids
    # (Joe's: 301, 302, ...).
    NEXT_ORDER_ID: Dict[str, int] = dict(FIRST_ORDER_ID)

    @classmethod
    def reset_order_ids(cls) -> None:
        """
        Reset the per-shop counter back to ``FIRST_ORDER_ID``. Tests that need
        a clean order-id sequence per case should call this in ``setUp``.
        """
        cls.NEXT_ORDER_ID = dict(cls.FIRST_ORDER_ID)

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        :param args: a dictionary with the following keys:
            - shop_name: the name of the shop to order from.
            - customer_name: the name of the person to order for.
            - order_details: the details of the order.

        :param sly_data: a dictionary with the following keys:
            - username: optional - the name of the person to order for, if already known.

        :return:
            In case of successful execution:
                an order number as a string.
            otherwise:
                a string error message in the format:
                "Error: <error message>"
        """
        logger.debug(">>>>>>>>>>>>>>>>>>> OrderAPI >>>>>>>>>>>>>>>>>>")
        # Client name is required to place an order.
        customer_name: str = args.get("customer_name", None)
        if not customer_name:
            logger.debug("No customer name provided. Trying to get it from sly_data")
            customer_name = sly_data.get("username")
        if not customer_name:
            error = "Error: Please provide a valid customer name for the order."
            logger.debug(error)
            return error

        # Now we have a client name. Keep it in the sly_data if it wasn't there before.
        if sly_data.get("username", None) is None:
            sly_data["username"] = customer_name

        # Shop name is required to place an order.
        shop: str = args.get("shop_name", None)
        if not shop:
            error = "Error: Please provide the name of the shop for the order."
            logger.debug(error)
            return error
        if shop not in OrderAPI.SHOPS:
            error = "Error: Please provide a valid shop name. Known shops are: " + ", ".join(OrderAPI.SHOPS)
            logger.debug(error)
            return error

        # Details of the order are required to place an order.
        order: str = args.get("order_details", None)
        if not order:
            error = "Error: Please provide the description of what to order."
            logger.debug(error)
            return error

        # Take the current id for this shop, then advance the class-level counter
        # so the next call returns a fresh id within the same run.
        order_id = OrderAPI.NEXT_ORDER_ID.get(shop, 0)
        OrderAPI.NEXT_ORDER_ID[shop] = order_id + 1

        message = f"Order {order_id} placed successfully for {customer_name} at {shop}. Details: {order}"
        logger.debug(message)
        logger.debug(">>>>>>>>>>>>>>>>>>> DONE !!! >>>>>>>>>>>>>>>>>>")
        return message

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        Delegates to the synchronous invoke method because it's quick, non-blocking.
        """
        return self.invoke(args, sly_data)
