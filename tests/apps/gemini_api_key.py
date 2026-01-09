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

from google import genai
from neuro_san.internals.run_context.langchain.util.api_key_error_check import ApiKeyErrorCheck


# Method for Testing Gemini API key
#  Reads the Gemini API key from an environment variable,
#  Creates a client, and submits a simple query ("What's the capital of France?").
#  The response should includes the word "Paris".
#  Any exceptions (Invalid API Key, OpenAI access being blocked, etc.) are reported.
def test_gemini_api_key():

    # Set your Gemini details
    api_key = os.getenv("GOOGLE_API_KEY")  # or use a string directly
    model_name = os.getenv("GOOGLE_MODEL_NAME")  # e.g., "gemini-pro"

    try:

        # Create a Gemini model client with Gemini API key and send a simple prompt
        client = genai.Client(api_key=api_key)  # Or just use: "your-key-here"
        response = client.models.generate_content(model=model_name, contents="What's the capital of France?")

        print("Successful call to Gemini")
        print(response.text)

    except Exception as e:
        print("Failed call to Gemini")
        exception_msg = ApiKeyErrorCheck.check_for_api_key_exception(e)
        print(f"Exception message: {exception_msg}")


if __name__ == "__main__":
    test_gemini_api_key()
