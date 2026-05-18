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

"""Tests for the `neuro-san-studio check-llm-keys` command and EnvValidator."""

from unittest.mock import MagicMock
from unittest.mock import patch

from pytest import MonkeyPatch

from neuro_san_studio.commands import check_llm_keys as check_llm_keys_module
from neuro_san_studio.commands.check_llm_keys import CheckLlmKeysCommand
from neuro_san_studio.commands.check_llm_keys import EnvValidator
from neuro_san_studio.commands.check_llm_keys import ValidationResult
from neuro_san_studio.commands.check_llm_keys import ValidationStatus


def _wipe_env(monkeypatch: MonkeyPatch) -> None:
    """Unset every env var that EnvValidator inspects."""
    for var in EnvValidator.LLM_API_KEYS:
        monkeypatch.delenv(var, raising=False)


class TestMaskValue:
    """Tests for EnvValidator.mask_value."""

    def test_empty_returns_stars(self) -> None:
        """Empty input is masked as ***."""
        assert EnvValidator.mask_value("") == "***"

    def test_short_returns_stars(self) -> None:
        """A short value (<=12 chars) is masked entirely as ***."""
        assert EnvValidator.mask_value("short") == "***"

    def test_exactly_12_chars_returns_stars(self) -> None:
        """The 12-char boundary is still fully masked."""
        assert EnvValidator.mask_value("a" * 12) == "***"

    def test_long_returns_first4_last4(self) -> None:
        """Long values reveal only the first 4 and last 4 characters."""
        masked = EnvValidator.mask_value("sk-abcdefghijklmnop")
        assert masked == "sk-a...mnop"


class TestIsPlaceholder:
    """Tests for EnvValidator.is_placeholder."""

    def test_empty_is_placeholder(self) -> None:
        """An empty string is treated as a placeholder."""
        assert EnvValidator().is_placeholder("") is True

    def test_your_prefix(self) -> None:
        """`YOUR_…` is a placeholder pattern."""
        assert EnvValidator().is_placeholder("YOUR_API_KEY_HERE") is True

    def test_angle_brackets(self) -> None:
        """`<…>`-wrapped values are placeholders."""
        assert EnvValidator().is_placeholder("<your-key>") is True

    def test_todo_marker(self) -> None:
        """`TODO_…` is a placeholder pattern."""
        assert EnvValidator().is_placeholder("TODO_REPLACE_ME") is True

    def test_changeme(self) -> None:
        """`CHANGEME` is a placeholder pattern."""
        assert EnvValidator().is_placeholder("CHANGEME") is True

    def test_real_key_is_not_placeholder(self) -> None:
        """A realistic-looking key is not flagged as a placeholder."""
        assert EnvValidator().is_placeholder("sk-abc1234567890abcdef") is False


class TestValidateTier1:
    """Tests for EnvValidator.validate_tier1."""

    def test_not_set(self, monkeypatch: MonkeyPatch) -> None:
        """Unset env var → NOT_SET."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        result = EnvValidator().validate_tier1("OPENAI_API_KEY")
        assert result.status == ValidationStatus.NOT_SET

    def test_placeholder(self, monkeypatch: MonkeyPatch) -> None:
        """Placeholder env var → PLACEHOLDER."""
        monkeypatch.setenv("OPENAI_API_KEY", "YOUR_OPENAI_KEY")
        result = EnvValidator().validate_tier1("OPENAI_API_KEY")
        assert result.status == ValidationStatus.PLACEHOLDER

    def test_valid(self, monkeypatch: MonkeyPatch) -> None:
        """Real-looking env var → VALID."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-abc1234567890abcdef")
        result = EnvValidator().validate_tier1("OPENAI_API_KEY")
        assert result.status == ValidationStatus.VALID


class TestValidateTier2:
    """Tests for EnvValidator.validate_tier2."""

    def test_openai_missing_prefix(self, monkeypatch: MonkeyPatch) -> None:
        """OpenAI key without `sk-` prefix → INVALID_FORMAT."""
        monkeypatch.setenv("OPENAI_API_KEY", "garbage_that_is_long_enough_to_pass_len_check")
        result = EnvValidator().validate_tier2("OPENAI_API_KEY")
        assert result.status == ValidationStatus.INVALID_FORMAT

    def test_openai_valid_format(self, monkeypatch: MonkeyPatch) -> None:
        """OpenAI key with `sk-` prefix and adequate length → VALID."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-abc1234567890abcdef")
        result = EnvValidator().validate_tier2("OPENAI_API_KEY")
        assert result.status == ValidationStatus.VALID

    def test_anthropic_missing_prefix(self, monkeypatch: MonkeyPatch) -> None:
        """Anthropic key missing `sk-ant-` prefix → INVALID_FORMAT."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-not-anthropic-but-long-enough")
        result = EnvValidator().validate_tier2("ANTHROPIC_API_KEY")
        assert result.status == ValidationStatus.INVALID_FORMAT

    def test_anthropic_valid_format(self, monkeypatch: MonkeyPatch) -> None:
        """Anthropic key with `sk-ant-` prefix and adequate length → VALID."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-abc1234567890abc")
        result = EnvValidator().validate_tier2("ANTHROPIC_API_KEY")
        assert result.status == ValidationStatus.VALID

    def test_aws_access_key_wrong_length(self, monkeypatch: MonkeyPatch) -> None:
        """AWS Access Key ID with non-20 length → INVALID_FORMAT."""
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA_too_short")
        result = EnvValidator().validate_tier2("AWS_ACCESS_KEY_ID")
        assert result.status == ValidationStatus.INVALID_FORMAT

    def test_aws_access_key_valid(self, monkeypatch: MonkeyPatch) -> None:
        """AWS Access Key ID with `AKIA` prefix and exact 20 length → VALID."""
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA" + "A" * 16)
        result = EnvValidator().validate_tier2("AWS_ACCESS_KEY_ID")
        assert result.status == ValidationStatus.VALID


class TestHasErrorsAndWarnings:
    """Tests for has_errors and has_warnings flag-routing."""

    def _result(self, status: ValidationStatus) -> ValidationResult:
        return ValidationResult(var_name="X", status=status, message="msg")

    def test_has_errors_for_invalid_format(self) -> None:
        """INVALID_FORMAT is an error."""
        results = [self._result(ValidationStatus.INVALID_FORMAT)]
        assert EnvValidator().has_errors(results) is True

    def test_has_errors_for_invalid_key(self) -> None:
        """INVALID_KEY is an error."""
        results = [self._result(ValidationStatus.INVALID_KEY)]
        assert EnvValidator().has_errors(results) is True

    def test_has_errors_for_rate_limited(self) -> None:
        """RATE_LIMITED is an error."""
        results = [self._result(ValidationStatus.RATE_LIMITED)]
        assert EnvValidator().has_errors(results) is True

    def test_has_errors_false_for_not_set(self) -> None:
        """NOT_SET is a warning, not an error."""
        results = [self._result(ValidationStatus.NOT_SET)]
        assert EnvValidator().has_errors(results) is False

    def test_has_errors_false_for_placeholder(self) -> None:
        """PLACEHOLDER is a warning, not an error."""
        results = [self._result(ValidationStatus.PLACEHOLDER)]
        assert EnvValidator().has_errors(results) is False

    def test_has_errors_false_for_valid(self) -> None:
        """VALID is neither warning nor error."""
        results = [self._result(ValidationStatus.VALID)]
        assert EnvValidator().has_errors(results) is False

    def test_has_warnings_for_not_set(self) -> None:
        """NOT_SET is a warning."""
        results = [self._result(ValidationStatus.NOT_SET)]
        assert EnvValidator().has_warnings(results) is True

    def test_has_warnings_for_placeholder(self) -> None:
        """PLACEHOLDER is a warning."""
        results = [self._result(ValidationStatus.PLACEHOLDER)]
        assert EnvValidator().has_warnings(results) is True

    def test_has_warnings_false_for_valid(self) -> None:
        """VALID is not a warning."""
        results = [self._result(ValidationStatus.VALID)]
        assert EnvValidator().has_warnings(results) is False

    def test_has_warnings_false_for_invalid_format(self) -> None:
        """INVALID_FORMAT is an error, not a warning."""
        results = [self._result(ValidationStatus.INVALID_FORMAT)]
        assert EnvValidator().has_warnings(results) is False


class TestCheckLlmKeysCommand:
    """Tests for CheckLlmKeysCommand.run."""

    def test_all_keys_unset_returns_zero(self, monkeypatch: MonkeyPatch) -> None:
        """Missing keys are warnings, not errors — run() must return 0."""
        _wipe_env(monkeypatch)
        with patch.object(EnvValidator, "print_results") as mock_print:
            exit_code = CheckLlmKeysCommand(tier=2).run()
        assert exit_code == 0
        mock_print.assert_called_once()

    def test_malformed_openai_key_returns_one(self, monkeypatch: MonkeyPatch) -> None:
        """Format error → has_errors True → run() returns 1."""
        _wipe_env(monkeypatch)
        monkeypatch.setenv("OPENAI_API_KEY", "garbage")

        validator = EnvValidator()
        results = validator.validate_all(tier=2)
        openai_result = next(r for r in results if r.var_name == "OPENAI_API_KEY")
        assert openai_result.status == ValidationStatus.INVALID_FORMAT
        assert validator.has_errors(results) is True

        exit_code = CheckLlmKeysCommand(tier=2).run()
        assert exit_code == 1

    def test_tier3_openai_mocked(self, monkeypatch: MonkeyPatch) -> None:
        """Tier 3 OpenAI path uses the mocked OpenAI client — no real call."""
        _wipe_env(monkeypatch)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-abc1234567890abcdef")

        mock_client = MagicMock()
        mock_client.models.list.return_value = []
        mock_openai_ctor = MagicMock(return_value=mock_client)

        monkeypatch.setattr(check_llm_keys_module, "OpenAI", mock_openai_ctor, raising=False)
        monkeypatch.setattr(check_llm_keys_module, "HAS_OPENAI", True, raising=False)

        result = EnvValidator().validate_tier3_openai("OPENAI_API_KEY")
        assert result.status == ValidationStatus.VALID
        mock_openai_ctor.assert_called_once_with(api_key="sk-abc1234567890abcdef")
        mock_client.models.list.assert_called_once()

    def test_tier3_anthropic_mocked(self, monkeypatch: MonkeyPatch) -> None:
        """Tier 3 Anthropic path uses the mocked Anthropic client — no real call."""
        _wipe_env(monkeypatch)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-abc1234567890abc")

        mock_client = MagicMock()
        mock_anthropic_ctor = MagicMock(return_value=mock_client)

        monkeypatch.setattr(check_llm_keys_module, "Anthropic", mock_anthropic_ctor, raising=False)
        monkeypatch.setattr(check_llm_keys_module, "HAS_ANTHROPIC", True, raising=False)

        result = EnvValidator().validate_tier3_anthropic("ANTHROPIC_API_KEY")
        assert result.status == ValidationStatus.VALID
        mock_anthropic_ctor.assert_called_once_with(api_key="sk-ant-abc1234567890abc")
        mock_client.messages.count_tokens.assert_called_once()

    def test_tier3_google_mocked(self, monkeypatch: MonkeyPatch) -> None:
        """Tier 3 Google path uses the mocked genai.Client — no real call."""
        _wipe_env(monkeypatch)
        monkeypatch.setenv("GOOGLE_API_KEY", "AIzaSy" + "x" * 30)

        mock_client = MagicMock()
        mock_client.models.list.return_value = iter([])
        mock_genai = MagicMock()
        mock_genai.Client.return_value = mock_client

        monkeypatch.setattr(check_llm_keys_module, "genai", mock_genai, raising=False)
        monkeypatch.setattr(check_llm_keys_module, "HAS_GOOGLE", True, raising=False)

        result = EnvValidator().validate_tier3_google("GOOGLE_API_KEY")
        assert result.status == ValidationStatus.VALID
        mock_genai.Client.assert_called_once()
