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
from typing import Dict
from typing import Union

from neuro_san.interfaces.coded_tool import CodedTool


class OrderAPI(CodedTool):
    """
    Places an order with a shop.
    """

    SHOP_1 = "Bob's Coffee Shop"
    SHOP_2 = "Henry's Fast Food"
    SHOP_3 = "Joe's Gas Station"
    SHOP_4 = "Jack's Liquor Store"
    SHOPS = [SHOP_1, SHOP_2, SHOP_3, SHOP_4]
    FIRST_ORDER_ID = {SHOP_1: 100, SHOP_2: 200, SHOP_3: 300, SHOP_4: 400}

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
        print(">>>>>>>>>>>>>>>>>>> OrderAPI >>>>>>>>>>>>>>>>>>")
        # Client name is required to place an order.
        customer_name: str = args.get("customer_name", None)
        if not customer_name:
            print("No customer name provided. Trying to get it from sly_data")
            customer_name = sly_data.get("username")
        if not customer_name:
            error = "Error: Please provide a valid customer name for the order."
            print(error)
            return error

        # Now we have a client name. Keep it in the sly_data if it wasn't there before.
        if sly_data.get("username", None) is None:
            sly_data["username"] = customer_name

        # Shop name is required to place an order.
        shop: str = args.get("shop_name", None)
        if not shop:
            error = "Error: Please provide the name of the shop for the order."
            print(error)
            return error
        if shop not in OrderAPI.SHOPS:
            error = "Error: Please provide a valid shop name. Known shops are: " + ", ".join(OrderAPI.SHOPS)
            print(error)
            return error

        # Details of the order are required to place an order.
        order: str = args.get("order_details", None)
        if not order:
            error = "Error: Please provide the description of what to order."
            print(error)
            return error

        order_id = OrderAPI.FIRST_ORDER_ID[shop] + 1  # Simulating an order ID generation

        message = f"Order {order_id} placed successfully for {customer_name} at {shop}. Details: {order}"
        print(message)
        print(">>>>>>>>>>>>>>>>>>> DONE !!! >>>>>>>>>>>>>>>>>>")
        return message

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        Delegates to the synchronous invoke method because it's quick, non-blocking.
        """
        return self.invoke(args, sly_data)
