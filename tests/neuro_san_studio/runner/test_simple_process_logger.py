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

"""Tests for SimpleProcessLogger."""

import io
import os
import tempfile
import time

from neuro_san_studio.interfaces.process_logger_interface import ProcessLoggerInterface
from neuro_san_studio.runner.simple_process_logger import SimpleProcessLogger


class _FakeProcess:  # pylint: disable=too-few-public-methods
    """Fake subprocess with readable stdout/stderr pipes."""

    def __init__(self, stdout_lines, stderr_lines):
        self.stdout = io.StringIO("".join(f"{line}\n" for line in stdout_lines))
        self.stderr = io.StringIO("".join(f"{line}\n" for line in stderr_lines))


class TestSimpleProcessLogger:
    """Tests for the SimpleProcessLogger fallback."""

    def test_implements_interface(self):
        """Test that SimpleProcessLogger implements ProcessLoggerInterface."""
        assert issubclass(SimpleProcessLogger, ProcessLoggerInterface)
        logger = SimpleProcessLogger()
        assert isinstance(logger, ProcessLoggerInterface)

    def test_drains_pipes_to_log_file(self):
        """Test that attach_process_logger writes output to the log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            process = _FakeProcess(["hello", "world"], ["error line"])

            logger = SimpleProcessLogger()
            logger.attach_process_logger(process, "TestProc", log_file)

            # Give daemon threads time to drain
            time.sleep(0.5)

            with open(log_file, encoding="utf-8") as f:
                content = f.read()

            assert "[TestProc:stdout] hello" in content
            assert "[TestProc:stdout] world" in content
            assert "[TestProc:stderr] error line" in content

    def test_handles_none_pipes(self):
        """Test that None pipes are skipped without error."""

        class _NullPipeProcess:  # pylint: disable=too-few-public-methods
            """Fake process with None pipes."""

            stdout = None
            stderr = None

        logger = SimpleProcessLogger()
        # Should not raise
        logger.attach_process_logger(_NullPipeProcess(), "NullProc", "/tmp/null.log")

    def test_creates_log_directory(self):
        """Test that missing parent directories are created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "nested", "deep", "test.log")
            process = _FakeProcess(["line"], [])

            logger = SimpleProcessLogger()
            logger.attach_process_logger(process, "TestProc", log_file)

            time.sleep(0.5)
            assert os.path.exists(log_file)
