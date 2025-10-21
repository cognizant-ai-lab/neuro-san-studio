# Copyright (C) 2023-2025 Cognizant Digital Business, Evolutionary AI.
# All Rights Reserved.
# Issued under the Academic Public License.
#
# You can be released from the terms, and requirements of the Academic Public
# License by purchasing a commercial license.
# Purchase of a commercial license is mandatory for any use of the
# neuro-san-studio SDK Software in commercial settings.
#
import os
from typing import Any
from typing import Dict
from typing import Union

from neuro_san.interfaces.coded_tool import CodedTool
from pypdf import PdfReader


class ExtractDocs(CodedTool):
    """
    CodedTool implementation extracts text from all PDFs in the given directory.
    Returns a dictionary mapping each PDF file name to its extracted text.
    """

    def __init__(self):
        self.default_path = ["coded_tools/airline_policy/knowdocs/Help Center.txt"]

        self.docs_path = {
            "Bag Issues": "coded_tools/airline_policy/knowdocs/baggage/bag-issues",
            "Carry On Baggage": "coded_tools/airline_policy/knowdocs/baggage/carryon",
            "Checked Baggage": "coded_tools/airline_policy/knowdocs/baggage/checked",
            "Special Items": "coded_tools/airline_policy/knowdocs/baggage/special-items",
            "Military Personnel": "coded_tools/airline_policy/knowdocs/flight/military-personnel",
            "Mileage Plus": "coded_tools/airline_policy/knowdocs/flight/mileage-plus",
            "Basic Economy Restrictions": "coded_tools/airline_policy/knowdocs/flight/basic-econ",
            "International Checked Baggage": "coded_tools/airline_policy/knowdocs/international",
            "Embargoes": "coded_tools/airline_policy/knowdocs/international",
        }

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        :param args: An argument dictionary with the following keys:
            - "directory" (str): The directory containing the documents.

        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
            but whose values are meant to be kept out of the chat stream.

            This dictionary is largely to be treated as read-only.
            It is possible to add key/value pairs to this dict that do not
            yet exist as a bulletin board, as long as the responsibility
            for which coded_tool publishes new entries is well understood
            by the agent chain implementation and the coded_tool implementation
            adding the data is not invoke()-ed more than once.

            Keys expected for this implementation are:
                None

        :return:
            If successful:
                A dictionary containing extracted text with the keys:
                - "file_name": The path and name of the processed document file.
                - "text": The extracted text from the document.
            Otherwise:
                A text string error message in the format:
                "Error: <error message>"
        """
        app_name: str = args.get("app_name", None)
        print("############### PDF text reader ###############")
        print(f"App name: {app_name}")
        if app_name is None:
            return "Error: No app name provided."
        directory = self.docs_path.get(app_name, self.default_path)

        if not isinstance(directory, (str, bytes, os.PathLike)):
            raise TypeError(f"Expected str, bytes, or os.PathLike object, got {type(directory).__name__} instead")

        docs = {}
        for root, dirs, files in os.walk(directory):
            for file in files:
                # Build the full path to the file
                file_path = os.path.join(root, file)

                if file.lower().endswith(".pdf"):
                    # Extract PDF content
                    content = self.extract_pdf_content(file_path)
                    # Store in the dictionary using a relative path (relative to the main directory)
                    rel_path = os.path.relpath(file_path, directory)
                    docs[rel_path] = content
                elif file.lower().endswith(".txt"):
                    # Extract text file content
                    content = self.extract_txt_content(file_path)
                    # Store in the dictionary using a relative path
                    rel_path = os.path.relpath(file_path, directory)
                    docs[rel_path] = content
        print("############### Documents extraction done ###############")
        if not docs:
            print("No PDF or text files found in the directory.")
            return {"docs": {}}
        return {"files": docs}

    def extract_pdf_content(self, pdf_path: str) -> str:
        """
        Extract text from a PDF file using pypdf, while attempting to preserve
        pagination (by inserting page headers).

        :param pdf_path: Full path to the PDF file.
        :return: Extracted text from the PDF.
        """
        text_output = []
        try:
            reader = PdfReader(pdf_path)
            for page_num, page in enumerate(reader.pages):
                # Add a page header for pagination
                text_output.append(f"\n\n--- Page {page_num + 1} ---\n\n")
                # Extract text from the page (fall back to empty string if None)
                page_text = page.extract_text() or ""
                text_output.append(page_text)
        except Exception as e:
            # In case there's an issue with reading the PDF
            print(f"Error reading PDF {pdf_path}: {e}")
            return ""

        return "".join(text_output)

    def extract_txt_content(self, txt_path: str) -> str:
        """
        Extract text from a plain text file.

        :param txt_path: Full path to the TXT file.
        :return: Content of the text file.
        """
        try:
            with open(txt_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            # In case there's an issue with reading the text file
            print(f"Error reading TXT {txt_path}: {e}")
            return ""
