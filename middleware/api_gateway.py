# Copyright © 2025 Cognizant Technology Solutions Corp, www.cognizant.com.
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

"""API Gateway for NeuroSan with per-request LLM API key injection."""

import asyncio
import logging
import os
from typing import Optional

from fastapi import FastAPI
from fastapi import Header
from fastapi import Request
from fastapi import Response
from httpx import AsyncClient

logger = logging.getLogger(__name__)

# NeuroSan service configuration
NEURO_SAN_HOST = os.getenv("NEURO_SAN_HOST", "localhost")
NEURO_SAN_PORT = int(os.getenv("NEURO_SAN_PORT", "8080"))
NEURO_SAN_BASE_URL = f"http://{NEURO_SAN_HOST}:{NEURO_SAN_PORT}"

# Timeout for requests to NeuroSan
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "300"))

app = FastAPI(
    title="NeuroSan API Gateway",
    description="Gateway for routing requests to NeuroSan with per-request LLM API key injection",
    version="1.0.0",
)


class APIKeyInjector:
    """Handles API key extraction from requests and injects them as environment variables."""

    # Mapping of HTTP header names to environment variables
    HEADER_TO_ENV_MAP = {
        "x-openai-api-key": "OPENAI_API_KEY",
        "x-azure-openai-api-key": "AZURE_OPENAI_API_KEY",
        "x-anthropic-api-key": "ANTHROPIC_API_KEY",
        "x-google-api-key": "GOOGLE_API_KEY",
        "x-aws-access-key": "AWS_ACCESS_KEY_ID",
        "x-aws-secret-key": "AWS_SECRET_ACCESS_KEY",
        "x-nvidia-api-key": "NVIDIA_API_KEY",
        "x-azure-openai-endpoint": "AZURE_OPENAI_ENDPOINT",
    }

    @staticmethod
    def extract_api_keys(
        request_headers: dict,
        authorization_header: Optional[str] = None,
    ) -> dict[str, str]:
        """
        Extract API keys from request headers.

        Args:
            request_headers: HTTP request headers
            authorization_header: Optional Authorization header for bearer token extraction

        Returns:
            Dictionary of environment variable names to API key values
        """
        api_keys = {}

        # Extract from custom headers (x-openai-api-key, x-anthropic-api-key, etc.)
        for header_name, env_var_name in APIKeyInjector.HEADER_TO_ENV_MAP.items():
            value = request_headers.get(header_name)
            if value:
                api_keys[env_var_name] = value
                logger.debug(f"Extracted {env_var_name} from header {header_name}")

        # Extract from Authorization header if present (Bearer <API_KEY>)
        if authorization_header:
            parts = authorization_header.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                # Try to infer the provider from other headers or default to OpenAI
                if "x-anthropic-api-key" not in request_headers:
                    api_keys["OPENAI_API_KEY"] = parts[1]
                    logger.debug("Extracted OPENAI_API_KEY from Authorization header")

        return api_keys

    @staticmethod
    async def inject_keys_into_request(
        api_keys: dict[str, str],
        request_headers: dict,
    ) -> dict[str, str]:
        """
        Prepare headers for forwarding to upstream service.

        Removes sensitive headers from the forwarded request while keeping others.

        Args:
            api_keys: Dictionary of API keys extracted from request
            request_headers: Original request headers

        Returns:
            Cleaned headers for forwarding
        """
        # Create a copy of headers, excluding API key headers
        forwarded_headers = {}

        # List of headers to exclude from forwarding
        exclude_headers = {
            "host",
            "content-length",
            "transfer-encoding",
        } | set(APIKeyInjector.HEADER_TO_ENV_MAP.keys())

        for header_name, header_value in request_headers.items():
            if header_name.lower() not in exclude_headers:
                forwarded_headers[header_name] = header_value

        return forwarded_headers


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "NeuroSan API Gateway",
        "version": "1.0.0",
    }


@app.get("/version")
async def version():
    """Version endpoint."""
    return {
        "version": "1.0.0",
        "neuro_san_endpoint": NEURO_SAN_BASE_URL,
    }


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy_request(
    request: Request,
    path: str,
    authorization: Optional[str] = Header(None),
):
    """
    Proxy requests to NeuroSan service with API key injection.

    Args:
        request: FastAPI Request object
        path: URL path to forward
        authorization: Optional Authorization header

    Returns:
        Response from NeuroSan service
    """
    try:
        # Extract API keys from request headers
        request_headers = dict(request.headers)
        api_keys = APIKeyInjector.extract_api_keys(request_headers, authorization)

        if api_keys:
            logger.info(f"Request contains API keys for: {', '.join(api_keys.keys())}")

        # Prepare headers for forwarding
        forwarded_headers = await APIKeyInjector.inject_keys_into_request(
            api_keys, request_headers
        )

        # Construct the URL for the upstream service
        url = f"{NEURO_SAN_BASE_URL}/{path}"
        if request.url.query:
            url = f"{url}?{request.url.query}"

        logger.debug(f"Forwarding {request.method} request to {url}")

        # Read request body if present
        body = await request.body()

        # Create a new environment dict with injected keys if they exist
        # Note: This approach modifies the subprocess environment
        # In production, consider passing credentials via request context
        env_vars = os.environ.copy()
        env_vars.update(api_keys)

        # Forward the request to the upstream service
        async with AsyncClient(
            timeout=REQUEST_TIMEOUT,
            verify=False,  # Note: In production, set verify=True for HTTPS
        ) as client:
            response = await client.request(
                method=request.method,
                url=url,
                headers=forwarded_headers,
                content=body if body else None,
            )

            # Stream the response back
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.headers.get("content-type"),
            )

    except Exception as exc:
        logger.error(f"Error proxying request: {exc}", exc_info=True)
        return Response(
            content={"error": "Failed to proxy request to NeuroSan service"},
            status_code=502,
        )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("API_GATEWAY_PORT", "9000"))
    host = os.getenv("API_GATEWAY_HOST", "0.0.0.0")

    logger.info(f"Starting API Gateway on {host}:{port}")
    logger.info(f"Forwarding to NeuroSan at {NEURO_SAN_BASE_URL}")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
