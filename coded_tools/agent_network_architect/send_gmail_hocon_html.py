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
from typing import Any
from typing import Dict
from typing import List

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.gmail_attachment import GmailAttachment


class SendGmailHoconHtml(CodedTool):
    """
    CodedTool implementation which send gmail with hocon and html file of
    an agent network as attachments.
    """

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        :param args: An argument dictionary whose keys are the parameters
            to the coded tool and whose values are the values passed for
            them by the calling agent.  This dictionary is to be treated as
            read-only.

            The argument dictionary expects the following keys:
                to: List[str],
                attachment_paths: List[str],
                cc: List[str],
                bcc: List[str],
                subject: str,
                message: str,

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
                agent_name
        :return: successful sent message ID or error message
        """

        # Extract arguments from the input dictionary
        to: List[str] = args.get("to")
        attachment_paths: List[str] = args.get("attachment_paths", [])
        cc: List[str] = args.get("cc")
        bcc: List[str] = args.get("bcc")
        subject: str = args.get("subject", "")
        message: str = args.get("message", "")
        html: bool = args.get("html", False)

        # Validate presence of required inputs
        if not to:
            return "Error: No receiver provided."

        # Check if the path is valid.
        # The attachments should be a HOCON file and a HTML file.
        valid_attachment_paths = [path for path in attachment_paths if os.path.isfile(path)]

        # Since 2 valid files are expected, if they are not both valid, use sly_data instead.
        if len(valid_attachment_paths) < 2:
            # Extract "agent_name" from sly_data and use it to create file paths.
            agent_name: str = sly_data.get("agent_network_name")
            if not agent_name:
                return "Error: No valid attachments file path found and no agent_name provided in the sly data."
            hocon_file = f"registries/{agent_name}.hocon"
            html_file = f"{agent_name}.html"
            attachment_paths = [path for path in [hocon_file, html_file] if os.path.isfile(path)]

        # Send the email
        email = GmailAttachment()

        return email.gmail_send_message_with_attachment(
            to=to, attachment_paths=attachment_paths, cc=cc, bcc=bcc, subject=subject, message=message, html=html
        )

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """Run invoke asynchronously."""
        return await asyncio.to_thread(self.invoke, args, sly_data)
