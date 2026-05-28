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

    @staticmethod
    def _run_init(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Scaffold a starter project with the OpenAI provider."""
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
        InitCommand(providers_arg="openai", root_dir=str(tmp_path)).run()

    @staticmethod
    def _assert_matches_template(
        tmp_path: Path,
        template_name: str,
        dest_rel: str,
        package: str = "neuro_san_studio.templates",
    ) -> None:
        """Assert a scaffolded file is byte-identical to its packaged template."""
        import importlib.resources  # pylint: disable=import-outside-toplevel

        upstream = (importlib.resources.files(package) / template_name).read_bytes()
        local = (tmp_path / dest_rel).read_bytes()
        assert local == upstream

    def test_run_scaffolds_all_files(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """`init --providers openai` should create all starter files."""
        monkeypatch.chdir(tmp_path)
        self._run_init(tmp_path, monkeypatch)

        assert (tmp_path / "registries" / "music_nerd.hocon").is_file()
        assert (tmp_path / "registries" / "aaosa.hocon").is_file()
        assert (tmp_path / "registries" / "aaosa_basic.hocon").is_file()
        assert (tmp_path / "registries" / "aaosa_basic_debug.hocon").is_file()
        assert (tmp_path / "registries" / "manifest.hocon").read_text().strip().startswith("{")
        # registries/generated/ must exist with an empty manifest so the include in the
        # main manifest resolves before agent_network_designer ever runs.
        generated_manifest = tmp_path / "registries" / "generated" / "manifest.hocon"
        assert generated_manifest.is_file()
        assert generated_manifest.read_text().strip() in ("{}", "{\n}")
        # Main manifest must declare the include so server-side discovery picks up
        # designer-generated networks the moment they appear.
        main_manifest = (tmp_path / "registries" / "manifest.hocon").read_text()
        assert 'include "registries/generated/manifest.hocon"' in main_manifest
        assert (tmp_path / "mcp" / "mcp_info.hocon").is_file()
        assert (tmp_path / "config" / "plugins.hocon").is_file()
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
        self._run_init(tmp_path, monkeypatch)
        self._assert_matches_template(tmp_path, "music_nerd.hocon", "registries/music_nerd.hocon")

    def test_aaosa_sourced_from_registries(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """aaosa.hocon should be copied from the registries package via the safety-net loop."""
        self._run_init(tmp_path, monkeypatch)
        self._assert_matches_template(tmp_path, "aaosa.hocon", "registries/aaosa.hocon", "registries")

    def test_aaosa_basic_sourced_from_registries(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """aaosa_basic.hocon should be copied from the registries package via the safety-net loop."""
        self._run_init(tmp_path, monkeypatch)
        self._assert_matches_template(tmp_path, "aaosa_basic.hocon", "registries/aaosa_basic.hocon", "registries")

    def test_aaosa_basic_debug_sourced_from_registries(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """aaosa_basic_debug.hocon should be copied from the registries package via the safety-net loop."""
        self._run_init(tmp_path, monkeypatch)
        self._assert_matches_template(
            tmp_path, "aaosa_basic_debug.hocon", "registries/aaosa_basic_debug.hocon", "registries"
        )

    def test_manifest_sourced_from_templates(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """manifest.hocon should be copied from neuro_san_studio.templates."""
        self._run_init(tmp_path, monkeypatch)
        self._assert_matches_template(tmp_path, "manifest.hocon", "registries/manifest.hocon")

    def test_mcp_info_sourced_from_mcp_package(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """mcp_info.hocon should be copied from neuro_san_studio.mcp (the same file run.py uses)."""
        self._run_init(tmp_path, monkeypatch)
        self._assert_matches_template(tmp_path, "mcp_info.hocon", "mcp/mcp_info.hocon", "neuro_san_studio.mcp")

    def test_plugins_sourced_from_templates(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """plugins.hocon should be copied from neuro_san_studio.templates."""
        self._run_init(tmp_path, monkeypatch)
        self._assert_matches_template(tmp_path, "plugins.hocon", "config/plugins.hocon")


class TestTemplateSync:
    """Ensure scaffolded templates stay in sync with their source-of-truth files in registries/ and config/."""

    @staticmethod
    def _assert_template_matches_source(template_name: str, source_rel: str) -> None:
        """Assert a packaged template is byte-identical to its source-of-truth file."""
        import importlib.resources  # pylint: disable=import-outside-toplevel

        template = (importlib.resources.files("neuro_san_studio.templates") / template_name).read_bytes()
        repo_root = Path(__file__).resolve().parents[3]
        source_of_truth = (repo_root / source_rel).read_bytes()
        assert template == source_of_truth, (
            f"templates/{template_name} has drifted from {source_rel}. Update both together."
        )

    def test_music_nerd_template_matches_registries_basic(self) -> None:
        """templates/music_nerd.hocon must be byte-identical to registries/basic/music_nerd.hocon."""
        self._assert_template_matches_source("music_nerd.hocon", "registries/basic/music_nerd.hocon")

    def test_plugins_template_matches_config(self) -> None:
        """templates/plugins.hocon must be byte-identical to config/plugins.hocon."""
        self._assert_template_matches_source("plugins.hocon", "config/plugins.hocon")
