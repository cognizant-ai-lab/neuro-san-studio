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

"""Tests for the validate command wrapper and its manifest-driven external agent discovery."""

import io
import os
import shutil
import sys
import tempfile
from functools import partial
from pathlib import Path
from typing import Any
from unittest import TestCase
from unittest.mock import patch

from neuro_san_studio.commands.validate import ValidateCommand
from neuro_san_studio.discovery.manifest_read_error import ManifestReadError

_MODULE = "neuro_san_studio.commands.validate"


class TestValidateCommandRun(TestCase):  # pylint: disable=too-many-public-methods
    """Tests for ValidateCommand.run - a thin wrapper over HoconValidatorCli plus manifest discovery."""

    def setUp(self) -> None:
        """
        Keep discovery and the class check away from the real repo and the developer's environment.
        """
        lister_patcher = patch(f"{_MODULE}.ServedNetworkLister")
        self.mock_lister = lister_patcher.start()
        self.addCleanup(lister_patcher.stop)
        self.mock_lister.return_value.list_names.return_value = []
        self.mock_lister.return_value.warnings = []

        checker_patcher = patch(f"{_MODULE}.NetworkClassChecker")
        self.mock_checker = checker_patcher.start()
        self.addCleanup(checker_patcher.stop)
        self.mock_checker.return_value.check.return_value = []
        self.mock_checker.return_value.get_checked_count.return_value = 0

        env_patcher = patch.dict(os.environ)
        env_patcher.start()
        self.addCleanup(env_patcher.stop)
        os.environ.pop("AGENT_MANIFEST_FILE", None)

    @staticmethod
    def _run_capturing_argv(command: ValidateCommand) -> list:
        """Run the command against a fake HoconValidatorCli and return the argv it saw."""
        captured = {}

        def fake_main():
            captured["argv"] = list(sys.argv)
            return 0

        with patch(f"{_MODULE}.HoconValidatorCli") as mock_cli:
            mock_cli.return_value.main.side_effect = fake_main
            command.run()
        return captured["argv"]

    @staticmethod
    def _external_agents_arg(argv: list) -> str:
        """Return the value that followed --external-agents in argv."""
        return argv[argv.index("--external-agents") + 1]

    def test_valid_returns_zero(self):
        """When the underlying validator returns 0, run() returns 0."""
        with patch(f"{_MODULE}.HoconValidatorCli") as mock_cli:
            mock_cli.return_value.main.return_value = 0
            self.assertEqual(ValidateCommand("agent.hocon").run(), 0)

    def test_validation_errors_return_one(self):
        """When the underlying validator returns 1, run() returns 1."""
        with patch(f"{_MODULE}.HoconValidatorCli") as mock_cli:
            mock_cli.return_value.main.return_value = 1
            self.assertEqual(ValidateCommand("agent.hocon").run(), 1)

    def test_load_error_code_two_is_normalized_to_one(self):
        """The library's exit code 2 (load error) is normalized to 1 for studio's CLI."""
        with patch(f"{_MODULE}.HoconValidatorCli") as mock_cli:
            mock_cli.return_value.main.return_value = 2
            self.assertEqual(ValidateCommand("agent.hocon").run(), 1)

    def test_unexpected_validator_error_returns_one(self):
        """An exception raised by the validator is caught and reported as exit code 1."""
        with patch(f"{_MODULE}.HoconValidatorCli") as mock_cli:
            mock_cli.return_value.main.side_effect = AttributeError("boom")
            self.assertEqual(ValidateCommand("agent.hocon").run(), 1)

    def test_builds_argv_from_all_options(self):
        """All command options are marshaled into the argv passed to HoconValidatorCli."""
        argv = self._run_capturing_argv(
            ValidateCommand(
                "agent.hocon",
                verbose=True,
                external_agents="/a,/b",
                mcp_servers="https://mcp.example.com",
                registry_dir="/reg",
            )
        )
        self.assertEqual(argv[1], "agent.hocon")
        self.assertIn("--verbose", argv)
        self.assertEqual(self._external_agents_arg(argv), "/a,/b")
        self.assertIn("--mcp-servers", argv)
        self.assertIn("https://mcp.example.com", argv)
        self.assertIn("--registry-dir", argv)
        self.assertIn("/reg", argv)

    def test_only_derived_registry_dir_added_when_no_flags_set(self):
        """With no options and nothing discovered, only the file path and the derived registry dir are passed."""
        argv = self._run_capturing_argv(ValidateCommand("agent.hocon"))
        self.assertEqual(argv, ["hocon_validator_cli", "agent.hocon", "--registry-dir", os.getcwd()])

    def test_sys_argv_restored_after_success(self):
        """sys.argv is restored after a normal run."""
        before = list(sys.argv)
        with patch(f"{_MODULE}.HoconValidatorCli") as mock_cli:
            mock_cli.return_value.main.return_value = 0
            ValidateCommand("agent.hocon").run()
        self.assertEqual(sys.argv, before)

    def test_sys_argv_restored_after_exception(self):
        """sys.argv is restored even when the validator raises."""
        before = list(sys.argv)
        with patch(f"{_MODULE}.HoconValidatorCli") as mock_cli:
            mock_cli.return_value.main.side_effect = RuntimeError("boom")
            ValidateCommand("agent.hocon").run()
        self.assertEqual(sys.argv, before)

    def _run_with_class_check(self, command: ValidateCommand) -> tuple[int, str]:
        """
        Run the command with a valid structure, so the class check runs.

        :param command: The command to run
        :return: The exit code and what the command printed
        """
        stdout: io.StringIO = io.StringIO()
        with patch(f"{_MODULE}.HoconValidatorCli") as mock_cli, patch("sys.stdout", stdout):
            mock_cli.return_value.main.return_value = 0
            exit_code: int = command.run()
        return exit_code, stdout.getvalue()

    def _make_project_dir(self) -> str:
        """
        Create an empty project folder that is removed when the test ends.

        :return: The folder's path
        """
        project_dir: str = tempfile.mkdtemp(prefix="validate_project_")
        self.addCleanup(shutil.rmtree, project_dir, True)
        return project_dir

    def _enter_project_dir(self) -> str:
        """
        Create an empty project folder, and make it the current directory until the test ends.

        :return: The folder's path
        """
        project_dir: str = self._make_project_dir()
        # Cleanups run last first, so the test leaves the folder before it is removed.
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(project_dir)
        return project_dir

    def _link(self, link: Path, target: Path) -> None:
        """
        Make a symlink to a folder, or skip the test where symlinks cannot be made.

        :param link: The symlink to make
        :param target: The folder it points at
        """
        try:
            link.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"Symlinks cannot be made here: {error}")

    @staticmethod
    def _record_environment(seen: dict[str, Any]) -> list[str]:
        """
        Stand in for the class check, and record how the process was set up for it.

        :param seen: Where to record sys.path[0], AGENT_TOOL_PATH, PYTHONPATH and AGENT_TOOL_PATH_ONLY
        :return: No errors
        """
        seen["path_first"] = sys.path[0]
        seen["agent_tool_path"] = os.environ.get("AGENT_TOOL_PATH")
        seen["pythonpath"] = os.environ.get("PYTHONPATH")
        seen["agent_tool_path_only"] = os.environ.get("AGENT_TOOL_PATH_ONLY")
        return []

    def test_class_check_failures_return_one_and_are_listed(self) -> None:
        """
        Classes that cannot be loaded make the command fail, and each one is listed, numbered.
        """
        self.mock_checker.return_value.check.return_value = ["first error", "second error"]

        exit_code, stdout = self._run_with_class_check(ValidateCommand("agent.hocon"))

        self.assertEqual(exit_code, 1)
        self.assertIn("Class check failed with 2 error(s):\n\n  1. first error\n  2. second error\n", stdout)

    def test_class_check_error_lines_go_under_their_number(self) -> None:
        """
        A full error from --verbose has several lines, which are printed under its number.
        """
        self.mock_checker.return_value.check.return_value = ["first line\nsecond line"]

        exit_code, stdout = self._run_with_class_check(ValidateCommand("agent.hocon"))

        self.assertEqual(exit_code, 1)
        self.assertIn("  1. first line\n     second line\n", stdout)

    def test_class_checker_gets_the_file_the_manifests_and_verbose(self) -> None:
        """
        The checker is given the network file, the manifest files and the verbose setting.
        """
        manifest_file: str = os.path.join(os.getcwd(), "registries", "manifest.hocon")

        self._run_with_class_check(ValidateCommand("agent.hocon", verbose=True))

        self.mock_checker.assert_called_once_with("agent.hocon", [manifest_file], verbose=True)

    def test_class_check_pass_prints_how_many_classes_loaded(self) -> None:
        """
        When every class loads, the command passes and says how many class references it checked.
        """
        self.mock_checker.return_value.get_checked_count.return_value = 3

        exit_code, stdout = self._run_with_class_check(ValidateCommand("agent.hocon"))

        self.assertEqual(exit_code, 0)
        self.assertIn("Class check passed: 3 class reference(s) loaded.", stdout)

    def test_class_check_skip_is_reported_and_passes(self) -> None:
        """
        A file outside the folder of every manifest is not checked, and the command says so and passes.
        """
        self.mock_checker.return_value.check.return_value = None

        exit_code, stdout = self._run_with_class_check(ValidateCommand("agent.hocon"))

        self.assertEqual(exit_code, 0)
        self.assertIn("Class check skipped: 'agent.hocon' is not inside the folder of any manifest", stdout)

    def test_class_check_is_skipped_outside_the_project_root(self) -> None:
        """
        From a folder other than the project root, the check would not use the project's .env, so it is
        skipped, and the command says so and passes.
        """
        project_dir: str = self._make_project_dir()

        exit_code, stdout = self._run_with_class_check(ValidateCommand("agent.hocon", registry_dir=project_dir))

        self.assertEqual(exit_code, 0)
        self.assertIn(f"Class check skipped: the current directory is not the project root '{project_dir}'.", stdout)
        self.mock_checker.assert_not_called()

    def test_class_check_is_skipped_for_another_projects_manifest(self) -> None:
        """
        A manifest given with --manifest or AGENT_MANIFEST_FILE belongs to the project that holds its
        registries folder, so the check is skipped from any other folder.
        """
        manifest_file: str = os.path.join(self._make_project_dir(), "registries", "manifest.hocon")

        flag_exit_code, flag_stdout = self._run_with_class_check(
            ValidateCommand("agent.hocon", manifest=manifest_file)
        )
        os.environ["AGENT_MANIFEST_FILE"] = manifest_file
        env_exit_code, env_stdout = self._run_with_class_check(ValidateCommand("agent.hocon"))

        self.assertEqual(flag_exit_code, 0)
        self.assertIn("Class check skipped: the current directory is not the project root", flag_stdout)
        self.assertEqual(env_exit_code, 0)
        self.assertIn("Class check skipped: the current directory is not the project root", env_stdout)
        self.mock_checker.assert_not_called()

    def test_registry_dir_does_not_make_another_folder_the_project_root(self) -> None:
        """
        --registry-dir only says where includes are found. It cannot make the current folder the root of
        another project, whose .env the check would then miss.
        """
        self._enter_project_dir()
        manifest_file: str = os.path.join(self._make_project_dir(), "registries", "manifest.hocon")

        exit_code, stdout = self._run_with_class_check(
            ValidateCommand("agent.hocon", registry_dir=".", manifest=manifest_file)
        )

        self.assertEqual(exit_code, 0)
        self.assertIn("Class check skipped: the current directory is not the project root", stdout)
        self.mock_checker.assert_not_called()

    def test_class_check_is_skipped_for_a_manifest_outside_a_registries_folder(self) -> None:
        """
        A manifest that is not in a registries folder has no project root, so the check is skipped.
        """
        self._enter_project_dir()

        exit_code, stdout = self._run_with_class_check(ValidateCommand("agent.hocon", manifest="scratch.hocon"))

        self.assertEqual(exit_code, 0)
        self.assertIn("Class check skipped: the manifest 'scratch.hocon' is not in a registries folder", stdout)
        self.mock_checker.assert_not_called()

    def test_project_root_given_through_a_symlink_is_the_current_directory(self) -> None:
        """
        A manifest path that reaches the project through a symlink still names the current directory as
        the project root, so the check runs.
        """
        project_dir: str = self._enter_project_dir()
        alias_dir: Path = Path(self._make_project_dir()) / "project_alias"
        self._link(alias_dir, Path(project_dir))

        self._run_with_class_check(
            ValidateCommand("agent.hocon", manifest=str(alias_dir / "registries" / "manifest.hocon"))
        )

        self.mock_checker.return_value.check.assert_called_once()

    def test_class_check_does_not_run_when_the_structure_is_invalid(self) -> None:
        """
        An invalid structure fails the command before any class is loaded.
        """
        with patch(f"{_MODULE}.HoconValidatorCli") as mock_cli:
            mock_cli.return_value.main.return_value = 1
            exit_code: int = ValidateCommand("agent.hocon").run()

        self.assertEqual(exit_code, 1)
        self.mock_checker.assert_not_called()

    def test_class_check_runs_with_the_project_set_up_like_the_server(self) -> None:
        """
        During the check, the project root is first on sys.path and in PYTHONPATH, and AGENT_TOOL_PATH is
        the project's coded_tools folder. Afterwards sys.path and the environment are as before.
        """
        project_dir: str = self._enter_project_dir()
        os.environ.pop("AGENT_TOOL_PATH", None)
        os.environ.pop("PYTHONPATH", None)
        seen: dict[str, Any] = {}
        self.mock_checker.return_value.check.side_effect = partial(self._record_environment, seen)
        path_before: list[str] = list(sys.path)

        self._run_with_class_check(ValidateCommand("agent.hocon", registry_dir=project_dir))

        root: str = str(Path(project_dir).resolve())
        self.assertEqual(seen.get("path_first"), root)
        self.assertEqual(seen.get("agent_tool_path"), str(Path(root) / "coded_tools"))
        self.assertEqual(seen.get("pythonpath"), root)
        self.assertEqual(sys.path, path_before)
        self.assertIsNone(os.environ.get("AGENT_TOOL_PATH"))
        self.assertIsNone(os.environ.get("PYTHONPATH"))

    def test_class_check_keeps_the_agent_tool_path_the_user_set(self) -> None:
        """
        An AGENT_TOOL_PATH the user set is used for the check and left as it was.
        """
        os.environ["AGENT_TOOL_PATH"] = "my_tools/"
        seen: dict[str, Any] = {}
        self.mock_checker.return_value.check.side_effect = partial(self._record_environment, seen)

        self._run_with_class_check(ValidateCommand("agent.hocon", registry_dir=self._enter_project_dir()))

        self.assertEqual(seen.get("agent_tool_path"), "my_tools/")
        self.assertEqual(os.environ.get("AGENT_TOOL_PATH"), "my_tools/")

    def test_class_check_keeps_agent_tool_path_only(self) -> None:
        """
        AGENT_TOOL_PATH_ONLY stays as the user set it, during the check and after it.
        """
        self._enter_project_dir()
        os.environ["AGENT_TOOL_PATH_ONLY"] = "true"
        seen: dict[str, Any] = {}
        self.mock_checker.return_value.check.side_effect = partial(self._record_environment, seen)

        self._run_with_class_check(ValidateCommand("agent.hocon"))

        self.assertEqual(seen.get("agent_tool_path_only"), "true")
        self.assertEqual(os.environ.get("AGENT_TOOL_PATH_ONLY"), "true")

    def test_sys_path_restored_when_the_class_check_raises(self) -> None:
        """
        A class check that raises is reported as exit code 1, and sys.path is put back.
        """
        self.mock_checker.return_value.check.side_effect = RuntimeError("boom")
        path_before: list[str] = list(sys.path)

        with patch("sys.stderr", io.StringIO()):
            exit_code, _ = self._run_with_class_check(ValidateCommand("agent.hocon"))

        self.assertEqual(exit_code, 1)
        self.assertEqual(sys.path, path_before)


class TestValidateCommandManifestDiscovery(TestCase):
    """Tests for how ValidateCommand seeds --external-agents from the composed manifest(s)."""

    def setUp(self) -> None:
        """
        Patch the lister and the class checker and isolate the environment, as in TestValidateCommandRun.
        """
        lister_patcher = patch(f"{_MODULE}.ServedNetworkLister")
        self.mock_lister = lister_patcher.start()
        self.addCleanup(lister_patcher.stop)
        self.mock_lister.return_value.list_names.return_value = []
        self.mock_lister.return_value.warnings = []

        checker_patcher = patch(f"{_MODULE}.NetworkClassChecker")
        self.mock_checker = checker_patcher.start()
        self.addCleanup(checker_patcher.stop)
        self.mock_checker.return_value.check.return_value = []
        self.mock_checker.return_value.get_checked_count.return_value = 0

        env_patcher = patch.dict(os.environ)
        env_patcher.start()
        self.addCleanup(env_patcher.stop)
        os.environ.pop("AGENT_MANIFEST_FILE", None)

    def _run_capturing_argv(self, command: ValidateCommand, stream_name: str = None) -> tuple:
        """Run the command against a fake HoconValidatorCli; return (exit_code, argv, captured stream text)."""
        captured = {}

        def fake_main():
            captured["argv"] = list(sys.argv)
            return 0

        stream = io.StringIO()
        with patch(f"{_MODULE}.HoconValidatorCli") as mock_cli:
            mock_cli.return_value.main.side_effect = fake_main
            if stream_name:
                with patch(f"sys.{stream_name}", stream):
                    exit_code = command.run()
            else:
                exit_code = command.run()
        return exit_code, captured.get("argv"), stream.getvalue()

    def test_discovered_names_are_passed_as_external_agents(self):
        """Names discovered from the manifest are forwarded as --external-agents."""
        self.mock_lister.return_value.list_names.return_value = ["/a", "/tools/b"]
        _, argv, _ = self._run_capturing_argv(ValidateCommand("agent.hocon"))
        self.assertEqual(argv[argv.index("--external-agents") + 1], "/a,/tools/b")

    def test_explicit_names_come_first_and_duplicates_dropped(self):
        """Explicit --external-agents precede discovered names, and repeats are removed."""
        self.mock_lister.return_value.list_names.return_value = ["/a", "/b"]
        _, argv, _ = self._run_capturing_argv(ValidateCommand("agent.hocon", external_agents="/b,/c"))
        self.assertEqual(argv[argv.index("--external-agents") + 1], "/b,/c,/a")

    def test_manifest_read_error_warns_and_continues(self):
        """A ManifestReadError is reported on stderr and validation still runs without discovered names."""
        self.mock_lister.return_value.list_names.side_effect = ManifestReadError(
            "include base directory '/reg' does not exist"
        )
        exit_code, argv, stderr = self._run_capturing_argv(ValidateCommand("agent.hocon"), stream_name="stderr")
        self.assertEqual(exit_code, 0)
        self.assertIn(
            "Warning: include base directory '/reg' does not exist; "
            "no external agents will be discovered from the manifest.",
            stderr,
        )
        self.assertNotIn("--external-agents", argv)

    def test_lister_warnings_are_printed(self):
        """Each manifest the lister skipped is reported on stderr while the discovered names are still used."""
        self.mock_lister.return_value.list_names.return_value = ["/a"]
        self.mock_lister.return_value.warnings = ["manifest file '/m' not found"]
        _, argv, stderr = self._run_capturing_argv(ValidateCommand("agent.hocon"), stream_name="stderr")
        self.assertIn(
            "Warning: manifest file '/m' not found; "
            "networks from this manifest will not be accepted as external agents.",
            stderr,
        )
        self.assertEqual(argv[argv.index("--external-agents") + 1], "/a")

    def test_manifest_option_takes_precedence_over_env(self):
        """--manifest wins over AGENT_MANIFEST_FILE."""
        os.environ["AGENT_MANIFEST_FILE"] = "/env/registries/manifest.hocon"
        self._run_capturing_argv(ValidateCommand("agent.hocon", manifest="/opt/registries/manifest.hocon"))
        self.mock_lister.assert_called_once_with(["/opt/registries/manifest.hocon"], base_dir=None)

    def test_env_manifest_pathsep_list_is_composed_in_one_lister(self):
        """An os.pathsep-separated AGENT_MANIFEST_FILE is handed to a single lister, in order."""
        first = "/p1/registries/manifest.hocon"
        second = "/p2/registries/manifest.hocon"
        os.environ["AGENT_MANIFEST_FILE"] = os.pathsep.join([first, second])
        self._run_capturing_argv(ValidateCommand("agent.hocon"))
        self.mock_lister.assert_called_once_with([first, second], base_dir=None)

    def test_default_manifest_is_under_registry_dir(self):
        """Without --manifest or the env var, the manifest is <registry_dir>/registries/manifest.hocon."""
        self._run_capturing_argv(ValidateCommand("agent.hocon", registry_dir="/reg"))
        expected = os.path.join("/reg", "registries", "manifest.hocon")
        self.mock_lister.assert_called_once_with([expected], base_dir="/reg")

    def test_default_manifest_is_under_cwd_without_registry_dir(self):
        """Without --registry-dir either, the manifest is <cwd>/registries/manifest.hocon."""
        self._run_capturing_argv(ValidateCommand("agent.hocon"))
        expected = os.path.join(os.getcwd(), "registries", "manifest.hocon")
        self.mock_lister.assert_called_once_with([expected], base_dir=None)

    def test_verbose_prints_discovery_summary(self):
        """--verbose reports how many names were taken from which manifest(s)."""
        self.mock_lister.return_value.list_names.return_value = ["/a", "/b"]
        command = ValidateCommand("agent.hocon", verbose=True, manifest="/m/registries/manifest.hocon")
        _, _, stdout = self._run_capturing_argv(command, stream_name="stdout")
        self.assertIn("Using 2 external agent name(s) from manifest(s): /m/registries/manifest.hocon", stdout)

    def test_discovery_exception_is_caught_by_run_guard(self):
        """An unexpected error during discovery is reported as exit code 1 and sys.argv is restored."""
        self.mock_lister.return_value.list_names.side_effect = RuntimeError("boom")
        before = list(sys.argv)
        with patch(f"{_MODULE}.HoconValidatorCli") as mock_cli, patch("sys.stderr", io.StringIO()):
            mock_cli.return_value.main.return_value = 0
            self.assertEqual(ValidateCommand("agent.hocon").run(), 1)
        self.assertEqual(sys.argv, before)


class TestValidateCommandRegistryDir(TestCase):
    """Tests for the --registry-dir value handed to HoconValidatorCli.

    It is always passed: left unset, the library derives its default from the raw AGENT_MANIFEST_FILE
    string, which is a nonexistent path for an os.pathsep list (neuro-san issue #1370).
    """

    def setUp(self) -> None:
        """
        Patch the lister and the class checker and isolate the environment, as in TestValidateCommandRun.
        """
        lister_patcher = patch(f"{_MODULE}.ServedNetworkLister")
        self.mock_lister = lister_patcher.start()
        self.addCleanup(lister_patcher.stop)
        self.mock_lister.return_value.list_names.return_value = []
        self.mock_lister.return_value.warnings = []

        checker_patcher = patch(f"{_MODULE}.NetworkClassChecker")
        self.mock_checker = checker_patcher.start()
        self.addCleanup(checker_patcher.stop)
        self.mock_checker.return_value.check.return_value = []
        self.mock_checker.return_value.get_checked_count.return_value = 0

        env_patcher = patch.dict(os.environ)
        env_patcher.start()
        self.addCleanup(env_patcher.stop)
        os.environ.pop("AGENT_MANIFEST_FILE", None)

    @staticmethod
    def _registry_dir_arg(command: ValidateCommand) -> str:
        """Run the command against a fake HoconValidatorCli and return the --registry-dir value it saw."""
        captured = {}

        def fake_main():
            captured["argv"] = list(sys.argv)
            return 0

        with patch(f"{_MODULE}.HoconValidatorCli") as mock_cli:
            mock_cli.return_value.main.side_effect = fake_main
            command.run()
        argv = captured["argv"]
        return argv[argv.index("--registry-dir") + 1]

    def test_explicit_registry_dir_is_forwarded(self):
        """--registry-dir given by the user is passed through unchanged."""
        self.assertEqual(self._registry_dir_arg(ValidateCommand("agent.hocon", registry_dir="/reg")), "/reg")

    def test_pathsep_list_uses_first_manifest_project_root(self):
        """A two-entry AGENT_MANIFEST_FILE yields the first manifest's project root, not the library's bogus path."""
        os.environ["AGENT_MANIFEST_FILE"] = os.pathsep.join(
            ["/p/registries/manifest.hocon", "/q/registries/overlay.hocon"]
        )
        self.assertEqual(self._registry_dir_arg(ValidateCommand("agent.hocon")), "/p")

    def test_single_env_manifest_uses_its_project_root(self):
        """A single AGENT_MANIFEST_FILE yields the same directory the library would derive itself."""
        os.environ["AGENT_MANIFEST_FILE"] = "/p/registries/manifest.hocon"
        self.assertEqual(self._registry_dir_arg(ValidateCommand("agent.hocon")), "/p")

    def test_manifest_option_uses_its_project_root(self):
        """--manifest inside a registries folder yields that folder's parent."""
        command = ValidateCommand("agent.hocon", manifest="/opt/registries/manifest.hocon")
        self.assertEqual(self._registry_dir_arg(command), "/opt")

    def test_manifest_outside_registries_folder_falls_back_to_cwd(self):
        """A scratch --manifest has no project root, so the current directory is used, not its grandparent."""
        command = ValidateCommand("agent.hocon", manifest="/tmp/scratch.hocon")
        self.assertEqual(self._registry_dir_arg(command), os.getcwd())

    def test_default_manifest_yields_cwd(self):
        """The default <cwd>/registries/manifest.hocon resolves to the current directory."""
        self.assertEqual(self._registry_dir_arg(ValidateCommand("agent.hocon")), os.getcwd())
