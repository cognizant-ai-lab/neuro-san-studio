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

import errno
import os
from pathlib import Path

from coded_tools.agent_network_editor.and_logger import AndLogger
from middleware.agent_network_designer.persistence.file_system_agent_network_persistor import DEFAULT_REGISTRIES_DIR
from middleware.agent_network_designer.persistence.file_system_agent_network_persistor import (
    FileSystemAgentNetworkPersistor,
)

CONFIG_FILE_UNAVAILABLE_MESSAGE: str = (
    "Error: Agent network config file is unavailable or not permitted. "
    "It must be an existing .hocon or .json file inside the registries directory."
)


class AgentNetworkConfigPathResolver:
    """
    Resolves the agent network config file a client names in sly_data to a canonical path inside a
    registry root (issue #1459), for AgentNetworkDefinitionMiddleware.

    Not thread-safe: resolve() records the last error on the instance, so use one instance per call.
    """

    def __init__(self, logger: AndLogger) -> None:
        """
        Constructor.

        :param logger: The caller's logger, so resolution diagnostics carry the caller's logger name
        """
        self.logger: AndLogger = logger
        self.error_message: str = ""

    def get_error_message(self) -> str:
        """
        :return: The client-facing message from the last failed resolve(), or "" if none has failed
        """
        return self.error_message

    def resolve(self, network_hocon_file: str | None) -> str | None:
        """
        Validate and resolve a user-supplied HOCON file reference into a canonical path inside a registry root.

        Resolution order:
          1. Absolute paths (POSIX-rooted, or Windows with drive/UNC anchor) are the candidate.
          2. Paths relative to cwd (typically the repo root) — if the input names an existing
             file under cwd whose canonical target is inside a registry root, that file is
             used. This covers paths copied from the repo tree such as
             "registries/generated/foo.hocon". A cwd match outside every root is logged and
             skipped, so a stray file in the server's working directory cannot shadow a
             registry file of the same name.
          3. Otherwise, paths are resolved against ``base_dir`` — the directory of the
             first non-empty entry in ``AGENT_MANIFEST_FILE`` (an ``os.pathsep``-separated
             list of manifest files, like ``PATH``), or ``DEFAULT_REGISTRIES_DIR`` when the
             env var is empty or unset. The parse is shared with
             ``FileSystemAgentNetworkPersistor`` so loads and saves agree on file location.

        Every tier's result is resolved (symlinks and ``..`` included) and must be inside a
        registry root: the directory of any ``AGENT_MANIFEST_FILE`` entry, or
        ``DEFAULT_REGISTRIES_DIR`` when none is set (issue #1459). See _canonical_path_inside_roots.

        Backslashes in the input are normalized to forward slashes so Windows-style paths
        work on POSIX (and vice versa).

        On invalid or disallowed input, records the client-facing message for get_error_message()
        and returns None.

        :param network_hocon_file: Agent network hocon file path
        :return: The canonical file path using OS-native separators, or None if invalid or not permitted
        """
        if not isinstance(network_hocon_file, str) or not network_hocon_file.strip():
            error_message: str = (
                f"Error: Invalid network_hocon_file value: {type(network_hocon_file).__name__} "
                "(expected non-empty string)."
            )
            self.logger.error(error_message)
            self.error_message = error_message
            return None

        # Normalize backslashes so Windows-style input also works on POSIX.
        normalized: str = network_hocon_file.strip().replace("\\", "/")
        candidate: Path = Path(normalized)
        # Treat as absolute only if pathlib agrees AND, on Windows, the path has a drive
        # letter (e.g. "C:/...") or a UNC anchor (e.g. "//server/share/..."). On Windows
        # a bare "/foo" is "drive-rooted": Python 3.13+ reports is_absolute() == True for
        # it, but the path is ambiguous without a drive, so we fall through to the
        # relative branch where the leading slash is stripped — preventing the input
        # from bypassing base_dir.
        if candidate.is_absolute() and (os.name != "nt" or candidate.drive):
            return self._confine_to_registries_root(candidate.as_posix(), network_hocon_file)

        # Strip leading separators so a user-supplied "/foo.hocon" cannot escape base_dir.
        # POSIX absolute paths are handled above; this catches the Windows drive-rooted
        # case where Path() would otherwise discard base_dir when joining with a rooted
        # right-hand side.
        trimmed_input: str = normalized.lstrip("/")

        # If the input names an existing file relative to cwd (typically the repo root when
        # running the server from the project directory), use it when its canonical target is
        # inside a registry root, e.g. "registries/generated/foo.hocon". A match outside every
        # root falls through to the registries lookup below rather than being rejected, so a
        # stray file in the working directory cannot block a valid registry path.
        try:
            is_cwd_file: bool = Path(trimmed_input).is_file()
        except OSError as stat_error:
            # On 3.12 and 3.13 is_file() raises PermissionError or ENAMETOOLONG instead of
            # returning False. Treat it as no match so the registries lookup still decides.
            self.logger.warning(
                "Could not check agent network config path %r relative to the working directory: %s",
                network_hocon_file,
                stat_error,
            )
            is_cwd_file = False
        if is_cwd_file:
            try:
                return self._canonical_path_inside_roots(trimmed_input)
            except (OSError, ValueError, RecursionError) as cwd_error:
                self.logger.warning(
                    "Ignoring agent network config path %r relative to the working directory (%s); "
                    "looking it up in the registries directory instead",
                    network_hocon_file,
                    cwd_error,
                )

        # Derive the base registries directory from AGENT_MANIFEST_FILE (the dirname of the
        # first non-empty entry), falling back to the default registries directory. The
        # parse is shared with the persistor so loads and saves cannot drift apart again.
        first_manifest: str = FileSystemAgentNetworkPersistor.get_first_manifest_path()
        base_dir: str = os.path.dirname(first_manifest) if first_manifest else DEFAULT_REGISTRIES_DIR
        return self._confine_to_registries_root((Path(base_dir) / trimmed_input).as_posix(), network_hocon_file)

    def _confine_to_registries_root(self, file_reference: str, network_hocon_file: str) -> str | None:
        """
        Allow only paths whose canonical target is inside a configured registry directory.

        Every refusal, including a path realpath() cannot resolve, gets the same generic client
        message (issue #1459); the server log records the input and the reason.

        :param file_reference: Candidate file path selected by resolve()
        :param network_hocon_file: The path as the client sent it, for the log
        :return: The canonical candidate path, or None after reporting a disallowed path
        """
        try:
            return self._canonical_path_inside_roots(file_reference)
        except (OSError, ValueError, RecursionError) as confine_error:
            # ValueError covers a NUL byte or a lone surrogate, which realpath() cannot encode;
            # OSError covers a symlink loop and a target outside every root.
            self.logger.error("Rejected agent network config path %r: %s", network_hocon_file, confine_error)
            self.error_message = CONFIG_FILE_UNAVAILABLE_MESSAGE
            return None

    @staticmethod
    def _canonical_path_inside_roots(file_reference: str) -> str:
        """
        Resolve a candidate path and require it to be inside a configured registry root.

        :param file_reference: Candidate file path, absolute or relative to cwd
        :return: The canonical path
        :raises PermissionError: When the canonical target is outside every registry root
        :raises OSError: When a symlink loop leaves the path partly unresolved
        :raises ValueError: When the path holds a NUL byte or cannot be encoded for the OS
        :raises RecursionError: When symlink resolution recurses too deeply
        """
        canonical_file: str = os.path.realpath(file_reference)
        # On Python 3.12 realpath() stops at a symlink loop and returns the rest of the path
        # unresolved but normalized, so "loopdir/../link.hocon" comes back as "<root>/link.hocon"
        # with link.hocon still a symlink that may point outside the root (3.13+ is fine). A
        # fully resolved path is a fixed point of realpath(), so a second pass that changes it
        # means the first one stopped early.
        if os.path.realpath(canonical_file) != canonical_file:
            raise OSError(errno.ELOOP, "Symbolic link loop left the path partly unresolved", canonical_file)

        allowed_roots: list[str] = AgentNetworkConfigPathResolver._get_registry_roots()
        for allowed_root in allowed_roots:
            canonical_root: str = os.path.realpath(allowed_root)
            try:
                common_path: str = os.path.commonpath((canonical_file, canonical_root))
            except ValueError:
                # Different drives on Windows: this root cannot contain the file.
                continue
            if os.path.normcase(common_path) == os.path.normcase(canonical_root):
                return canonical_file

        raise PermissionError(
            errno.EACCES, f"Canonical target is outside configured registry roots {allowed_roots}", canonical_file
        )

    @staticmethod
    def _get_registry_roots() -> list[str]:
        """
        :return: The directory of every AGENT_MANIFEST_FILE entry (parsed by the persistor so loads
                and saves agree), or DEFAULT_REGISTRIES_DIR when the env var has no entry
        """
        manifest_paths: list[str] = FileSystemAgentNetworkPersistor.get_manifest_paths()
        allowed_roots: list[str] = [os.path.dirname(path) or "." for path in manifest_paths]
        return allowed_roots or [DEFAULT_REGISTRIES_DIR]
