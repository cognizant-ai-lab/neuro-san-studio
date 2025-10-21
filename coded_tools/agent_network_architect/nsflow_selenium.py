# Copyright (C) 2023-2025 Cognizant Digital Business, Evolutionary AI.
# All Rights Reserved.
# Issued under the Academic Public License.
#
# You can be released from the terms, and requirements of the Academic Public
# License by purchasing a commercial license.
# Purchase of a commercial license is mandatory for any use of the
# neuro-san-studio SDK Software in commercial settings.
#
# END COPYRIGHT

import asyncio
import os
import time
from typing import Any
from typing import Dict
from typing import Optional

from neuro_san.interfaces.coded_tool import CodedTool

# pylint: disable=import-error
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

TIME_TO_FIND_ELEMENT = 120.0
TIME_BEFORE_CLICK_SEND = 2.0
TIME_AFTER_RESPONSE_BEFORE_CLOSE = 10.0


class NsflowSelenium(CodedTool):
    """
    CodedTool implementation which opens nsflow in Chrome, enters text input,
    submits the input, waits for the response, and closes the browser.
    """

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        :param args: An argument dictionary whose keys are the parameters
            to the coded tool and whose values are the values passed for
            them by the calling agent.  This dictionary is to be treated as
            read-only.

            The argument dictionary expects the following keys:
                "agent_name": Name of the network to run
                "query": Input for the agent network
                "url": URL of nsflow to run the network
                "time_to_find_element": Maximum seconds to wait for page elements to appear
                "time_before_click_send": Seconds to wait after typing the query before clicking send
                "time_after_response_before_close": Seconds to wait after receiving response before closing the browser

        :param sly_data: A dictionary whose keys are defined by the agent
            hierarchy, but whose values are meant to be kept out of the
            chat stream.

            This dictionary is largely to be treated as read-only.
            It is possible to add key/value pairs to this dict that do not
            yet exist as a bulletin board, as long as the responsibility
            for which coded_tool publishes new entries is well understood
            by the agent chain implementation and the coded_tool
            implementation adding the data is not invoke()-ed more than
            once.

            Keys expected for this implementation are:
                "agent_name"
        :return: successful sent message ID or error message
        """

        # Extract arguments from the input dictionary

        # Required arguments

        # Extract "agent_name" from args if it is not available use sly_data.
        # Try to get "agent_name" from args; if the corresponding HOCON file doesn't exist, fall back to sly_data.
        agent_name: str = args.get("agent_name")
        hocon_file = f"registries/{agent_name}.hocon"

        if not os.path.isfile(hocon_file):
            print(f"Cannot find agent network HOCON file for '{agent_name}' from args.")
            print("Attempting to get 'agent_name' from sly_data instead.")
            agent_name = sly_data.get("agent_network_name")
            hocon_file = f"registries/{agent_name}.hocon"

        # Final validation: ensure agent_name is set and the file exists.
        if not agent_name or not os.path.isfile(hocon_file):
            return f"Error: HOCON file not found for agent '{agent_name}'. Expected at: registries/{agent_name}.hocon"

        query: str = args.get("query")
        url: str = args.get("url")

        # Validate presence of required inputs
        if not query:
            return "Error: No query provided."
        if not url:
            return "Error: No url provided"

        # Optional arguments
        time_to_find_element: float = args.get("time_to_find_element", TIME_TO_FIND_ELEMENT)
        time_before_click_send: float = args.get("time_before_click_send", TIME_BEFORE_CLICK_SEND)
        time_after_response_before_close: float = args.get(
            "time_after_response_before_close", TIME_AFTER_RESPONSE_BEFORE_CLOSE
        )

        return connect_run_agent_nsflow(
            url, agent_name, query, time_to_find_element, time_before_click_send, time_after_response_before_close
        )

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """Run invoke asynchronously."""
        return await asyncio.to_thread(self.invoke, args, sly_data)


# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
def connect_run_agent_nsflow(
    url: str,
    agent_name: str,
    query: str,
    time_to_find_element: Optional[float] = TIME_TO_FIND_ELEMENT,
    time_before_click_send: Optional[float] = TIME_BEFORE_CLICK_SEND,
    time_after_response_before_close: Optional[float] = TIME_AFTER_RESPONSE_BEFORE_CLOSE,
) -> str:
    """
    Automates interaction with a web-based agent interface using Selenium WebDriver.

    Opens the specified URL of nsflow client, selects an agent by name from the sidebar, sends a query message,
    waits for the agent's response, then returns the response text. Handles timeouts and WebDriver errors gracefully.

    :param url: The URL of the web page hosting the agent interface.
    :param agent_name: The exact name of the agent to interact with (must match the sidebar button text).
    :param query: The text query to send to the agent.
    :param time_to_find_element: Maximum seconds to wait for page elements to appear.
    :param time_before_click_send: Seconds to wait after typing the query before clicking send.
    :param time_after_response_before_close: Seconds to wait after receiving response before closing the browser.

    :return: A formatted string containing the original query and the agent's response,
                or an error message if a timeout or WebDriver error occurs.
    """

    # Set up Chrome window size to max
    options = Options()
    options.add_argument("--start-maximized")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        driver.get(url)

        wait = WebDriverWait(driver, time_to_find_element)

        # Click the sidebar button with text {agent_name}
        click_sidebar(wait, agent_name)

        # Type a message into the chat input
        type_message(wait, query)

        # Wait before clicking send
        time.sleep(time_before_click_send)

        # Click the Send button
        click_send(wait)

        # Wait for the response box (<span>{agent_name}</span>) to appear
        response = get_response(driver, wait, agent_name)

        print(f"Agent response: {response}")
        print(
            f"Agent {agent_name} response detected, waiting "
            f"{time_after_response_before_close} seconds before closing the browser."
        )

        time.sleep(time_after_response_before_close)

        return f"Query: {query}\nResponse: {response}"

    except TimeoutException as timeout_error:
        timeout_error_msg = "Timed out waiting for page to load or element to appear."
        print(f"{timeout_error_msg}")
        print(timeout_error)
        return timeout_error_msg
    except WebDriverException as webdriver_error:
        webdriver_error_msg = "WebDriver encountered an issue."
        print(f"{webdriver_error_msg}")
        print(webdriver_error)
        return webdriver_error_msg

    finally:
        # Close browser after finish testing
        driver.quit()


def click_sidebar(wait: WebDriverWait, agent_name: str):
    """
    Waits for and clicks the sidebar button corresponding to the given agent name.

    :param wait: WebDriverWait instance for waiting on elements.
    :param agent_name: The exact name of the agent whose sidebar button to click.
    """
    button = wait.until(
        EC.element_to_be_clickable((By.XPATH, f"//button[contains(@class, 'sidebar-btn') and text()='{agent_name}']"))
    )
    button.click()


def type_message(wait: WebDriverWait, query: str):
    """
    Waits for the chat input box to appear, then types the query message into it.

    :param wait: WebDriverWait instance for waiting on elements.
    :param query: The message text to type into the chat input.
    """
    chat_input = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "chat-input-box")))
    chat_input.click()
    chat_input.clear()
    chat_input.send_keys(query)


def click_send(wait: WebDriverWait):
    """
    Waits for and clicks the Send button in the chat interface.

    :param wait: WebDriverWait instance for waiting on elements.
    """
    send_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "chat-send-btn")))
    send_button.click()


def get_response(driver: WebDriver, wait: WebDriverWait, agent_name: str) -> str:
    """
    Waits for the agent's response element to appear, then retrieves and returns
    the last message text from the chat.

    :param driver: The Selenium WebDriver instance.
    :param wait: WebDriverWait instance for waiting on elements.
    :param agent_name: The exact name of the agent whose response to retrieve.
    :return: The text content of the agent's last chat response, or a default message if none found.
    """
    wait.until(
        EC.presence_of_element_located((By.XPATH, f"//div[contains(@class, 'font-bold')]/span[text()='{agent_name}']"))
    )
    # Find all texts in the text boxes
    # The agent responses should be the last one
    elements = driver.find_elements(By.CSS_SELECTOR, "div.chat-markdown > p")

    return elements[-1].text if elements else "No agent response found"
