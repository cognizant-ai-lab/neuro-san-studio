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

"""Tests for the `neuro-san-studio init` command."""

import os
import sys
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from neuro_san_studio.commands import init as init_module
from neuro_san_studio.commands.init import InitCommand


class TestProvidersArgParsing:
    """Tests for InitCommand._parse_providers_arg."""

    def test_single_provider(self) -> None:
        """A single provider key should come back as a single-item list."""
        assert InitCommand._parse_providers_arg("openai") == ["openai"]  # pylint: disable=protected-access

    def test_multiple_providers_preserve_order(self) -> None:
        """User order should be preserved."""
        assert InitCommand._parse_providers_arg(  # pylint: disable=protected-access
            "anthropic,openai,google"
        ) == ["anthropic", "openai", "google"]

    def test_dedupe_and_whitespace(self) -> None:
        """Whitespace should be stripped and duplicates removed."""
        assert InitCommand._parse_providers_arg(  # pylint: disable=protected-access
            " openai , anthropic, openai"
        ) == ["openai", "anthropic"]

    def test_case_insensitive(self) -> None:
        """Provider keys should be case-insensitive."""
        assert InitCommand._parse_providers_arg("OpenAI,GOOGLE") == [  # pylint: disable=protected-access
            "openai",
            "google",
        ]

    def test_invalid_provider_raises(self) -> None:
        """An unknown provider should raise ValueError with a helpful message."""
        with pytest.raises(ValueError, match="Unknown provider 'bogus'"):
            InitCommand._parse_providers_arg("openai,bogus")  # pylint: disable=protected-access

    def test_empty_raises(self) -> None:
        """An empty --providers value should raise."""
        with pytest.raises(ValueError, match="at least one provider"):
            InitCommand._parse_providers_arg(",,")  # pylint: disable=protected-access


class TestLlmConfigRendering:
    """Tests for InitCommand._render_llm_config."""

    def test_single_provider_no_class_key(self) -> None:
        """Single provider should render a flat model_name block with no class key."""
        # pylint: disable=protected-access
        rendered = InitCommand._render_llm_config(["openai"])
        assert '"model_name": "gpt-5.2"' in rendered
        assert '"class"' not in rendered
        assert '"fallbacks"' not in rendered

    def test_multiple_providers_render_fallbacks(self) -> None:
        """Multiple providers should render a fallbacks list in the selected order."""
        # pylint: disable=protected-access
        rendered = InitCommand._render_llm_config(["openai", "anthropic", "google"])
        assert '"fallbacks"' in rendered
        # Order: openai first, then anthropic, then google
        openai_pos = rendered.index("gpt-5.2")
        anthropic_pos = rendered.index("claude-sonnet")
        google_pos = rendered.index("gemini-3-flash")
        assert openai_pos < anthropic_pos < google_pos
        assert '"class"' not in rendered

    def test_openai_promoted_to_front_of_fallbacks(self) -> None:
        """Even if OpenAI is selected last, it should lead the fallback list."""
        # pylint: disable=protected-access
        rendered = InitCommand._render_llm_config(["anthropic", "openai"])
        assert rendered.index("gpt-5.2") < rendered.index("claude-sonnet")

    def test_non_openai_order_preserved(self) -> None:
        """Without OpenAI, the user's order should be preserved."""
        # pylint: disable=protected-access
        rendered = InitCommand._render_llm_config(["google", "anthropic"])
        assert rendered.index("gemini-3-flash") < rendered.index("claude-sonnet")


class TestRunFlow:
    """Tests for the full InitCommand.run() flow."""

    def test_run_scaffolds_all_files(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """`init --providers openai` should create all four starter files."""
        monkeypatch.chdir(tmp_path)
        # Force the non-TTY branch to exercise the flag path.
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
        InitCommand(providers_arg="openai", root_dir=str(tmp_path)).run()

        assert (tmp_path / "registries" / "music_nerd.hocon").is_file()
        assert (tmp_path / "registries" / "manifest.hocon").read_text().strip().startswith("{")
        assert (tmp_path / "mcp" / "mcp_info.hocon").is_file()
        llm_config = (tmp_path / "config" / "llm_config.hocon").read_text()
        assert '"model_name": "gpt-5.2"' in llm_config
        assert '"class"' not in llm_config

    def test_run_skips_existing_files(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Existing target files must be left untouched and logged as [skip]."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        existing = config_dir / "llm_config.hocon"
        existing.write_text("DO NOT OVERWRITE\n")

        InitCommand(providers_arg="openai", root_dir=str(tmp_path)).run()

        assert existing.read_text() == "DO NOT OVERWRITE\n"
        out = capsys.readouterr().out
        assert "[skip]" in out
        assert "config/llm_config.hocon" in out or os.path.join("config", "llm_config.hocon") in out

    def test_run_non_tty_defaults_to_openai(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """With no --providers and no TTY, the command must default to OpenAI."""
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
        InitCommand(providers_arg=None, root_dir=str(tmp_path)).run()
        llm_config = (tmp_path / "config" / "llm_config.hocon").read_text()
        assert '"model_name": "gpt-5.2"' in llm_config
        assert '"fallbacks"' not in llm_config

    def test_run_interactive_multi_select(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Interactive mode should parse numbered input into the right providers."""
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        monkeypatch.setattr(init_module, "timedinput", lambda *_a, **_kw: "1,2")
        InitCommand(providers_arg=None, root_dir=str(tmp_path)).run()
        llm_config = (tmp_path / "config" / "llm_config.hocon").read_text()
        assert '"fallbacks"' in llm_config
        assert "gpt-5.2" in llm_config
        assert "claude-sonnet" in llm_config

    def test_run_interactive_empty_input_defaults_to_openai(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Pressing enter at the prompt should accept the default (OpenAI)."""
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        monkeypatch.setattr(init_module, "timedinput", lambda *_a, **_kw: "")
        InitCommand(providers_arg=None, root_dir=str(tmp_path)).run()
        llm_config = (tmp_path / "config" / "llm_config.hocon").read_text()
        assert '"model_name": "gpt-5.2"' in llm_config

    def test_music_nerd_sourced_from_templates(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """music_nerd.hocon should be copied from neuro_san_studio.templates."""
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
        InitCommand(providers_arg="openai", root_dir=str(tmp_path)).run()

        from importlib import resources  # pylint: disable=import-outside-toplevel

        upstream = (resources.files("neuro_san_studio.templates") / "music_nerd.hocon").read_bytes()
        local = (tmp_path / "registries" / "music_nerd.hocon").read_bytes()
        assert local == upstream

    def test_manifest_sourced_from_templates(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """manifest.hocon should be copied from neuro_san_studio.templates."""
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
        InitCommand(providers_arg="openai", root_dir=str(tmp_path)).run()

        from importlib import resources  # pylint: disable=import-outside-toplevel

        upstream = (resources.files("neuro_san_studio.templates") / "manifest.hocon").read_bytes()
        local = (tmp_path / "registries" / "manifest.hocon").read_bytes()
        assert local == upstream

    def test_mcp_info_sourced_from_mcp_package(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """mcp_info.hocon should be copied from neuro_san_studio.mcp (the same file run.py uses)."""
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
        InitCommand(providers_arg="openai", root_dir=str(tmp_path)).run()

        from importlib import resources  # pylint: disable=import-outside-toplevel

        upstream = (resources.files("neuro_san_studio.mcp") / "mcp_info.hocon").read_bytes()
        local = (tmp_path / "mcp" / "mcp_info.hocon").read_bytes()
        assert local == upstream


class TestTemplateSync:  # pylint: disable=too-few-public-methods
    """Ensure scaffolded templates stay in sync with their source-of-truth files in registries/."""

    def test_music_nerd_template_matches_registries_basic(self) -> None:
        """templates/music_nerd.hocon must be byte-identical to registries/basic/music_nerd.hocon."""
        from importlib import resources  # pylint: disable=import-outside-toplevel

        template = (resources.files("neuro_san_studio.templates") / "music_nerd.hocon").read_bytes()
        repo_root = Path(__file__).resolve().parents[3]
        source_of_truth = (repo_root / "registries" / "basic" / "music_nerd.hocon").read_bytes()
        assert template == source_of_truth, (
            "neuro_san_studio/templates/music_nerd.hocon has drifted from "
            "registries/basic/music_nerd.hocon. Update both together."
        )
