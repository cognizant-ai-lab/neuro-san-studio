# Copyright 2025 Cognizant Technology Solutions Corp, www.cognizant.com.
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

"""
Environment variable validation and startup diagnostics.

This module provides three-tier validation for LLM API keys and other
critical environment variables:

- Tier 1: Placeholder detection (always runs)
- Tier 2: Format validation (always runs)
- Tier 3: Live validation via API calls (optional, via --validate-keys flag)
"""

import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional


class ValidationStatus(Enum):
    """Status of environment variable validation."""

    VALID = "valid"
    NOT_SET = "not_set"
    PLACEHOLDER = "placeholder"
    INVALID_FORMAT = "invalid_format"
    INVALID_KEY = "invalid_key"
    RATE_LIMITED = "rate_limited"
    NO_CREDITS = "no_credits"
    NETWORK_ERROR = "network_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class ValidationResult:
    """Result of validating an environment variable."""

    var_name: str
    status: ValidationStatus
    message: str
    masked_value: Optional[str] = None


class EnvValidator:
    """Validates environment variables for LLM API keys and other critical settings."""

    # Placeholder patterns that indicate unconfigured values
    PLACEHOLDER_PATTERNS = [
        "YOUR_",
        "REPLACE",
        "INSERT",
        "TODO",
        "CHANGEME",
        "CHANGE_ME",
        "ENTER_",
        "PUT_",
        "ADD_",
        "<",
        ">",
        "xxx",
        "...",
    ]

    # Format validators for known API keys
    # Each validator returns (is_valid, error_message)
    KEY_FORMAT_VALIDATORS: dict[str, Callable[[str], tuple[bool, str]]] = {
        "OPENAI_API_KEY": lambda v: (
            (v.startswith("sk-") and len(v) >= 20),
            "OpenAI keys should start with 'sk-' and be at least 20 characters",
        ),
        "ANTHROPIC_API_KEY": lambda v: (
            (v.startswith("sk-ant-") and len(v) >= 20),
            "Anthropic keys should start with 'sk-ant-' and be at least 20 characters",
        ),
        "GOOGLE_API_KEY": lambda v: (
            (len(v) >= 20 and v.isalnum() or "-" in v or "_" in v),
            "Google API keys should be at least 20 characters",
        ),
        "AWS_ACCESS_KEY_ID": lambda v: (
            (v.startswith("AKIA") and len(v) == 20),
            "AWS Access Key IDs should start with 'AKIA' and be exactly 20 characters",
        ),
        "AWS_SECRET_ACCESS_KEY": lambda v: (
            (len(v) == 40),
            "AWS Secret Access Keys should be exactly 40 characters",
        ),
        "AZURE_OPENAI_API_KEY": lambda v: (
            (len(v) >= 20),
            "Azure OpenAI keys should be at least 20 characters",
        ),
        "BRAVE_API_KEY": lambda v: (
            (len(v) >= 20),
            "Brave API keys should be at least 20 characters",
        ),
    }

    # Keys that should be validated (grouped by provider)
    LLM_API_KEYS = [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
    ]

    def __init__(self):
        """Initialize the environment validator."""
        self.results: list[ValidationResult] = []

    @staticmethod
    def mask_value(value: str) -> str:
        """Mask a sensitive value, showing only first 4 and last 4 characters."""
        if not value:
            return "***"
        if len(value) <= 12:
            return "***"
        return f"{value[:4]}...{value[-4:]}"

    def is_placeholder(self, value: str) -> bool:
        """Check if a value appears to be a placeholder."""
        if not value:
            return True
        value_upper = value.upper()
        return any(pattern in value_upper for pattern in self.PLACEHOLDER_PATTERNS)

    def validate_tier1(self, var_name: str) -> ValidationResult:
        """
        Tier 1: Check if variable is set and not a placeholder.

        Args:
            var_name: Name of the environment variable to check

        Returns:
            ValidationResult with status and message
        """
        value = os.getenv(var_name)

        if not value:
            return ValidationResult(
                var_name=var_name,
                status=ValidationStatus.NOT_SET,
                message="Configure in .env file",
                masked_value=None,
            )

        if self.is_placeholder(value):
            return ValidationResult(
                var_name=var_name,
                status=ValidationStatus.PLACEHOLDER,
                message="Appears to be a placeholder value",
                masked_value=self.mask_value(value),
            )

        return ValidationResult(
            var_name=var_name,
            status=ValidationStatus.VALID,
            message="Set",
            masked_value=self.mask_value(value),
        )

    def validate_tier2(self, var_name: str) -> ValidationResult:
        """
        Tier 2: Validate the format of the value.

        Args:
            var_name: Name of the environment variable to check

        Returns:
            ValidationResult with status and message
        """
        # First run tier 1
        tier1_result = self.validate_tier1(var_name)
        if tier1_result.status != ValidationStatus.VALID:
            return tier1_result

        value = os.getenv(var_name, "")

        # Check if we have a format validator for this key
        if var_name in self.KEY_FORMAT_VALIDATORS:
            is_valid, error_msg = self.KEY_FORMAT_VALIDATORS[var_name](value)
            if not is_valid:
                return ValidationResult(
                    var_name=var_name,
                    status=ValidationStatus.INVALID_FORMAT,
                    message=error_msg,
                    masked_value=self.mask_value(value),
                )

        return ValidationResult(
            var_name=var_name,
            status=ValidationStatus.VALID,
            message="Format valid",
            masked_value=self.mask_value(value),
        )

    def validate_tier3_openai(self, var_name: str) -> ValidationResult:
        """Validate OpenAI API key with a live API call."""
        tier2_result = self.validate_tier2(var_name)
        if tier2_result.status != ValidationStatus.VALID:
            return tier2_result

        value = os.getenv(var_name, "")

        try:
            from openai import AuthenticationError, OpenAI, RateLimitError

            client = OpenAI(api_key=value)
            # Lightweight call - list models doesn't consume tokens
            client.models.list()
            return ValidationResult(
                var_name=var_name,
                status=ValidationStatus.VALID,
                message="API key verified",
                masked_value=self.mask_value(value),
            )
        except AuthenticationError:
            return ValidationResult(
                var_name=var_name,
                status=ValidationStatus.INVALID_KEY,
                message="Authentication failed - invalid API key",
                masked_value=self.mask_value(value),
            )
        except RateLimitError:
            return ValidationResult(
                var_name=var_name,
                status=ValidationStatus.RATE_LIMITED,
                message="Rate limited - key may be valid but quota exceeded",
                masked_value=self.mask_value(value),
            )
        except ImportError:
            return ValidationResult(
                var_name=var_name,
                status=ValidationStatus.UNKNOWN_ERROR,
                message="openai package not installed - skipping live validation",
                masked_value=self.mask_value(value),
            )
        except Exception as e:
            return ValidationResult(
                var_name=var_name,
                status=ValidationStatus.NETWORK_ERROR,
                message=f"Connection error: {type(e).__name__}",
                masked_value=self.mask_value(value),
            )

    def validate_tier3_anthropic(self, var_name: str) -> ValidationResult:
        """Validate Anthropic API key with a live API call."""
        tier2_result = self.validate_tier2(var_name)
        if tier2_result.status != ValidationStatus.VALID:
            return tier2_result

        value = os.getenv(var_name, "")

        try:
            from anthropic import (
                Anthropic,
                AuthenticationError,
                BadRequestError,
                RateLimitError,
            )

            client = Anthropic(api_key=value)
            # Lightweight call - count tokens using the messages API
            client.messages.count_tokens(
                model="claude-3-haiku-20240307",
                messages=[{"role": "user", "content": "test"}],
            )
            return ValidationResult(
                var_name=var_name,
                status=ValidationStatus.VALID,
                message="API key verified",
                masked_value=self.mask_value(value),
            )
        except BadRequestError:
            # 400 means the key authenticated but request was malformed
            # This still confirms the key is valid
            return ValidationResult(
                var_name=var_name,
                status=ValidationStatus.VALID,
                message="API key verified",
                masked_value=self.mask_value(value),
            )
        except AuthenticationError:
            return ValidationResult(
                var_name=var_name,
                status=ValidationStatus.INVALID_KEY,
                message="Authentication failed - invalid API key",
                masked_value=self.mask_value(value),
            )
        except RateLimitError:
            return ValidationResult(
                var_name=var_name,
                status=ValidationStatus.RATE_LIMITED,
                message="Rate limited - key may be valid but quota exceeded",
                masked_value=self.mask_value(value),
            )
        except ImportError:
            return ValidationResult(
                var_name=var_name,
                status=ValidationStatus.UNKNOWN_ERROR,
                message="anthropic package not installed - skipping live validation",
                masked_value=self.mask_value(value),
            )
        except Exception as e:
            return ValidationResult(
                var_name=var_name,
                status=ValidationStatus.NETWORK_ERROR,
                message=f"Connection error: {type(e).__name__}",
                masked_value=self.mask_value(value),
            )

    def validate_tier3_google(self, var_name: str) -> ValidationResult:
        """Validate Google API key with a live API call."""
        tier2_result = self.validate_tier2(var_name)
        if tier2_result.status != ValidationStatus.VALID:
            return tier2_result

        value = os.getenv(var_name, "")

        try:
            from google import genai

            client = genai.Client(api_key=value)
            # Lightweight call - list models
            list(client.models.list())
            return ValidationResult(
                var_name=var_name,
                status=ValidationStatus.VALID,
                message="API key verified",
                masked_value=self.mask_value(value),
            )
        except ImportError:
            return ValidationResult(
                var_name=var_name,
                status=ValidationStatus.UNKNOWN_ERROR,
                message="google-genai package not installed - skipping live validation",
                masked_value=self.mask_value(value),
            )
        except Exception as e:
            error_msg = str(e).lower()
            if "api key" in error_msg or "invalid" in error_msg or "401" in error_msg:
                return ValidationResult(
                    var_name=var_name,
                    status=ValidationStatus.INVALID_KEY,
                    message="Authentication failed - invalid API key",
                    masked_value=self.mask_value(value),
                )
            return ValidationResult(
                var_name=var_name,
                status=ValidationStatus.NETWORK_ERROR,
                message=f"Connection error: {type(e).__name__}",
                masked_value=self.mask_value(value),
            )

    def validate_tier3(self, var_name: str) -> ValidationResult:
        """
        Tier 3: Validate with a live API call.

        Args:
            var_name: Name of the environment variable to check

        Returns:
            ValidationResult with status and message
        """
        # Route to appropriate validator based on key type
        if var_name == "OPENAI_API_KEY":
            return self.validate_tier3_openai(var_name)
        elif var_name == "ANTHROPIC_API_KEY":
            return self.validate_tier3_anthropic(var_name)
        elif var_name == "GOOGLE_API_KEY":
            return self.validate_tier3_google(var_name)
        else:
            # For keys without live validation, return tier 2 result
            return self.validate_tier2(var_name)

    def validate_all(self, live_validation: bool = False) -> list[ValidationResult]:
        """
        Validate all known LLM API keys.

        Args:
            live_validation: If True, perform Tier 3 live validation

        Returns:
            List of ValidationResult objects
        """
        self.results = []

        for var_name in self.LLM_API_KEYS:
            if live_validation:
                result = self.validate_tier3(var_name)
            else:
                result = self.validate_tier2(var_name)
            self.results.append(result)

        return self.results

    def print_results(self, results: Optional[list[ValidationResult]] = None) -> None:
        """Print validation results in a formatted table."""
        if results is None:
            results = self.results

        if not results:
            print("No validation results to display.")
            return

        print("\n" + "=" * 70)
        print("Environment Variable Validation Results")
        print("=" * 70)

        # Group by status for cleaner output
        valid_results = [r for r in results if r.status == ValidationStatus.VALID]
        warning_results = [
            r
            for r in results
            if r.status in (ValidationStatus.NOT_SET, ValidationStatus.PLACEHOLDER)
        ]
        error_results = [
            r
            for r in results
            if r.status
            not in (
                ValidationStatus.VALID,
                ValidationStatus.NOT_SET,
                ValidationStatus.PLACEHOLDER,
            )
        ]

        if valid_results:
            print("\n[VALID]")
            for r in valid_results:
                print(f"  {r.var_name}: {r.masked_value} - {r.message}")

        if warning_results:
            print("\n[WARNING]")
            for r in warning_results:
                status_icon = "!" if r.status == ValidationStatus.PLACEHOLDER else "-"
                masked = r.masked_value or "not set"
                print(f"  {status_icon} {r.var_name}: {masked} - {r.message}")

        if error_results:
            print("\n[ERROR]")
            for r in error_results:
                print(f"  X {r.var_name}: {r.masked_value} - {r.message}")

        print("\n" + "=" * 70)

        # Summary
        total = len(results)
        valid_count = len(valid_results)
        warning_count = len(warning_results)
        error_count = len(error_results)

        print(f"Summary: {valid_count}/{total} valid, {warning_count} warnings, {error_count} errors")
        print("=" * 70 + "\n")

    def has_errors(self, results: Optional[list[ValidationResult]] = None) -> bool:
        """Check if any results have error status."""
        if results is None:
            results = self.results
        error_statuses = {
            ValidationStatus.INVALID_FORMAT,
            ValidationStatus.INVALID_KEY,
            ValidationStatus.RATE_LIMITED,
            ValidationStatus.NO_CREDITS,
        }
        return any(r.status in error_statuses for r in results)

    def has_warnings(self, results: Optional[list[ValidationResult]] = None) -> bool:
        """Check if any results have warning status."""
        if results is None:
            results = self.results
        warning_statuses = {ValidationStatus.NOT_SET, ValidationStatus.PLACEHOLDER}
        return any(r.status in warning_statuses for r in results)
