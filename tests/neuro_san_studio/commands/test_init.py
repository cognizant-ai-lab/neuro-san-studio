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
from pyhocon import ConfigFactory
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

    def test_user_order_preserved_when_openai_not_first(self) -> None:
        """Regression test for #1076: user-selected order must be honored.

        Earlier behavior auto-promoted OpenAI to position 0 even when the user
        explicitly listed it last; this asserts the fix that respects the
        user's order.
        """
        # pylint: disable=protected-access
        rendered = InitCommand._render_llm_config(["anthropic", "openai"])
        assert rendered.index("claude-sonnet") < rendered.index("gpt-5.2")

    def test_three_provider_order_preserved_with_openai_last(self) -> None:
        """Regression test for #1076: arbitrary three-provider order is preserved."""
        # pylint: disable=protected-access
        rendered = InitCommand._render_llm_config(["google", "anthropic", "openai"])
        google_pos = rendered.index("gemini-3-flash")
        anthropic_pos = rendered.index("claude-sonnet")
        openai_pos = rendered.index("gpt-5.2")
        assert google_pos < anthropic_pos < openai_pos

    def test_non_openai_order_preserved(self) -> None:
        """Without OpenAI, the user's order should be preserved."""
        # pylint: disable=protected-access
        rendered = InitCommand._render_llm_config(["google", "anthropic"])
        assert rendered.index("gemini-3-flash") < rendered.index("claude-sonnet")

    def test_two_provider_openai_already_first_unchanged(self) -> None:
        """Boundary for #1076: when OpenAI is already first, order is unchanged.

        The removed promotion only fired when OpenAI was selected but not first
        (``ordered[0] != "openai"``); this pins the symmetric case where the
        promotion was always a no-op, so a future reintroduction is caught.
        """
        # pylint: disable=protected-access
        rendered = InitCommand._render_llm_config(["openai", "google"])
        fallbacks = [dict(fb) for fb in ConfigFactory.parse_string(rendered)["llm_config"]["fallbacks"]]
        assert [fb["model_name"] for fb in fallbacks] == ["gpt-5.2", "gemini-3-flash"]

    def test_empty_providers_raises(self) -> None:
        """An empty provider list must raise rather than render an empty fallbacks array.

        An empty ``fallbacks`` list is syntactically valid HOCON but the neuro-san
        runtime rejects it with "No fully-specified LLM found"; the guard turns a
        silent unbootable-project footgun into an explicit error.
        """
        # pylint: disable=protected-access
        with pytest.raises(ValueError, match="at least one provider"):
            InitCommand._render_llm_config([])


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

    def test_run_providers_arg_preserves_anthropic_first(self, tmp_path: Path) -> None:
        """Regression test for #1076: ``--providers anthropic,openai`` yields Anthropic-first config."""
        InitCommand(providers_arg="anthropic,openai", root_dir=str(tmp_path)).run()
        llm_config = (tmp_path / "config" / "llm_config.hocon").read_text()
        assert llm_config.index("claude-sonnet") < llm_config.index("gpt-5.2")

    def test_run_interactive_anthropic_first_preserves_order(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Regression test for #1076: interactive selection ``2,1`` yields Anthropic-first config.

        Mirrors the exact reproduction steps in the issue: pick Anthropic (2)
        then OpenAI (1) at the prompt, and confirm the generated fallback file
        lists Anthropic before OpenAI.
        """
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        monkeypatch.setattr(init_module, "timedinput", lambda *_a, **_kw: "2,1")
        InitCommand(providers_arg=None, root_dir=str(tmp_path)).run()
        llm_config = (tmp_path / "config" / "llm_config.hocon").read_text()
        assert llm_config.index("claude-sonnet") < llm_config.index("gpt-5.2")

    def test_parsed_fallbacks_first_entry_is_user_primary(self, tmp_path: Path) -> None:
        """Behavioral regression for #1076: parse the generated config the same
        way the agent chain does and assert ``fallbacks[0]`` is the user's
        first-selected provider.

        The runtime path is ``langchain_run_context.create_agent_with_fallbacks``,
        which extracts ``fallbacks`` from the parsed ``llm_config`` and iterates
        it; the first entry is treated as primary. Asserting that here gives a
        higher-fidelity check than substring ordering in the rendered text.
        """
        InitCommand(providers_arg="anthropic,openai", root_dir=str(tmp_path)).run()
        raw = (tmp_path / "config" / "llm_config.hocon").read_text()
        parsed_llm_config = ConfigFactory.parse_string(raw)["llm_config"]
        fallbacks = [dict(fb) for fb in parsed_llm_config["fallbacks"]]
        assert fallbacks[0]["model_name"] == "claude-sonnet"
        assert fallbacks[1]["model_name"] == "gpt-5.2"

    def test_parsed_fallbacks_three_provider_order_preserved(self, tmp_path: Path) -> None:
        """Behavioral regression for #1076: a three-provider selection preserves
        order through HOCON parsing into the runtime ``fallbacks`` list.
        """
        InitCommand(providers_arg="google,anthropic,openai", root_dir=str(tmp_path)).run()
        raw = (tmp_path / "config" / "llm_config.hocon").read_text()
        parsed_llm_config = ConfigFactory.parse_string(raw)["llm_config"]
        fallbacks = [dict(fb) for fb in parsed_llm_config["fallbacks"]]
        assert [fb["model_name"] for fb in fallbacks] == ["gemini-3-flash", "claude-sonnet", "gpt-5.2"]

    def test_issue_1076_interactive_2_1_parsed_anthropic_first(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Behavioral regression for #1076 at the parsed layer: the exact ``2,1``
        keystrokes from the issue must yield ``fallbacks == [anthropic, openai]``
        once the generated HOCON is parsed the way the agent chain parses it.

        This raises the issue's literal reproduction from substring ordering
        (``test_run_interactive_anthropic_first_preserves_order``) to the
        structural layer the runtime actually reads.
        """
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        monkeypatch.setattr(init_module, "timedinput", lambda *_a, **_kw: "2,1")
        InitCommand(providers_arg=None, root_dir=str(tmp_path)).run()
        raw = (tmp_path / "config" / "llm_config.hocon").read_text()
        parsed_llm_config = ConfigFactory.parse_string(raw)["llm_config"]
        models = [dict(fb)["model_name"] for fb in parsed_llm_config["fallbacks"]]
        assert models == ["claude-sonnet", "gpt-5.2"]

    def test_single_provider_parsed_is_flat_no_fallbacks(self, tmp_path: Path) -> None:
        """Regression guard for the untouched single-provider branch.

        The runtime wraps a flat ``llm_config`` as a one-entry fallback list via
        ``llm_config.get("fallbacks", [llm_config])``; an accidental ``fallbacks``
        wrap or a stray ``class`` key here would change resolution. Asserts the
        parsed shape rather than substrings.
        """
        InitCommand(providers_arg="openai", root_dir=str(tmp_path)).run()
        raw = (tmp_path / "config" / "llm_config.hocon").read_text()
        parsed_llm_config = ConfigFactory.parse_string(raw)["llm_config"]
        assert parsed_llm_config["model_name"] == "gpt-5.2"
        assert "fallbacks" not in parsed_llm_config
        assert "class" not in parsed_llm_config

    def test_multi_provider_has_no_top_level_model_name(self, tmp_path: Path) -> None:
        """Multi-provider config must rely solely on the ``fallbacks`` list.

        A stray top-level ``model_name`` would be read as a default by any
        consumer that does not enter the fallback loop (the exact misread that
        made the original review believe the fix was cosmetic).
        """
        InitCommand(providers_arg="anthropic,openai", root_dir=str(tmp_path)).run()
        raw = (tmp_path / "config" / "llm_config.hocon").read_text()
        parsed_llm_config = ConfigFactory.parse_string(raw)["llm_config"]
        assert "model_name" not in parsed_llm_config
        assert "fallbacks" in parsed_llm_config

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
