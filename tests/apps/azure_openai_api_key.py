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

import os

from openai import OpenAI
from openai.types.responses import Response


def test_azure_open_ai_api_key():
    """
    Method to test the Azure OpenAI API key.
    Reads the Azure OpenAI API key, endpoint and deployment name from environment variables,
    creates a client for Azure's v1 API, and submits a simple query ("What's the capital of France?")
    through the Responses API, which neuro-san uses for Azure OpenAI by default.
    The response should include the word "Paris".
    Any exceptions (Invalid API Key, Azure OpenAI access being blocked, etc.) are reported.
    See Azure OpenAI Quickstart for more information
    https://learn.microsoft.com/en-us/azure/ai-services/openai/chatgpt-quickstart?tabs=keyless%2Ctypescript-keyless%2Cpython-new%2Ccommand-line&pivots=programming-language-python
    :return: Nothing
    """

    # Set your Azure details
    api_key = os.getenv("AZURE_OPENAI_API_KEY")  # or use a string directly
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")  # e.g., "https://your-resource.openai.azure.com/"
    # Azure OpenAI requires you to first deploy a model and then reference it using the deployment name in API calls
    # deployment name is NOT the model name itself. It's a label you assign to the model when you deploy it. E.g., you
    # may deploy a "gpt-4o" model and label it "my-gpt-4o"
    deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")  # e.g., "my-gpt-4o"

    # Name a missing setting here: the OpenAI client reports a missing endpoint only as "Connection error."
    missing: list[str] = []
    for name, value in (
        ("AZURE_OPENAI_API_KEY", api_key),
        ("AZURE_OPENAI_ENDPOINT", azure_endpoint.strip()),
        ("AZURE_OPENAI_DEPLOYMENT_NAME", deployment_name),
    ):
        if not value:
            missing.append(name)
    if missing:
        print(f"Failed call to Azure OpenAI. Set these environment variables: {', '.join(missing)}")
        return

    # Set up the client with your API key
    try:
        # Azure's v1 API serves the OpenAI API under <endpoint>/openai/v1/ and takes no api-version.
        # Accept an endpoint that already ends in the v1 path, as neuro-san does.
        base_url: str = azure_endpoint.strip().rstrip("/")
        if not base_url.endswith("/openai/v1"):
            base_url += "/openai/v1"
        client = OpenAI(api_key=api_key, base_url=f"{base_url}/")

        # Make a Responses API request
        response: Response = client.responses.create(
            model=deployment_name,
            instructions="You are a helpful assistant.",
            input="What's the capital of France?",
        )

        # Print the assistant's reply
        print("Successful call to Azure OpenAI")
        print(f"response: {response.output_text}")

    except Exception as e:  # pylint: disable=broad-except
        print("Failed call to Azure OpenAI. Exception:")
        print(e)


if __name__ == "__main__":
    test_azure_open_ai_api_key()
