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

import ast
import logging
import os
import sys
from pathlib import Path
from typing import Any
from typing import List
from typing import Optional
from typing import Tuple

import pytest
from neuro_san.internals.graph.persistence.raw_manifest_restorer import RawManifestRestorer
from pyhocon import ConfigFactory
from pytest import MonkeyPatch

from neuro_san_studio.commands import init as init_module
from neuro_san_studio.commands.init import InitCommand
from neuro_san_studio.importer.agent_network_importer import AgentNetworkImporter
from neuro_san_studio.utils.shared_registries import SHARED_REGISTRY_INCLUDES

LOCAL_ROOTS: Tuple[str, ...] = ("coded_tools", "middleware")

# The repo checkout the scaffold is copied from (PackagePaths.installed_library_root resolves
# here when the tests run in-repo). Used to tell a `from pkg import name` that names a real
# source module — which the walker must therefore have copied — from one that names an
# attribute, which no static check can require.
REPO_ROOT: Path = Path(__file__).resolve().parents[3]

# What `ns init` must install. Spelled out rather than derived: the production list now comes from
# neuro_san_studio/templates/manifest.hocon, so pinning the expectation independently makes a change
# to that template a deliberate, reviewed change to what every new project contains, instead of a
# side effect noticed after release. Update both in the same commit.
EXPECTED_DEFAULT_NETWORKS: List[str] = [
    "basic/music_nerd.hocon",
    "agent_network_designer.hocon",
    "agent_network_editor.hocon",
    "agent_network_instructions_editor.hocon",
    "agent_network_query_generator.hocon",
    "agent_network_test_generator.hocon",
    "experimental/cruse_theme_agent.hocon",
    "experimental/cruse_widget_agent.hocon",
]


@pytest.fixture(name="scaffolded_project", scope="module")
def fixture_scaffolded_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One `ns init --providers openai` scaffold, shared by every read-only assertion.

    Scaffolding copies ~55 files, so doing it per test dominated this module's runtime.
    Tests that mutate the tree must scaffold their own instead of using this.
    """
    root = tmp_path_factory.mktemp("scaffold")
    InitCommand(providers_arg="openai", root_dir=str(root)).run()
    return root


def _import_from_base_parts(node: ast.ImportFrom, source_parts: List[str]) -> Optional[List[str]]:
    """
    Resolve the absolute package a ``from ... import ...`` statement is relative to.

    Mirrors CPython (and LocalImportWalker._import_from_base): an absolute import is just
    ``node.module``; a relative import anchors at the importing file's own package and climbs
    ``level - 1`` packages from there.

    :param node: The ``from ... import ...`` statement.
    :param source_parts: The importing file's path segments relative to the project root,
        e.g. ["coded_tools", "pkg", "tool.py"].
    :return: Absolute module segments of the import's base, or None when a relative import
        climbs above the tree (which CPython would reject too).
    """
    if node.level == 0:
        if node.module is None:
            return None
        return node.module.split(".")
    # Both `pkg/__init__.py` and `pkg/mod.py` sit in package `pkg`, so dropping the filename
    # yields the anchor package either way.
    package_parts: List[str] = source_parts[:-1]
    climb: int = node.level - 1
    if climb > len(package_parts):
        return None
    if climb:
        anchor: List[str] = package_parts[: len(package_parts) - climb]
    else:
        anchor = package_parts
    if not anchor:
        return None
    if node.module:
        return anchor + node.module.split(".")
    return anchor


def _local_imports_of(source: Path, source_parts: List[str]) -> List[Tuple[List[str], bool]]:
    """
    Collect every project-local module reference `source` makes, across all import shapes.

    Covers plain ``import a.b``, absolute ``from a.b import c``, and relative
    ``from .sibling import c`` / ``from . import c`` — the shapes the dependency walker must
    close over.

    :param source: The .py file to parse.
    :param source_parts: `source`'s path segments relative to the project root, used to
        anchor relative imports the way CPython does.
    :return: (module_segments, must_exist) pairs whose first segment is a LOCAL_ROOTS
        package. must_exist is True for references that can only be a module (plain imports
        and `from` bases). It is False for the names of a `from base import name` statement,
        which may be attributes: those are required only when the source repo has them as
        modules (see the caller).
    """
    references: List[Tuple[List[str], bool]] = []
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                references.append((alias.name.split("."), True))
        elif isinstance(node, ast.ImportFrom):
            base: Optional[List[str]] = _import_from_base_parts(node, source_parts)
            if base is None:
                continue
            references.append((base, True))
            for alias in node.names:
                # `from pkg import *` names nothing checkable statically.
                if alias.name == "*":
                    continue
                references.append((base + [alias.name], False))
    local: List[Tuple[List[str], bool]] = []
    for parts, must_exist in references:
        if parts and parts[0] in LOCAL_ROOTS:
            local.append((parts, must_exist))
    return local


def _module_exists_under(root: Path, parts: List[str]) -> bool:
    """
    Whether the dotted module whose segments are `parts` is importable under `root`.

    A bare directory counts too: an init-less directory is a PEP 420 namespace package the
    runtime imports happily (the repo ships several under coded_tools/), so requiring an
    __init__.py here would flag imports that actually work.

    :param root: Directory holding the top-level packages (scaffold root or repo root).
    :param parts: Module path segments, e.g. ["coded_tools", "pkg", "mod"].
    :return: True when ``<root>/.../mod.py`` exists or ``<root>/.../mod`` is a directory
        (with or without an ``__init__.py``).
    """
    base: Path = root.joinpath(*parts)
    if base.with_suffix(".py").is_file():
        return True
    return base.is_dir()


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

        assert (tmp_path / "registries" / "basic" / "music_nerd.hocon").is_file()
        for shared in SHARED_REGISTRY_INCLUDES:
            assert (tmp_path / "registries" / shared).is_file()
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
        # The designer reads manifest_and.hocon to learn which networks it may compose.
        assert (tmp_path / "registries" / "manifest_and.hocon").is_file()
        # Every default network lands on disk...
        for network in EXPECTED_DEFAULT_NETWORKS:
            assert (tmp_path / "registries" / network).is_file(), f"{network} was not scaffolded"
        # ...along with the coded tools and middleware they need.
        assert (tmp_path / "coded_tools" / "agent_network_editor" / "add_agent.py").is_file()
        assert (
            tmp_path / "middleware" / "agent_network_designer" / "agent_network_definition_middleware.py"
        ).is_file()

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

    def test_music_nerd_sourced_from_registries(self, scaffolded_project: Path) -> None:
        """music_nerd should be installed from the registries package like every other network."""
        import importlib.resources  # pylint: disable=import-outside-toplevel

        upstream = (importlib.resources.files("registries") / "basic" / "music_nerd.hocon").read_bytes()
        local = (scaffolded_project / "registries" / "basic" / "music_nerd.hocon").read_bytes()
        assert local == upstream

    def test_aaosa_sourced_from_registries(self, scaffolded_project: Path) -> None:
        """aaosa.hocon should be copied from the registries package via the safety-net loop."""
        self._assert_matches_template(scaffolded_project, "aaosa.hocon", "registries/aaosa.hocon", "registries")

    def test_aaosa_basic_sourced_from_registries(self, scaffolded_project: Path) -> None:
        """aaosa_basic.hocon should be copied from the registries package via the safety-net loop."""
        self._assert_matches_template(
            scaffolded_project, "aaosa_basic.hocon", "registries/aaosa_basic.hocon", "registries"
        )

    def test_aaosa_basic_debug_sourced_from_registries(self, scaffolded_project: Path) -> None:
        """aaosa_basic_debug.hocon should be copied from the registries package via the safety-net loop."""
        self._assert_matches_template(
            scaffolded_project, "aaosa_basic_debug.hocon", "registries/aaosa_basic_debug.hocon", "registries"
        )

    def test_expertise_scoping_instructions_sourced_from_registries(self, scaffolded_project: Path) -> None:
        """expertise_scoping_instructions.hocon should be copied from the registries package.

        The scaffolded basic/music_nerd.hocon includes it and substitutes
        ``${expertise_scoping_instructions}``, so a project missing this file fails to parse.
        """
        self._assert_matches_template(
            scaffolded_project,
            "expertise_scoping_instructions.hocon",
            "registries/expertise_scoping_instructions.hocon",
            "registries",
        )

    def test_manifest_sourced_from_templates(self, scaffolded_project: Path) -> None:
        """manifest.hocon should be copied from neuro_san_studio.templates."""
        self._assert_matches_template(scaffolded_project, "manifest.hocon", "registries/manifest.hocon")

    def test_mcp_info_sourced_from_mcp_package(self, scaffolded_project: Path) -> None:
        """mcp_info.hocon should be copied from neuro_san_studio.mcp (the same file run.py uses)."""
        self._assert_matches_template(
            scaffolded_project, "mcp_info.hocon", "mcp/mcp_info.hocon", "neuro_san_studio.mcp"
        )

    def test_plugins_sourced_from_templates(self, scaffolded_project: Path) -> None:
        """plugins.hocon should be copied from neuro_san_studio.templates."""
        self._assert_matches_template(scaffolded_project, "plugins.hocon", "config/plugins.hocon")


class TestTemplateSync:  # pylint: disable=too-few-public-methods
    """Ensure packaged templates stay in sync with their source-of-truth files."""

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

    def test_plugins_template_matches_config(self) -> None:
        """templates/plugins.hocon must be byte-identical to config/plugins.hocon."""
        self._assert_template_matches_source("plugins.hocon", "config/plugins.hocon")


class TestSharedRegistryIncludes:
    """Guard the single shared-includes list that `ns init` and `ns import` both consume."""

    def test_importer_uses_the_shared_constant(self) -> None:
        """AgentNetworkImporter must not maintain its own copy of the list.

        `expertise_scoping_instructions.hocon` was missing from both lists because they were
        edited independently. Asserting identity — not equality — keeps them one object.
        """
        assert AgentNetworkImporter.SHARED_INCLUDES is SHARED_REGISTRY_INCLUDES

    def test_every_shared_include_exists_in_the_packaged_registries(self) -> None:
        """Each name must resolve to a real file, or `ns init` silently scaffolds nothing.

        `_copy_template` reads through importlib.resources, so a typo or a renamed fragment
        surfaces only at scaffold time — and `ns import` degrades to a warning, not an error.
        """
        import importlib.resources  # pylint: disable=import-outside-toplevel

        for shared in SHARED_REGISTRY_INCLUDES:
            assert (importlib.resources.files("registries") / shared).is_file(), (
                f"{shared} is listed in SHARED_REGISTRY_INCLUDES but is not in the registries package."
            )

    def test_no_shared_include_is_an_agent_network(self) -> None:
        """Shared includes must be substitution fragments, never networks.

        The list doubles as the manifest exclusion set, so anything with a `tools` block
        landing here would stop being served the moment it was added.
        """
        import importlib.resources  # pylint: disable=import-outside-toplevel

        for shared in SHARED_REGISTRY_INCLUDES:
            text = (importlib.resources.files("registries") / shared).read_text(encoding="utf-8")
            assert "tools" not in ConfigFactory.parse_string(text), (
                f"{shared} looks like an agent network; excluding it from the manifest would unserve it."
            )


class TestDefaultNetworks:
    """`ns init` must scaffold a project where the Agent Network Designer actually runs."""

    @staticmethod
    def _manifest_keys(project: Path) -> dict:
        """Parse the scaffolded manifest the way the neuro-san server reads it."""
        prev_cwd = os.getcwd()
        try:
            os.chdir(project)
            return dict(RawManifestRestorer().restore(file_reference="registries/manifest.hocon"))
        finally:
            os.chdir(prev_cwd)

    def test_scaffolded_tree_is_import_complete(self, scaffolded_project: Path) -> None:
        """Every coded_tools/middleware module the scaffold imports must exist in the scaffold.

        This is the regression guard for the dependency-walker gap. The walker used to map each
        HOCON `class` field to exactly one .py file and stop, so add_agent.py landed without the
        constants.py / and_logger.py / progress_handler.py it imports at module scope, and the
        designer died with ModuleNotFoundError on first use. Asserting the closure — rather than
        a hand-written file list — keeps holding as the designer's own imports change.

        All import shapes count: plain `import a.b`, `from a.b import c`, and
        relative `from .sibling import c` — including imports made only in a package
        __init__.py, which execute whenever any module of the package is imported. A
        `from base import name` name may be an attribute rather than a module, which no
        static check can require; it is required exactly when the source repo has it as a
        module, because then the walker's job was to copy it.

        :param scaffolded_project: The shared read-only `ns init` scaffold fixture.
        """
        project = scaffolded_project

        missing: List[Tuple[str, str]] = []
        for root in LOCAL_ROOTS:
            for source in sorted((project / root).rglob("*.py")):
                source_parts: List[str] = list(source.relative_to(project).parts)
                for parts, must_exist in _local_imports_of(source, source_parts):
                    if _module_exists_under(project, parts):
                        continue
                    if not must_exist and not _module_exists_under(REPO_ROOT, parts):
                        # `from base import name` where the repo has no such module either:
                        # an attribute import, satisfied by `base` alone (checked above via
                        # its own must_exist entry).
                        continue
                    missing.append((str(source.relative_to(project)), ".".join(parts)))

        assert not missing, f"scaffolded modules import files that were not scaffolded: {missing}"

    def test_package_roots_are_regular_packages(self, scaffolded_project: Path) -> None:
        """coded_tools/ and middleware/ need an __init__.py or the installed copies shadow them.

        Python treats a directory without __init__.py as a namespace *portion* and keeps
        scanning sys.path, so neuro-san-studio's own installed coded_tools package wins even
        though the project root comes first. The project's tools would then be silently ignored.
        """
        project = scaffolded_project

        assert (project / "coded_tools" / "__init__.py").is_file()
        assert (project / "middleware" / "__init__.py").is_file()

    def test_manifest_declares_every_default_network(self, scaffolded_project: Path) -> None:
        """A network on disk but absent from the manifest is not served at all."""
        keys = self._manifest_keys(scaffolded_project)

        for network in EXPECTED_DEFAULT_NETWORKS:
            assert network in keys, f"{network} was scaffolded but not registered"

    def test_designer_manifest_parses_and_its_includes_resolve(
        self, scaffolded_project: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The scaffolded manifest_and.hocon must parse cleanly through the designer's read path.

        The designer's GetSubnetwork reads registries/manifest_and.hocon relative to the
        project root via RawManifestRestorer, and pyhocon resolves its `include` directives
        against the process CWD. A template drift — e.g. "syncing" it with the repo-level
        registries/manifest_and.hocon, which additionally includes the industry manifest that
        `ns init` never scaffolds — would make every fresh project emit pyhocon
        "Cannot include file" warnings while still returning an empty mapping, so an
        existence-only assertion cannot catch it. Guard both: the restore must produce a
        mapping, and pyhocon must stay silent, meaning every include resolved.

        :param scaffolded_project: The shared read-only `ns init` scaffold fixture.
        :param caplog: pytest's log capture, used to detect pyhocon include failures.
        """
        project = scaffolded_project
        prev_cwd: str = os.getcwd()
        try:
            os.chdir(project)
            with caplog.at_level(logging.WARNING, logger="pyhocon.config_parser"):
                # The external restorer is annotated `-> Any`; dict(raw) below proves it is a mapping.
                raw: Any = RawManifestRestorer().restore(
                    file_reference=os.path.join("registries", "manifest_and.hocon")
                )
        finally:
            os.chdir(prev_cwd)

        # A fresh scaffold has no generated networks yet, so the designer sees an empty
        # (but valid) palette. dict() also asserts the restore returned a mapping.
        assert not dict(raw)
        pyhocon_complaints: List[str] = []
        for record in caplog.records:
            if record.name == "pyhocon.config_parser":
                pyhocon_complaints.append(record.getMessage())
        assert not pyhocon_complaints, f"manifest_and.hocon includes did not resolve: {pyhocon_complaints}"

    def test_support_networks_are_served_but_not_public(self, scaffolded_project: Path) -> None:
        """The designer's sub-networks and the CRUSE pair must be reachable, not listed.

        `ns import` would register these as a flat `true`, which is why init scaffolds the
        manifest from a template instead of calling update_manifest.
        """
        keys = self._manifest_keys(scaffolded_project)

        for support in (
            "agent_network_editor.hocon",
            "agent_network_instructions_editor.hocon",
            "agent_network_query_generator.hocon",
            "experimental/cruse_theme_agent.hocon",
            "experimental/cruse_widget_agent.hocon",
        ):
            assert dict(keys[support]) == {"serve": True, "public": False}, support

    def test_public_networks_are_plain_true(self, scaffolded_project: Path) -> None:
        """The entry points a user picks from the UI stay publicly listed."""
        keys = self._manifest_keys(scaffolded_project)

        for public in (
            "basic/music_nerd.hocon",
            "agent_network_designer.hocon",
            "agent_network_test_generator.hocon",
        ):
            assert keys[public] is True, public

    def test_architect_is_not_installed(self, scaffolded_project: Path) -> None:
        """agent_network_architect needs Gmail credentials, Selenium, and a second server.

        It ships disabled even in this repo's manifest, so scaffolding it would only give a new
        user a network that cannot run. `ns import agent_network_architect` remains available.
        """
        project = scaffolded_project

        assert not (project / "registries" / "agent_network_architect.hocon").exists()
        assert "agent_network_architect.hocon" not in self._manifest_keys(project)

    def test_rerun_is_idempotent_and_preserves_edits(self, tmp_path: Path) -> None:
        """A second `ns init` must not clobber a network the user has since edited."""
        project = tmp_path
        InitCommand(providers_arg="openai", root_dir=str(project)).run()
        edited = project / "registries" / "agent_network_designer.hocon"
        edited.write_text("# my edits\n")

        InitCommand(providers_arg="openai", root_dir=str(project)).run()

        assert edited.read_text() == "# my edits\n"

    def test_manifest_declares_nothing_it_does_not_install(self, scaffolded_project: Path) -> None:
        """Every served key must have landed on disk, or the server hands out a 404."""
        keys = self._manifest_keys(scaffolded_project)

        assert set(keys) == set(EXPECTED_DEFAULT_NETWORKS)


class TestDefaultNetworkDerivation:
    """Guard the install list `ns init` derives from templates/manifest.hocon."""

    def test_derived_list_is_pinned(self) -> None:
        """What every new project gets must be an explicit, reviewed decision.

        The list is derived from the manifest template so it cannot drift from what is served --
        but that also means a one-line edit to the template silently changes what every `ns init`
        installs. Pin it here so the change shows up in review.
        """
        assert InitCommand._default_network_hocons() == EXPECTED_DEFAULT_NETWORKS  # pylint: disable=protected-access

    def test_derivation_ignores_the_generated_include(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """The result must not depend on the directory `ns init` was invoked from.

        The template carries `include "registries/generated/manifest.hocon"` for the benefit of the
        running server. pyhocon resolves a relative include against the process CWD, so honoring it
        from a studio checkout would splice every designer-generated network into the install list,
        and honoring it from a re-initialized project would splice in that project's own output.
        """
        # pylint: disable=protected-access
        monkeypatch.chdir(Path(__file__).resolve().parents[3])
        from_studio_root = InitCommand._default_network_hocons()
        monkeypatch.chdir(tmp_path)
        from_empty_dir = InitCommand._default_network_hocons()

        assert from_studio_root == from_empty_dir == EXPECTED_DEFAULT_NETWORKS
        assert not [name for name in from_studio_root if name.startswith("generated/")]

    def test_derivation_logs_no_include_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """An unresolvable include makes pyhocon log "Cannot include file ..." to the console.

        `ns init` output is the first thing a new user sees; it must not carry parser warnings
        about a file that was never meant to be resolved at scaffold time.
        """
        with caplog.at_level(logging.WARNING, logger="pyhocon.config_parser"):
            InitCommand._default_network_hocons()  # pylint: disable=protected-access

        assert not caplog.records

    def test_every_derived_network_exists_in_the_registries_package(self) -> None:
        """A typo'd or renamed key would otherwise surface only as a [warn] during a real init.

        AgentNetworkImporter degrades a missing source HOCON to a warning rather than an error, so
        a bad key in the template produces a project quietly missing a network.
        """
        import importlib.resources  # pylint: disable=import-outside-toplevel

        for network in InitCommand._default_network_hocons():  # pylint: disable=protected-access
            path = importlib.resources.files("registries")
            for segment in network.split("/"):
                path = path / segment
            assert path.is_file(), f"{network} is declared in templates/manifest.hocon but is not in registries/."
