# Copyright (C) 2023-2025 Cognizant Digital Business, Evolutionary AI.
# All Rights Reserved.
# Issued under the Academic Public License.
#
# You can be released from the terms, and requirements of the Academic Public
# License by purchasing a commercial license.
# Purchase of a commercial license is mandatory for any use of the
# neuro-san SDK Software in commercial settings.
#
# END COPYRIGHT

from typing import Any
from typing import Dict
from typing import Union

from langchain_community.utilities import GoogleSerperAPIWrapper
from neuro_san.interfaces.coded_tool import CodedTool

# Default parameters for google serper
K = 10  # number of search results
GL = "us"  # country
HL = "en"  # langauge
TYPE = "search"  # search type


class GoogleSerper(CodedTool):
    """
    CodedTool implementation which provides a way to do website search by Google Serper
    """

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "query" the query to search for.

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
            In case of successful execution:
                A dictionary including metadata.
            otherwise:
                a text string an error message in the format:
                "Error: <error message>"
        """
        # Get query from args
        query: str = args.get("query", "")
        if query == "":
            return "Error: No query provided."

        # Parameters for google serper

        # Country code to localize search results (e.g., "us" for United States)
        gl: str = args.get("gl", GL)
        # Language code for the search interface (e.g., "en" for English)
        hl: str = args.get("hl", HL)
        # Number of top search results to retrieve
        k: int = args.get("k", K)
        # Type of search (e.g., "news", "places", "images", or "search" for general)
        search_type: str = args.get("type", TYPE)
        # Search filter string (e.g., "qdr:d" for past day results); optional and can be used for time filtering
        # Default is None.
        tbs: str = args.get("tbs")

        # Create search with the above parameters
        search = GoogleSerperAPIWrapper(gl=gl, hl=hl, k=k, type=search_type, tbs=tbs)

        # Perform search asynchronously
        results = await search.aresults(query)

        return results
