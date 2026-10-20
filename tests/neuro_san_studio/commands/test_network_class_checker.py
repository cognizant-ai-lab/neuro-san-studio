# Copyright © 2026 Cognizant Technology Solutions Corp, www.cognizant.com.
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

import importlib
import json
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from neuro_san_studio.commands.network_class_checker import NetworkClassChecker

# Module sources for the test package. Each holds one class, named where {class_name} stands.
CODED_TOOL_SOURCE: str = (
    "from neuro_san.interfaces.coded_tool import CodedTool\n"
    "\n"
    "\n"
    "class {class_name}(CodedTool):\n"
    '    """A coded tool for the class check tests."""\n'
)
PLAIN_CLASS_SOURCE: str = 'class {class_name}:\n    """A class that is not a coded tool."""\n'
MIDDLEWARE_SOURCE: str = (
    "from langchain.agents.middleware.types import AgentMiddleware\n"
    "\n"
    "\n"
    "class {class_name}(AgentMiddleware):\n"
    '    """A middleware for the class check tests."""\n'
)
# A logger the tests use to show that logging works again after a check.
TEST_LOGGER: str = "network_class_checker_test"


class TestNetworkClassChecker(TestCase):  # pylint: disable=too-many-public-methods
    """
    Tests for NetworkClassChecker.

    Each test builds a project in a temp folder: a registries folder for the network files, and a package of
    coded tools and middleware that AGENT_TOOL_PATH points at. The package has a name of its own, so its
    modules never shadow the real coded_tools package for later tests.
    """

    def setUp(self) -> None:
        """
        Create the project, and set the process up the way the server's is: the project first on sys.path
        and in PYTHONPATH, AGENT_TOOL_PATH pointing at the package, and AGENT_TOOL_PATH_ONLY unset.
        """
        self.project_dir: Path = Path(tempfile.mkdtemp(prefix="class_checker_")).resolve()
        self.addCleanup(shutil.rmtree, str(self.project_dir), True)
        self.package: str = f"checker_tools_{uuid4().hex}"
        self.registries_dir: Path = self.project_dir / "registries"
        self.manifest_file: str = str(self.registries_dir / "manifest.hocon")
        self._write(self.registries_dir / "manifest.hocon", "{}\n")
        self._write_module("net/lookup_tool.py", CODED_TOOL_SOURCE, "LookupTool")
        self._write_module("group/sub_net/local_tool.py", CODED_TOOL_SOURCE, "LocalTool")
        self._write_module("not_coded.py", PLAIN_CLASS_SOURCE, "NotCoded")
        self._write_module("fake_middleware.py", MIDDLEWARE_SOURCE, "FakeMiddleware")

        environment: Any = patch.dict(
            os.environ,
            {
                "AGENT_TOOL_PATH": str(self.project_dir / self.package),
                "PYTHONPATH": str(self.project_dir),
            },
        )
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop("AGENT_TOOL_PATH_ONLY", None)
        sys.path.insert(0, str(self.project_dir))
        self.addCleanup(sys.path.remove, str(self.project_dir))
        self.addCleanup(self._forget_modules, self.package)
        importlib.invalidate_caches()

    @staticmethod
    def _write(path: Path, text: str) -> None:
        """
        Write a text file, creating its folder first.

        :param path: The file to write
        :param text: The file's contents
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _write_module(self, relative_path: str, source: str, class_name: str) -> None:
        """
        Write a module into the test package, with an __init__.py in each of its folders.

        :param relative_path: The module's path under the package folder
        :param source: The module's source, with {class_name} where the class name goes
        :param class_name: The name of the class the module defines
        """
        module_path: Path = self.project_dir / self.package / relative_path
        folder: Path = module_path.parent
        while folder != self.project_dir:
            if not (folder / "__init__.py").exists():
                self._write(folder / "__init__.py", "")
            folder = folder.parent
        self._write(module_path, source.format(class_name=class_name))

    def _write_network(self, relative_path: str, tools: list[dict[str, Any]]) -> str:
        """
        Write a network file into the registries folder.

        :param relative_path: The file's path under the registries folder
        :param tools: The network's agent specs, front man first
        :return: The path of the file
        """
        network_path: Path = self.registries_dir / relative_path
        # JSON is valid HOCON.
        self._write(network_path, json.dumps({"tools": tools}, indent=4))
        return str(network_path)

    def _link(self, link: Path, target: Path) -> None:
        """
        Make a symlink, or skip the test where symlinks cannot be made.

        :param link: The symlink to make
        :param target: The file or folder it points at
        """
        try:
            link.symlink_to(target, target_is_directory=target.is_dir())
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"Symlinks cannot be made here: {error}")

    @staticmethod
    def _forget_modules(package: str) -> None:
        """
        Remove the test package's modules from sys.modules, so no later test can import them.

        :param package: The name of the test package
        """
        names: list[str] = []
        for name in sys.modules:
            if name == package or name.startswith(f"{package}."):
                names.append(name)
        for name in names:
            sys.modules.pop(name, None)

    @staticmethod
    def _front_man(tools: list[str], middleware: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Build the spec of a front man that calls the given tools and loads the given middleware.

        :param tools: The names of the agents the front man calls
        :param middleware: The front man's middleware entries
        :return: The front man's spec
        """
        return {
            "name": "front",
            "function": {"description": "Answers questions."},
            "instructions": "Answer the question.",
            "tools": tools,
            "middleware": middleware,
        }

    @staticmethod
    def _coded_tool(name: str, class_reference: str) -> dict[str, Any]:
        """
        Build the spec of a coded tool.

        :param name: The coded tool's name
        :param class_reference: The class the coded tool names
        :return: The coded tool's spec
        """
        return {
            "name": name,
            "function": {"description": "Looks a value up."},
            "class": class_reference,
        }

    def _middleware(self, module_and_class: str) -> dict[str, Any]:
        """
        Build a middleware entry for a class in the test package.

        :param module_and_class: The class's module and name under the test package
        :return: The middleware entry
        """
        return {"class": f"{self.package}.{module_and_class}"}

    def _check(self, network_path: str) -> list[str] | None:
        """
        Run the check on a network file, with the project's manifest.

        :param network_path: The network file to check
        :return: What the check returned
        """
        return NetworkClassChecker(network_path, [self.manifest_file]).check()

    def test_every_class_loads(self) -> None:
        """
        A network whose coded tool and middleware classes all exist passes, and both references are counted.
        """
        network_path: str = self._write_network(
            "net.hocon",
            [
                self._front_man(["lookup"], [self._middleware("fake_middleware.FakeMiddleware")]),
                self._coded_tool("lookup", "lookup_tool.LookupTool"),
            ],
        )
        checker: NetworkClassChecker = NetworkClassChecker(network_path, [self.manifest_file])

        errors: list[str] | None = checker.check()

        self.assertEqual(errors, [])
        self.assertEqual(checker.get_checked_count(), 2)

    def test_reports_a_coded_tool_whose_module_is_missing(self) -> None:
        """
        A coded tool that names a module that does not exist is reported with the agent, class and module.
        """
        network_path: str = self._write_network(
            "net.hocon",
            [
                self._front_man(["lookup"], []),
                self._coded_tool("lookup", "missing_tool.LookupTool"),
            ],
        )

        errors: list[str] | None = self._check(network_path)

        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith("Agent 'lookup': "))
        self.assertIn('Could not find class "LookupTool"', errors[0])
        self.assertIn('in module "missing_tool"', errors[0])
        self.assertNotIn("AGENT_TOOL_PATH_ONLY", errors[0])

    def test_reports_a_class_that_is_not_a_coded_tool(self) -> None:
        """
        A coded tool whose class loads but is not a CodedTool is reported.
        """
        network_path: str = self._write_network(
            "net.hocon",
            [
                self._front_man(["lookup"], []),
                self._coded_tool("lookup", "not_coded.NotCoded"),
            ],
        )

        errors: list[str] | None = self._check(network_path)

        self.assertEqual(errors, ["Agent 'lookup': class 'not_coded.NotCoded' is not a CodedTool."])

    def test_reports_a_middleware_class_that_cannot_be_found(self) -> None:
        """
        A middleware class in a module that does not exist is reported with the agent that loads it.
        """
        network_path: str = self._write_network(
            "net.hocon",
            [self._front_man([], [self._middleware("no_such.NoSuchMiddleware")])],
        )

        errors: list[str] | None = self._check(network_path)

        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith("Agent 'front': "))
        self.assertIn("NoSuchMiddleware", errors[0])
        self.assertIn("not found", errors[0])

    def test_reports_a_middleware_class_that_is_not_middleware(self) -> None:
        """
        A middleware entry naming a class that is not an AgentMiddleware is reported.
        """
        network_path: str = self._write_network(
            "net.hocon",
            [self._front_man([], [self._middleware("net.lookup_tool.LookupTool")])],
        )

        errors: list[str] | None = self._check(network_path)

        self.assertEqual(len(errors), 1)
        self.assertIn("must be a subclass of AgentMiddleware", errors[0])

    def test_short_reference_is_found_in_the_network_folder(self) -> None:
        """
        A network in a subfolder gets the server's name for it, so a short reference is found in the
        network's own folder of the package.
        """
        network_path: str = self._write_network(
            "group/sub_net.hocon",
            [
                self._front_man(["local"], []),
                self._coded_tool("local", "local_tool.LocalTool"),
            ],
        )
        checker: NetworkClassChecker = NetworkClassChecker(network_path, [self.manifest_file])

        errors: list[str] | None = checker.check()

        self.assertEqual(errors, [])
        self.assertEqual(checker.find_network_location(), (self.registries_dir, "group/sub_net.hocon"))

    def test_fully_qualified_reference_follows_agent_tool_path_only(self) -> None:
        """
        With AGENT_TOOL_PATH_ONLY on, a fully-qualified reference fails without its module being imported,
        as on the server, and the report says how to name it. With the flag off, the same reference loads.
        """
        network_path: str = self._write_network(
            "net.hocon",
            [
                self._front_man(["lookup"], []),
                self._coded_tool("lookup", f"{self.package}.net.lookup_tool.LookupTool"),
            ],
        )

        with patch.dict(os.environ, {"AGENT_TOOL_PATH_ONLY": "true"}):
            strict_errors: list[str] | None = self._check(network_path)
        # The lookup may import the packages above the module, but never the module itself.
        imported_in_strict_mode: bool = f"{self.package}.net.lookup_tool" in sys.modules
        default_errors: list[str] | None = self._check(network_path)

        self.assertEqual(len(strict_errors), 1)
        self.assertIn("AGENT_TOOL_PATH_ONLY is on", strict_errors[0])
        self.assertIn("name its module relative to AGENT_TOOL_PATH", strict_errors[0])
        self.assertFalse(imported_in_strict_mode)
        self.assertEqual(default_errors, [])

    def test_short_reference_loads_with_agent_tool_path_only(self) -> None:
        """
        AGENT_TOOL_PATH_ONLY only stops references that go around AGENT_TOOL_PATH, so a short reference
        still loads.
        """
        network_path: str = self._write_network(
            "net.hocon",
            [
                self._front_man(["lookup"], []),
                self._coded_tool("lookup", "lookup_tool.LookupTool"),
            ],
        )

        with patch.dict(os.environ, {"AGENT_TOOL_PATH_ONLY": "true"}):
            errors: list[str] | None = self._check(network_path)

        self.assertEqual(errors, [])

    def test_coded_tool_that_allows_reservations_is_checked(self) -> None:
        """
        A coded tool that allows reservations is checked like any other: its class loads, or is reported.
        """
        found_tool: dict[str, Any] = self._coded_tool("found", "lookup_tool.LookupTool")
        found_tool["allow"] = {"reservations": True}
        missing_tool: dict[str, Any] = self._coded_tool("missing", "missing_tool.Copyist")
        missing_tool["allow"] = {"reservations": True}
        network_path: str = self._write_network(
            "net.hocon",
            [self._front_man(["found", "missing"], []), found_tool, missing_tool],
        )
        checker: NetworkClassChecker = NetworkClassChecker(network_path, [self.manifest_file])

        errors: list[str] | None = checker.check()

        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith("Agent 'missing': "))
        self.assertEqual(checker.get_checked_count(), 2)

    def test_only_the_classes_the_server_loads_are_checked(self) -> None:
        """
        Each kind of agent is checked for what the server loads for it: nothing for a toolbox agent, no
        middleware for a coded tool, and no class for an LLM agent. Each of those names a module that does
        not exist, so loading one would be reported.
        """
        toolbox_agent: dict[str, Any] = {
            "name": "search",
            "toolbox": "web_fetch",
            "function": {"description": "Fetches a page."},
            "class": "missing_toolbox_module.Tool",
            "middleware": [{"class": "missing_toolbox_middleware.Middleware"}],
        }
        coded_tool: dict[str, Any] = self._coded_tool("lookup", "lookup_tool.LookupTool")
        coded_tool["middleware"] = [{"class": "missing_coded_tool_middleware.Middleware"}]
        llm_agent: dict[str, Any] = {
            "name": "helper",
            "instructions": "Help with the question.",
            "class": "missing_llm_module.Agent",
        }
        network_path: str = self._write_network(
            "net.hocon",
            [self._front_man(["search", "lookup", "helper"], []), toolbox_agent, coded_tool, llm_agent],
        )
        checker: NetworkClassChecker = NetworkClassChecker(network_path, [self.manifest_file])

        errors: list[str] | None = checker.check()

        self.assertEqual(errors, [])
        self.assertEqual(checker.get_checked_count(), 1)

    def test_reports_a_coded_tool_class_that_is_not_a_string(self) -> None:
        """
        A coded tool whose class is not a string is reported, and the check goes on to the other agents.
        """
        number_tool: dict[str, Any] = self._coded_tool("number", "placeholder.Placeholder")
        number_tool["class"] = 42
        network_path: str = self._write_network(
            "net.hocon",
            [
                self._front_man(["number", "missing"], []),
                number_tool,
                self._coded_tool("missing", "missing_tool.Missing"),
            ],
        )

        errors: list[str] | None = self._check(network_path)

        self.assertEqual(len(errors), 2)
        self.assertEqual(errors[0], "Agent 'number': class must be a non-empty string, not 42.")
        self.assertTrue(errors[1].startswith("Agent 'missing': "))

    def test_reports_middleware_the_server_cannot_use(self) -> None:
        """
        Middleware that is not a list of dictionaries, and an entry whose class is not a non-empty string,
        are reported, as the server fails on them. An entry that names no class is skipped, as on the server.
        """
        front_man: dict[str, Any] = self._front_man(
            ["other", "flag"],
            [
                "not a dictionary",
                {"class": ""},
                {"class": 42},
                {"args": {"limit": 1}},
            ],
        )
        other_agent: dict[str, Any] = {
            "name": "other",
            "function": {"description": "Answers other questions."},
            "instructions": "Answer the question.",
            "middleware": {"class": f"{self.package}.fake_middleware.FakeMiddleware"},
        }
        # The server takes the length of the value, which a boolean does not have.
        flag_agent: dict[str, Any] = {
            "name": "flag",
            "function": {"description": "Answers yes or no."},
            "instructions": "Answer the question.",
            "middleware": False,
        }
        network_path: str = self._write_network("net.hocon", [front_man, other_agent, flag_agent])
        checker: NetworkClassChecker = NetworkClassChecker(network_path, [self.manifest_file])

        errors: list[str] | None = checker.check()

        self.assertEqual(
            errors,
            [
                "Agent 'front': middleware at index 0 must be a dictionary.",
                "Agent 'front': middleware at index 1 must name its class as a non-empty string, not ''.",
                "Agent 'front': middleware at index 2 must name its class as a non-empty string, not 42.",
                "Agent 'other': middleware must be a list of dictionaries.",
                "Agent 'flag': middleware must be a list of dictionaries.",
            ],
        )
        self.assertEqual(checker.get_checked_count(), 2)

    def test_empty_middleware_is_no_middleware(self) -> None:
        """
        An empty middleware value is no middleware to the server, so it passes the check.
        """
        other_agent: dict[str, Any] = {
            "name": "other",
            "function": {"description": "Answers other questions."},
            "instructions": "Answer the question.",
            "middleware": "",
        }
        front_man: dict[str, Any] = self._front_man(["other"], [])
        front_man["middleware"] = {}
        network_path: str = self._write_network("net.hocon", [front_man, other_agent])
        checker: NetworkClassChecker = NetworkClassChecker(network_path, [self.manifest_file])

        errors: list[str] | None = checker.check()

        self.assertEqual(errors, [])
        self.assertEqual(checker.get_checked_count(), 0)

    def test_coded_tool_is_told_apart_by_the_keys_being_set(self) -> None:
        """
        As on the server, an agent is a coded tool when its function and class are set, even when they are
        empty, so both of these are checked and reported.
        """
        empty_function: dict[str, Any] = self._coded_tool("empty_function", "missing_tool.LookupTool")
        empty_function["function"] = {}
        network_path: str = self._write_network(
            "net.hocon",
            [
                self._front_man(["empty_function", "empty_class"], []),
                empty_function,
                self._coded_tool("empty_class", ""),
            ],
        )
        checker: NetworkClassChecker = NetworkClassChecker(network_path, [self.manifest_file])

        errors: list[str] | None = checker.check()

        self.assertEqual(len(errors), 2)
        self.assertTrue(errors[0].startswith("Agent 'empty_function': Could not find class \"LookupTool\""))
        self.assertEqual(errors[1], "Agent 'empty_class': class must be a non-empty string, not ''.")
        self.assertEqual(checker.get_checked_count(), 2)

    def test_one_failure_does_not_hide_the_others(self) -> None:
        """
        Every class that cannot be loaded is reported, not only the first.
        """
        middleware: list[dict[str, Any]] = [
            self._middleware("no_such.FirstMiddleware"),
            self._middleware("no_such.SecondMiddleware"),
        ]
        network_path: str = self._write_network(
            "net.hocon",
            [
                self._front_man(["first", "second"], middleware),
                self._coded_tool("first", "missing_one.First"),
                self._coded_tool("second", "missing_two.Second"),
            ],
        )

        errors: list[str] | None = self._check(network_path)

        self.assertEqual(len(errors), 4)
        self.assertIn("FirstMiddleware", errors[0])
        self.assertIn("SecondMiddleware", errors[1])

    def test_file_outside_every_manifest_folder_is_not_checked(self) -> None:
        """
        A file outside the folder of every manifest has no network name, so it is not checked.
        """
        outside_path: Path = self.project_dir / "elsewhere" / "net.hocon"
        self._write(outside_path, json.dumps({"tools": [self._front_man([], [])]}))
        checker: NetworkClassChecker = NetworkClassChecker(str(outside_path), [self.manifest_file])

        self.assertIsNone(checker.find_network_location())
        self.assertIsNone(checker.check())

    def test_network_in_a_symlinked_folder_keeps_its_name(self) -> None:
        """
        A network reached through a symlinked folder under the manifest's folder is named from its path
        there, as the server names it, so its short reference is found.
        """
        shared_dir: Path = self.project_dir / "shared_networks"
        network: dict[str, Any] = {
            "tools": [
                self._front_man(["local"], []),
                self._coded_tool("local", "local_tool.LocalTool"),
            ],
        }
        self._write(shared_dir / "sub_net.hocon", json.dumps(network))
        self._link(self.registries_dir / "group", shared_dir)
        checker: NetworkClassChecker = NetworkClassChecker(
            str(self.registries_dir / "group" / "sub_net.hocon"), [self.manifest_file]
        )

        location: tuple[Path, str] | None = checker.find_network_location()
        errors: list[str] | None = checker.check()

        self.assertEqual(location, (self.registries_dir, "group/sub_net.hocon"))
        self.assertEqual(errors, [])

    def test_symlinked_manifest_file_keeps_its_folder(self) -> None:
        """
        A manifest that is a symlink to a file elsewhere serves the networks in its own folder, as on the
        server.
        """
        real_manifest: Path = self.project_dir / "shared" / "manifest.hocon"
        self._write(real_manifest, "{}\n")
        linked_manifest: Path = self.registries_dir / "linked_manifest.hocon"
        self._link(linked_manifest, real_manifest)
        network_path: str = self._write_network("net.hocon", [self._front_man([], [])])
        checker: NetworkClassChecker = NetworkClassChecker(network_path, [str(linked_manifest)])

        self.assertEqual(checker.find_network_location(), (self.registries_dir, "net.hocon"))

    def test_file_given_through_another_path_to_the_manifest_folder_is_found(self) -> None:
        """
        A file given through a symlink to the manifest's folder, as /tmp is for /private/tmp on macOS, is
        found once the paths are resolved.
        """
        alias_dir: Path = self.project_dir / "registries_alias"
        self._link(alias_dir, self.registries_dir)
        self._write_network("net.hocon", [self._front_man([], [])])
        checker: NetworkClassChecker = NetworkClassChecker(str(alias_dir / "net.hocon"), [self.manifest_file])

        self.assertEqual(checker.find_network_location(), (self.registries_dir, "net.hocon"))

    def test_manifest_given_through_another_path_to_its_folder_is_found(self) -> None:
        """
        A manifest given through a symlink to its folder is found for a file given through the real path,
        once the paths are resolved.
        """
        alias_dir: Path = self.project_dir / "registries_alias"
        self._link(alias_dir, self.registries_dir)
        network_path: str = self._write_network("net.hocon", [self._front_man([], [])])
        checker: NetworkClassChecker = NetworkClassChecker(network_path, [str(alias_dir / "manifest.hocon")])

        self.assertEqual(checker.find_network_location(), (self.registries_dir, "net.hocon"))

    def test_symlinked_file_given_through_another_path_to_its_folder_keeps_its_name(self) -> None:
        """
        A symlinked file in the manifest's folder, given through another path to that folder, is named
        from its place in the folder, as the server names it, not from the file it points at.
        """
        real_file: Path = self.project_dir / "outside" / "real.hocon"
        self._write(real_file, json.dumps({"tools": [self._front_man([], [])]}))
        self._link(self.registries_dir / "linked.hocon", real_file)
        alias_dir: Path = self.project_dir / "registries_alias"
        self._link(alias_dir, self.registries_dir)
        checker: NetworkClassChecker = NetworkClassChecker(str(alias_dir / "linked.hocon"), [self.manifest_file])

        self.assertEqual(checker.find_network_location(), (self.registries_dir, "linked.hocon"))

    def test_symlink_outside_the_manifest_folder_is_named_from_its_target(self) -> None:
        """
        A file given through a symlink outside every manifest folder that points at a file inside one is
        checked under the name of the file it points at.
        """
        self._write_network(
            "group/sub_net.hocon",
            [
                self._front_man(["local"], []),
                self._coded_tool("local", "local_tool.LocalTool"),
            ],
        )
        outside_link: Path = self.project_dir / "my_sub_net.hocon"
        self._link(outside_link, self.registries_dir / "group" / "sub_net.hocon")
        checker: NetworkClassChecker = NetworkClassChecker(str(outside_link), [self.manifest_file])

        location: tuple[Path, str] | None = checker.find_network_location()
        errors: list[str] | None = checker.check()

        self.assertEqual(location, (self.registries_dir, "group/sub_net.hocon"))
        self.assertEqual(errors, [])

    def test_network_in_a_later_manifest_folder_is_found(self) -> None:
        """
        With several manifests, a file in the folder of a later one is found there and named from it.
        """
        more_registries: Path = self.project_dir / "more_registries"
        self._write(more_registries / "manifest.hocon", "{}\n")
        other_path: Path = more_registries / "other.hocon"
        self._write(other_path, json.dumps({"tools": [self._front_man([], [])]}))
        checker: NetworkClassChecker = NetworkClassChecker(
            str(other_path), [self.manifest_file, str(more_registries / "manifest.hocon")]
        )

        self.assertEqual(checker.find_network_location(), (more_registries, "other.hocon"))

    def test_unusable_agent_tool_path_is_reported_and_middleware_still_checked(self) -> None:
        """
        When AGENT_TOOL_PATH cannot be mapped to a module path, the report says so once for all coded
        tools, and the middleware is still checked.
        """
        network_path: str = self._write_network(
            "net.hocon",
            [
                self._front_man(["lookup", "other"], [self._middleware("fake_middleware.FakeMiddleware")]),
                self._coded_tool("lookup", "lookup_tool.LookupTool"),
                self._coded_tool("other", "lookup_tool.LookupTool"),
            ],
        )
        checker: NetworkClassChecker = NetworkClassChecker(network_path, [self.manifest_file])

        # AGENT_TOOL_PATH is a folder path, which neuro-san maps to a module path through PYTHONPATH.
        with patch.dict(os.environ, {"PYTHONPATH": str(self.registries_dir)}):
            errors: list[str] | None = checker.check()

        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith("Coded tools cannot be looked up: "))
        self.assertEqual(checker.get_checked_count(), 1)

    def test_logging_works_again_after_the_check(self) -> None:
        """
        Logging is off only while the classes load, so the server's long error is not logged during the
        check, and the process logs as before once the check ends.
        """
        network_path: str = self._write_network(
            "net.hocon",
            [
                self._front_man(["lookup"], []),
                self._coded_tool("lookup", "missing_tool.LookupTool"),
            ],
        )
        with self.assertNoLogs(level="ERROR"):
            self._check(network_path)

        with self.assertLogs(TEST_LOGGER, level="ERROR") as captured:
            logging.getLogger(TEST_LOGGER).error("still logging")

        self.assertEqual(captured.output, [f"ERROR:{TEST_LOGGER}:still logging"])

    def test_logging_the_caller_turned_off_stays_off(self) -> None:
        """
        The check puts back the logging level it found, so logging the caller turned off stays off.
        """
        network_path: str = self._write_network(
            "net.hocon",
            [
                self._front_man(["lookup"], []),
                self._coded_tool("lookup", "missing_tool.LookupTool"),
            ],
        )
        # The cleanup puts back the level the test started with.
        self.addCleanup(logging.disable, logging.root.manager.disable)
        logging.disable(logging.CRITICAL)

        self._check(network_path)

        self.assertFalse(logging.getLogger(TEST_LOGGER).isEnabledFor(logging.CRITICAL))

    def test_verbose_reports_the_full_error(self) -> None:
        """
        With verbose on, the report has the server's full error for a class, with its hints.
        """
        network_path: str = self._write_network(
            "net.hocon",
            [
                self._front_man(["lookup"], []),
                self._coded_tool("lookup", "missing_tool.LookupTool"),
            ],
        )

        errors: list[str] | None = NetworkClassChecker(network_path, [self.manifest_file], verbose=True).check()

        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith("Agent 'lookup': Could not find class \"LookupTool\"\n"))
        self.assertIn('for the agent called "lookup"', errors[0])
        self.assertIn("Check these things:", errors[0])
