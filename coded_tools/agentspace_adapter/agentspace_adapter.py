import logging
import os
from typing import Any
from typing import Dict
from typing import Union

# Check if the google-cloud-discoveryengine package is installed
try:
    from google.cloud import discoveryengine_v1 as discoveryengine
except ImportError as e:
    raise ImportError(
        "The google-cloud-discoveryengine package is not installed. "
        "Please install it using 'pip install google-cloud-discoveryengine'."
    ) from e
# Check if the google.api_core package is installed
try:
    from google.api_core.client_options import ClientOptions
except ImportError as e:
    raise ImportError(
        "The google.api_core package is not installed. Please install it using 'pip install google-api-core'."
    ) from e

from neuro_san.interfaces.coded_tool import CodedTool


class AgentSpaceSearch(CodedTool):
    """
    CodedTool implementation which provides a way to utilize different websites' search feature
    """

    def __init__(self):
        """
        Initialize the AgentSpaceSearch class.
        """
        # Use your own GCP_PROJECT_ID
        self.project_id = os.getenv("GCP_PROJECT_ID", "gbg-project-gravity")
        # Values: "global", "us", "eu"
        self.location = os.getenv("GCP_LOCATION", "global")
        # Use your own agent/engine_id created using your service account
        self.engine_id = os.getenv("ENGINE_ID", "enterprise-search-17401609_1740160937596")

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
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

                Keys expected for this implementation are:
                    None

        :return:
            In case of successful execution:
                The URL to the app as a string.
            otherwise:
                a text string an error message in the format:
                "Error: <error message>"
        """
        search_query: str = args.get("search_query", "")
        if search_query == "":
            return "Error: No search query provided."

        logger = logging.getLogger(self.__class__.__name__)
        logger.info(">>>>>>>>>>>>>>>>>>>WebsiteSearch>>>>>>>>>>>>>>>>>>")
        logger.info("Search Query: %s", str(search_query))
        res = self.search_sample(search_query)
        logger.info(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")
        return res

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """Asynchronous version of the invoke method."""
        # For this example, we will just call the synchronous method
        return self.invoke(args, sly_data)

    # Helper function to perform the search
    def search_sample(self, search_query: str) -> discoveryengine.services.search_service.pagers.SearchPager:
        """
        Perform a search using the Discovery Engine API.
        """
        #  For more information, refer to:
        # https://cloud.google.com/generative-ai-app-builder/docs/locations#specify_a_multi-region_for_your_data_store
        client_options = (
            ClientOptions(api_endpoint=f"{self.location}-discoveryengine.googleapis.com")
            if self.location != "global"
            else None
        )

        # Create a client
        client = discoveryengine.SearchServiceClient(client_options=client_options)

        # The full resource name of the search app serving config
        proj_loc = f"projects/{self.project_id}/locations/{self.location}/"
        proj_loc_engine_id = f"{proj_loc}collections/default_collection/engines/{self.engine_id}/"
        serving_config = f"{proj_loc_engine_id}/servingConfigs/default_config"

        # Optional - only supported for unstructured data: Configuration options for search.
        # Refer to the `ContentSearchSpec` reference for all supported fields:
        # https://cloud.google.com/python/docs/reference/discoveryengine/latest/google.cloud.discoveryengine_v1.types.SearchRequest.ContentSearchSpec
        content_search_spec = discoveryengine.SearchRequest.ContentSearchSpec(
            # For information about snippets, refer to:
            # https://cloud.google.com/generative-ai-app-builder/docs/snippets
            snippet_spec=discoveryengine.SearchRequest.ContentSearchSpec.SnippetSpec(return_snippet=True),
            # For information about search summaries, refer to:
            # https://cloud.google.com/generative-ai-app-builder/docs/get-search-summaries
            summary_spec=discoveryengine.SearchRequest.ContentSearchSpec.SummarySpec(
                summary_result_count=5,
                include_citations=True,
                ignore_adversarial_query=True,
                ignore_non_summary_seeking_query=True,
                model_prompt_spec=discoveryengine.SearchRequest.ContentSearchSpec.SummarySpec.ModelPromptSpec(
                    preamble="YOUR_CUSTOM_PROMPT"
                ),
                model_spec=discoveryengine.SearchRequest.ContentSearchSpec.SummarySpec.ModelSpec(
                    version="stable",
                ),
            ),
        )

        # Refer to the `SearchRequest` reference for all supported fields:
        # https://cloud.google.com/python/docs/reference/discoveryengine/latest/google.cloud.discoveryengine_v1.types.SearchRequest
        request = discoveryengine.SearchRequest(
            serving_config=serving_config,
            query=search_query,
            page_size=10,
            content_search_spec=content_search_spec,
            query_expansion_spec=discoveryengine.SearchRequest.QueryExpansionSpec(
                condition=discoveryengine.SearchRequest.QueryExpansionSpec.Condition.AUTO,
            ),
            spell_correction_spec=discoveryengine.SearchRequest.SpellCorrectionSpec(
                mode=discoveryengine.SearchRequest.SpellCorrectionSpec.Mode.AUTO
            ),
            # Optional: Use fine-tuned model for this request
            # custom_fine_tuning_spec=discoveryengine.CustomFineTuningSpec(
            #     enable_search_adaptor=True
            # ),
        )

        page_result = client.search(request)

        # Handle the response
        for response in page_result:
            print(response)

        return page_result
