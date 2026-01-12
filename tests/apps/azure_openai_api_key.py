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

from neuro_san.internals.run_context.langchain.util.api_key_error_check import ApiKeyErrorCheck
from openai import AzureOpenAI


def test_azure_open_ai_api_key():
    """
    Method for Testing Azure OpenAI API key
      Reads the Azure OpenAI API key from an environment variable,
      Creates a client, and submits a simple query ("What's the capital of France?").
      The response should includes the word "Paris".
    Any exceptions (Invalid API Key, Azure OpenAI access being blocked, etc.) are reported.
    See Azure OpenAI Quickstart for more information
    https://learn.microsoft.com/en-us/azure/ai-services/openai/chatgpt-quickstart?tabs=keyless%2Ctypescript-keyless%2Cpython-new%2Ccommand-line&pivots=programming-language-python
    """

    # Set your Azure details
    api_key = os.getenv("AZURE_OPENAI_API_KEY")  # or use a string directly
    api_version = os.getenv("OPENAI_API_VERSION")  # or use a string directly
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")  # e.g., "https://your-resource.openai.azure.com/"
    # Azure OpenAI requires you to first deploy a model and then reference it using the deployment name in API calls
    # deployment name is NOT the model name itself. It's a label you assign to the model when you deploy it. E.g., you
    # may deploy a "gpt-4" model and label it "my-gpt-4"
    deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")  # e.g., "gpt-4" or "gpt-3.5-turbo"

    # Create AzureOpenAI client
    client = AzureOpenAI(api_key=api_key, api_version=api_version, azure_endpoint=azure_endpoint)

    # Set up the client with your API key
    response = None
    try:

        # Make a chat completion request
        response = client.chat.completions.create(
            model=deployment_name,  # or "gpt-3.5-turbo"
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What's the capital of France?"},
            ],
        )

        # Print the assistant's reply
        print("Successful call to Azure OpenAI")
        print(f"reponse: {response.choices[0].message.content}")

    except Exception as e:  # pylint: disable=broad-except
        print("Failed call to Azure OpenAI")
        print(f"Exception: {e}")
        exception_msg = ApiKeyErrorCheck.check_for_api_key_exception(e)
        print(f"Exception message: {exception_msg}")


if __name__ == "__main__":
    test_azure_open_ai_api_key()
