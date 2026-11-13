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

"""Shared credential redaction for Agent Network Consultant diagnostics."""

import os
import re
from typing import ClassVar


class SensitiveDataRedactor:
    """Apply one credential-detection policy to Agent Network Consultant diagnostic text."""

    REDACTION = "[REDACTED]"
    SENSITIVE_KEY_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"(?:(?:^|[_-])token$|(?:^|[_-])(?:api[_-]?key|authorization|credentials?|password|secret|"
        r"access[_-]?key|access[_-]?token|auth[_-]?token|bearer[_-]?token|private[_-]?key|pwd)(?:$|[_-]))",
        re.IGNORECASE,
    )
    ASSIGNMENT_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"(?<![A-Za-z0-9_-])(?P<key_quote>[\"']?)(?P<key>[A-Za-z_][A-Za-z0-9_-]*)"
        r"(?P=key_quote)(?P<separator>\s*[:=]\s*)(?P<value>\"(?:\\.|[^\"\\])*\"|"
        r"'(?:\\.|[^'\\])*'|[^,;\n}\]]+)",
        re.IGNORECASE,
    )
    PROVIDER_TOKEN_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"\b(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{8,}|AIza[0-9A-Za-z_-]{20,}|"
        r"AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]+|github_pat_[A-Za-z0-9_]+|"
        r"xox[baprs]-[A-Za-z0-9-]+|glpat-[A-Za-z0-9_-]+|sk_(?:live|test)_[A-Za-z0-9]+)\b"
    )
    BEARER_TOKEN_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE)
    PRIVATE_KEY_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----.*?-----END (?:[A-Z0-9]+ )*PRIVATE KEY-----",
        re.DOTALL,
    )

    @classmethod
    def is_sensitive_key(cls, key_name: str) -> bool:
        """
        Return whether a configuration key conventionally contains a credential.

        The strict policy preserves ordinary counters such as ``max_tokens`` and ``completion_token_count``.

        :param key_name: The configuration or environment key to inspect.
        :return: Whether values under the key must be redacted.
        """
        return cls.SENSITIVE_KEY_PATTERN.search(key_name) is not None

    @classmethod
    def redact_text(cls, text: str) -> str:
        """
        Redact configured secrets, credential assignments, and recognizable provider tokens.

        :param text: The diagnostic text to sanitize.
        :return: The text with credential values replaced by the shared redaction marker.
        """
        redacted = cls.PRIVATE_KEY_PATTERN.sub(cls.REDACTION, text)
        # Read current values so credentials loaded after module import are protected without retaining them globally.
        for name, value in os.environ.items():
            if len(value) >= 8 and cls.is_sensitive_key(name):
                redacted = redacted.replace(value, cls.REDACTION)
        redacted = cls.ASSIGNMENT_PATTERN.sub(cls._redact_assignment, redacted)
        redacted = cls.PROVIDER_TOKEN_PATTERN.sub(cls.REDACTION, redacted)
        return cls.BEARER_TOKEN_PATTERN.sub(f"Bearer {cls.REDACTION}", redacted)

    @classmethod
    def _redact_assignment(cls, match: re.Match[str]) -> str:
        """
        Redact one assignment when its key uses the shared credential-key convention.

        :param match: The assignment-pattern match to inspect.
        :return: The original assignment or its redacted equivalent.
        """
        key_name = match.group("key")
        if not cls.is_sensitive_key(key_name):
            value = match.group("value")
            # A harmless outer label can contain a nested credential assignment, so inspect its value recursively.
            redacted_value = cls.ASSIGNMENT_PATTERN.sub(cls._redact_assignment, value)
            if redacted_value == value:
                return match.group(0)
            key_quote = match.group("key_quote")
            return f"{key_quote}{key_name}{key_quote}{match.group('separator')}{redacted_value}"
        key_quote = match.group("key_quote")
        return f"{key_quote}{key_name}{key_quote}{match.group('separator')}{cls.REDACTION}"
