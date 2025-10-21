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
import base64
import mimetypes
import os
from email.message import EmailMessage
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

# pylint: disable=import-error
from googleapiclient.errors import HttpError
from langchain_google_community.gmail.utils import build_resource_service
from neuro_san.interfaces.coded_tool import CodedTool


class GmailAttachment(CodedTool):
    """
    CodedTool implementation which provides a way to send message with attachment
    """

    def __init__(self):
        # Create the Gmail API client
        self.service = build_resource_service()

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        :param args: An argument dictionary whose keys are the parameters
            to the coded tool and whose values are the values passed for
            them by the calling agent.  This dictionary is to be treated as
            read-only.

            The argument dictionary expects the following keys:
                to: List[str],
                attachment_path: List[str],
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
                None
        :return: successful sent message ID or error message
        """

        # Extract arguments from the input dictionary
        to: List[str] = args.get("to")
        attachment_paths: List[str] = args.get("attachment_paths")
        cc: List[str] = args.get("cc")
        bcc: List[str] = args.get("bcc")
        subject: str = args.get("subject", "")
        message: str = args.get("message", "")
        html: bool = args.get("html", False)

        # Validate presence of required inputs
        if not to:
            return "Error: No receiver provided."
        if not attachment_paths:
            return "Error: No attachment_path provided."

        return self.gmail_send_message_with_attachment(to, attachment_paths, cc, bcc, subject, message, html)

    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-positional-arguments
    def gmail_send_message_with_attachment(
        self,
        to: List[str],
        attachment_paths: List[str],
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        subject: Optional[str] = "",
        message: Optional[str] = "",
        html: Optional[bool] = False,
    ) -> str:
        """
        Sends an email with a file attachment using the Gmail API.

        :param to: List of recipient email addresses.
        :param attachment_paths: Path to the files to attach.
        :param cc: List of CC email addresses. Defaults to None.
        :param bcc: List of BCC email addresses. Defaults to None.
        :param subject: Subject line of the email. Defaults to None.
        :param message: Plain text body of the email. Defaults to None.

        :return: successful sent message ID or error statement
        """

        try:
            # Set headers
            email_message = EmailMessage()
            email_message["To"] = ", ".join(to)
            if cc:
                email_message["Cc"] = ", ".join(cc)
            if bcc:
                email_message["Bcc"] = ", ".join(bcc)
            email_message["From"] = "me"  # Gmail API will resolve authenticated sender
            if subject:
                email_message["Subject"] = subject

            # Set body message as html or plain text
            if message:
                if html:
                    email_message.add_alternative(message, subtype="html")
                else:
                    email_message.set_content(message)

            # Add attachments
            self.attach_file_to_email(email_message, attachment_paths)

            # Encode and send
            encoded_message = base64.urlsafe_b64encode(email_message.as_bytes()).decode()
            send_request_body = {"raw": encoded_message}

            sent_message = self.service.users().messages().send(userId="me", body=send_request_body).execute()

            return f"Message sent. Message ID: {sent_message['id']}"

        except HttpError as http_error:
            return f"An error occurred: {http_error}"

    def attach_file_to_email(self, email_message: EmailMessage, attachment_paths: List[str]):
        """
        Attaches one or more files to an existing EmailMessage object.

        Each file is added as an attachment with its appropriate MIME type,
        inferred from the file extension.

        :param email_message: The email message to which the files will be attached.
        :param attachment_paths: A list of file paths for the files to attach.
        """
        for path in attachment_paths:
            if not os.path.isfile(path):
                raise FileNotFoundError(f"Attachment not found: {path}")

            mime_type, _ = mimetypes.guess_type(path)
            if mime_type is None:
                mime_type = "application/octet-stream"
            maintype, subtype = mime_type.split("/")

            with open(path, "rb") as f:
                email_message.add_attachment(
                    f.read(), maintype=maintype, subtype=subtype, filename=os.path.basename(path)
                )

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """Run invoke asynchronously."""
        return await asyncio.to_thread(self.invoke, args, sly_data)
