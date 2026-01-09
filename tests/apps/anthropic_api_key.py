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

import anthropic
from neuro_san.internals.run_context.langchain.util.api_key_error_check import ApiKeyErrorCheck


# Method for Testing Anthropic API key
#  Reads the Anthropic API keys from an environment variables,
#  Creates a client, and submits a simple query ("What's the capital of France?").
#  The response should includes the word "Paris".
#  Any exceptions (Invalid API Key, Azure OpenAI access being blocked, etc.) are reported.
def test_anthropic_api_key():

    # Set your Anthropic details
    api_key = os.getenv("ANTHROPIC_API_KEY")  # or use a string directly

    # Set model to the model you want to use, e.g., "claude-opus-4-20250514"
    model = "claude-opus-4-20250514"

    # Create Anthropic client
    client = anthropic.Anthropic(api_key=api_key)

    # Set up the client with your API key
    try:
        message = client.messages.create(
            model=model,
            max_tokens=1024,
            system="You are a helpful assistant.",
            messages=[{"role": "user", "content": [{"type": "text", "text": "What's the capital of France?"}]}],
        )

        # Print the assistant's reply
        print("Successful call to Anthropic")
        print(f"reponse: {message.content[0].text}")

    except Exception as e:
        print("Failed call to Anthropic")
        print(f"Exception: {e}")
        exception_msg = ApiKeyErrorCheck.check_for_api_key_exception(e)
        print(f"Exception message: {exception_msg}")


if __name__ == "__main__":
    test_anthropic_api_key()
