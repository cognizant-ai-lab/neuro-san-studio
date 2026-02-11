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
from openai import OpenAI


# Method for Testing OpenAI API key
#  Reads the OpenAI API key from an environment variable,
#  Creates a client, and submits a simple query ("What's the capital of France?").
#  The response should includes the word "Paris".
#  Any exceptions (Invalid API Key, OpenAI access being blocked, etc.) are reported.
def test_open_ai_api_key():

    # Set up the client with your API key
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = None
    try:

        # Make a chat completion request
        response = client.chat.completions.create(
            model="gpt-4",  # or "gpt-3.5-turbo"
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What's the capital of France?"},
            ],
        )

        # Print the assistant's reply
        print("Successful call to OpenAI")
        print(f"reponse: {response.choices[0].message.content}")

    except Exception as e:
        print("Failed call to OpenAI")
        exception_msg = ApiKeyErrorCheck.check_for_api_key_exception(e)
        print(f"Exception message: {exception_msg}")


if __name__ == "__main__":
    test_open_ai_api_key()
