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

"""Tests for the shared Agent Network Consultant credential redactor."""

import os
from unittest import TestCase
from unittest.mock import patch

from neuro_san_studio.agent_network_consultant.sensitive_data_redactor import SensitiveDataRedactor


class TestSensitiveDataRedactor(TestCase):
    """Verify diagnostic redaction protects credentials without hiding ordinary configuration."""

    def test_sensitive_keys_exclude_token_counters(self) -> None:
        """Recognize credential keys without treating token-count settings as secrets."""
        self.assertTrue(SensitiveDataRedactor.is_sensitive_key("OPENAI_API_KEY"))
        self.assertTrue(SensitiveDataRedactor.is_sensitive_key("access_token"))
        self.assertTrue(SensitiveDataRedactor.is_sensitive_key("AWS_ACCESS_KEY_ID"))
        self.assertTrue(SensitiveDataRedactor.is_sensitive_key("HF_TOKEN"))
        self.assertTrue(SensitiveDataRedactor.is_sensitive_key("GITHUB_TOKEN"))
        self.assertTrue(SensitiveDataRedactor.is_sensitive_key("token"))
        self.assertTrue(SensitiveDataRedactor.is_sensitive_key("PRIVATE_KEY"))
        self.assertTrue(SensitiveDataRedactor.is_sensitive_key("SERVICENOW_PERSONAL_PWD"))
        self.assertFalse(SensitiveDataRedactor.is_sensitive_key("max_tokens"))
        self.assertFalse(SensitiveDataRedactor.is_sensitive_key("completion_token_count"))

    def test_redact_text_uses_environment_assignments_and_provider_patterns(self) -> None:
        """Apply every shared credential rule without exposing the original values."""
        environment_secret = "environment-secret-value"
        provider_secret = "sk-proj-example-secret-value"
        text = (
            f"configured={environment_secret}; OPENAI_API_KEY={provider_secret}; "
            f"Authorization: Bearer {provider_secret}"
        )
        with patch.dict(os.environ, {"PRIVATE_AUTH_TOKEN": environment_secret}, clear=True):
            redacted = SensitiveDataRedactor.redact_text(text)

        self.assertNotIn(environment_secret, redacted)
        self.assertNotIn(provider_secret, redacted)
        self.assertIn(SensitiveDataRedactor.REDACTION, redacted)

    def test_redact_text_matches_designer_credential_formats(self) -> None:
        """Redact the AWS, GitLab, and Stripe formats covered by the Designer's PII policy."""
        credential_values = (
            "AKIAIOSFODNN7EXAMPLE",
            "glpat-example_private_token",
            "sk_live_ExamplePrivateKey123",
        )

        redacted = SensitiveDataRedactor.redact_text("; ".join(credential_values))

        for credential_value in credential_values:
            with self.subTest(credential_value=credential_value):
                self.assertNotIn(credential_value, redacted)

    def test_assignment_redaction_preserves_non_secret_token_settings(self) -> None:
        """Redact token credentials while retaining token-count diagnostics."""
        text = "HF_TOKEN=hf-secret-value; access_token: access-secret; max_tokens=8192; completion_token_count=42"

        redacted = SensitiveDataRedactor.redact_text(text)

        self.assertNotIn("hf-secret-value", redacted)
        self.assertNotIn("access-secret", redacted)
        self.assertIn("HF_TOKEN=[REDACTED]", redacted)
        self.assertIn("access_token: [REDACTED]", redacted)
        self.assertIn("max_tokens=8192", redacted)
        self.assertIn("completion_token_count=42", redacted)

    def test_assignment_redaction_finds_a_secret_after_a_nonsecret_label(self) -> None:
        """Redact a credential assignment nested in a labeled diagnostic entry."""
        secret = "customer-secret-123"

        redacted = SensitiveDataRedactor.redact_text(f"employee_policy: api_key={secret}")

        self.assertEqual("employee_policy: api_key=[REDACTED]", redacted)
        self.assertNotIn(secret, redacted)

    def test_redact_text_handles_quoted_mappings_authorization_and_private_keys(self) -> None:
        """Redact realistic exception representations without leaving credential suffixes or key material."""
        api_secret = "ordinary secret value"
        basic_secret = "dXNlcjpwYXNz"
        github_secret = "github_pat_example_private_value"
        environment_secret = "service-now-private-password"
        private_key = "-----BEGIN PRIVATE KEY-----\nprivate-key-body\n-----END PRIVATE KEY-----"
        text = (
            f"{{\"api_key\": \"{api_secret}\", 'Authorization': 'Basic {basic_secret}'}}; "
            f'token="secret with spaces"; github={github_secret}; key={private_key}; value={environment_secret}'
        )
        with patch.dict(os.environ, {"SERVICENOW_PWD": environment_secret}, clear=True):
            redacted = SensitiveDataRedactor.redact_text(text)

        leaked_values: tuple[str, str, str, str, str, str] = (
            api_secret,
            basic_secret,
            github_secret,
            environment_secret,
            private_key,
            "secret with spaces",
        )
        for leaked_value in leaked_values:
            with self.subTest(leaked_value=leaked_value):
                self.assertNotIn(leaked_value, redacted)
        self.assertGreaterEqual(redacted.count(SensitiveDataRedactor.REDACTION), 5)
