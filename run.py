# Copyright (C) 2023-2025 Cognizant Digital Business, Evolutionary AI.
# All Rights Reserved.
# Issued under the Academic Public License.
#
# You can be released from the terms, and requirements of the Academic Public
# License by purchasing a commercial license.
# Purchase of a commercial license is mandatory for any use of the
# neuro-san-studio SDK Software in commercial settings.
#
import argparse
import glob
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from typing import Any
from typing import Dict

from dotenv import load_dotenv


class NeuroSanRunner:
    """Command-line tool to run the Neuro SAN server and web client."""

    # pylint: disable=too-many-instance-attributes
    def __init__(self):
        """Initialize configuration and parse CLI arguments."""
        self.is_windows = os.name == "nt"
        self.root_dir = os.path.dirname(os.path.abspath(__file__))
        self.logs_dir = os.path.join(self.root_dir, "logs")
        self.thinking_file = os.path.join(self.logs_dir, "agent_thinking.txt")
        self.thinking_dir = os.path.join(self.logs_dir, "thinking_dir")
        print(f"Root directory: {self.root_dir}")

        # Load environment variables from .env file
        self.load_env_variables()

        # Default Configuration
        self.args: Dict[str, Any] = {
            "server_host": os.getenv("NEURO_SAN_SERVER_HOST", "localhost"),
            "server_grpc_port": int(os.getenv("NEURO_SAN_SERVER_GRPC_PORT", "30011")),
            "server_http_port": int(os.getenv("NEURO_SAN_SERVER_HTTP_PORT", "8080")),
            "server_connection": str(os.getenv("NEURO_SAN_SERVER_CONNECTION", "http")),
            "manifest_update_period_seconds": int(os.getenv("AGENT_MANIFEST_UPDATE_PERIOD_SECONDS", "5")),
            "default_sly_data": str(os.getenv("DEFAULT_SLY_DATA", "")),
            "nsflow_host": os.getenv("NSFLOW_HOST", "localhost"),
            "nsflow_port": int(os.getenv("NSFLOW_PORT", "4173")),
            "nsflow_log_level": os.getenv("NSFLOW_LOG_LEVEL", "info"),
            "vite_api_protocol": os.getenv("VITE_API_PROTOCOL", "http"),
            "vite_ws_protocol": os.getenv("VITE_WS_PROTOCOL", "ws"),
            "neuro_san_web_client_port": int(os.getenv("NEURO_SAN_WEB_CLIENT_PORT", "5003")),
            "thinking_file": os.getenv("THINKING_FILE", self.thinking_file),
            "thinking_dir": os.getenv("THINKING_DIR", self.thinking_dir),
            # Ensure all paths are resolved relative to `self.root_dir`
            "agent_manifest_file": os.getenv(
                "AGENT_MANIFEST_FILE", os.path.join(self.root_dir, "registries", "manifest.hocon")
            ),
            "agent_tool_path": os.getenv("AGENT_TOOL_PATH", os.path.join(self.root_dir, "coded_tools")),
            "agent_toolbox_info_file": os.getenv(
                "AGENT_TOOLBOX_INFO_FILE", os.path.join(self.root_dir, "toolbox", "toolbox_info.hocon")
            ),
            "logs_dir": self.logs_dir,
        }

        # Ensure logs directory exists
        os.makedirs(self.logs_dir, exist_ok=True)
        os.makedirs(self.thinking_dir, exist_ok=True)

        # Parse command-line arguments
        self.args.update(self.parse_args())

        # Process references
        self.server_process = None
        self.flask_webclient_process = None
        self.nsflow_process = None

    def load_env_variables(self):
        """Load .env file from project root and set variables."""
        env_path = os.path.join(self.root_dir, ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path)
            print(f"Loaded environment variables from: {env_path}")
        else:
            print(f"No .env file found at {env_path}. \nUsing defaults.\n")

    def parse_args(self):
        """Parses command-line arguments for configuration."""
        parser = argparse.ArgumentParser(
            description="Run the Neuro SAN server and web client.",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )

        parser.add_argument(
            "--server-host", type=str, default=self.args["server_host"], help="Host address for the Neuro SAN server"
        )
        parser.add_argument(
            "--server-grpc-port",
            type=int,
            default=self.args["server_grpc_port"],
            help="Port number for the Neuro SAN server grpc endpoint",
        )
        parser.add_argument(
            "--server-http-port",
            type=int,
            default=self.args["server_http_port"],
            help="Port number for the Neuro SAN server http endpoint",
        )
        parser.add_argument(
            "--nsflow-port",
            type=int,
            default=self.args["nsflow_port"],
            help="Port number for the nsflow client",
        )
        parser.add_argument(
            "--web-client-port",
            type=int,
            default=self.args["neuro_san_web_client_port"],
            help="Port number for the web client",
        )
        parser.add_argument(
            "--thinking-file", type=str, default=self.args["thinking_file"], help="Path to the agent thinking file"
        )
        parser.add_argument("--no-html", action="store_true", help="Don't generate html for network diagrams")
        parser.add_argument(
            "--client-only", action="store_true", help="Run only the nsflow client without NeuroSan server"
        )
        parser.add_argument(
            "--server-only", action="store_true", help="Run only the NeuroSan server without the default nsflow client"
        )
        parser.add_argument(
            "--use-flask-web-client", action="store_true", help="Use the flask based neuro-san-web-client"
        )

        args, _ = parser.parse_known_args()
        explicitly_passed_args = {arg for arg in sys.argv[1:] if arg.startswith("--")}
        # Check for mutually exclusive arguments
        if args.client_only and (
            "--server-host" in explicitly_passed_args or "--server-port" in explicitly_passed_args
        ):
            parser.error("[x] You cannot specify --server-host or --server-port when using --client-only mode.")
        if args.server_only and (
            "--nsflow-host" in explicitly_passed_args or "--nsflow-port" in explicitly_passed_args
        ):
            parser.error("[x] You cannot specify --nsflow-host or --nsflow-port when using --server-only mode.")
        if args.client_only and args.server_only:
            parser.error("[x] You cannot specify both --client-only and --server-only at the same time.")

        return vars(args)

    def set_environment_variables(self):
        """Set required environment variables, optionally using neuro-san defaults."""
        print("\n" + "=" * 50 + "\n")
        print("Setting environment variables...\n")
        # Common env variables
        os.environ["PYTHONPATH"] = self.root_dir
        os.environ["AGENT_MANIFEST_FILE"] = self.args["agent_manifest_file"]
        os.environ["AGENT_TOOL_PATH"] = self.args["agent_tool_path"]
        os.environ["AGENT_TOOLBOX_INFO_FILE"] = self.args["agent_toolbox_info_file"]
        os.environ["NEURO_SAN_SERVER_CONNECTION"] = self.args["server_connection"]
        os.environ["AGENT_MANIFEST_UPDATE_PERIOD_SECONDS"] = str(self.args["manifest_update_period_seconds"])
        print(f"PYTHONPATH set to: {os.environ['PYTHONPATH']}")
        print(f"AGENT_MANIFEST_FILE set to: {os.environ['AGENT_MANIFEST_FILE']}")
        print(f"AGENT_TOOL_PATH set to: {os.environ['AGENT_TOOL_PATH']}")
        print(f"AGENT_TOOLBOX_INFO_FILE set to: {os.environ['AGENT_TOOLBOX_INFO_FILE']}")
        print(f"NEURO_SAN_SERVER_CONNECTION set to: {os.environ['NEURO_SAN_SERVER_CONNECTION']}")
        print(f"AGENT_MANIFEST_UPDATE_PERIOD_SECONDS set to: {os.environ['AGENT_MANIFEST_UPDATE_PERIOD_SECONDS']}\n")

        # Client-only env variables
        if not self.args["server_only"]:
            os.environ["THINKING_FILE"] = self.args["thinking_file"]
            os.environ["THINKING_DIR"] = self.args["thinking_dir"]
            print(f"THINKING_FILE set to: {os.environ['THINKING_FILE']}")
            print(f"THINKING_DIR set to: {os.environ['THINKING_DIR']}")
            if self.args["use_flask_web_client"]:
                os.environ["NEURO_SAN_WEB_CLIENT_PORT"] = str(self.args["web_client_port"])
                print(f"NEURO_SAN_WEB_CLIENT_PORT set to: {os.environ['NEURO_SAN_WEB_CLIENT_PORT']}")
            else:
                os.environ["NSFLOW_PORT"] = str(self.args["nsflow_port"])
                os.environ["VITE_API_PROTOCOL"] = str(self.args["vite_api_protocol"])
                os.environ["VITE_WS_PROTOCOL"] = str(self.args["vite_ws_protocol"])
                print(f"NSFLOW_PORT set to: {os.environ['NSFLOW_PORT']}")
                print(f"VITE_API_PROTOCOL set to: {os.environ['VITE_API_PROTOCOL']}")
                print(f"VITE_WS_PROTOCOL set to: {os.environ['VITE_WS_PROTOCOL']}")
                # Set env variable for using nsflow in client-only mode
                if self.args["client_only"]:
                    os.environ["NSFLOW_CLIENT_ONLY"] = "True"
                    print(f"NSFLOW_CLIENT_ONLY set to: {os.environ['NSFLOW_CLIENT_ONLY']}")

        # Server-only env variables
        if not self.args["client_only"]:
            os.environ["NEURO_SAN_SERVER_HOST"] = self.args["server_host"]
            os.environ["NEURO_SAN_SERVER_GRPC_PORT"] = str(self.args["server_grpc_port"])
            os.environ["NEURO_SAN_SERVER_HTTP_PORT"] = str(self.args["server_http_port"])

            print(f"NEURO_SAN_SERVER_HOST set to: {os.environ['NEURO_SAN_SERVER_HOST']}")
            print(f"NEURO_SAN_SERVER_GRPC_PORT set to: {os.environ['NEURO_SAN_SERVER_GRPC_PORT']}\n")
            print(f"NEURO_SAN_SERVER_HTTP_PORT set to: {os.environ['NEURO_SAN_SERVER_HTTP_PORT']}\n")

        print("\n" + "=" * 50 + "\n")

    @staticmethod
    def generate_html_files():
        """Generate .html files for all registry files except manifest.hocon."""
        for file in glob.glob("./registries/*"):
            if os.path.basename(file) != "manifest.hocon":
                print(f"Generating .html file for: {file}")
                result = subprocess.run(
                    [sys.executable, "-m", "neuro_san_web_client.agents_diagram_builder", "--input_file", file],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    check=True,
                )
                print(result.stdout)
                if result.stderr:
                    print(result.stderr, file=sys.stderr)

    @staticmethod
    def stream_output(pipe, log_file, prefix):
        """Stream subprocess output to console and log file in real-time."""
        with open(log_file, "a", encoding="utf-8") as log:
            for line in iter(pipe.readline, ""):
                formatted_line = f"{prefix}: {line.strip()}"
                print(formatted_line)  # Print to console
                log.write(formatted_line + "\n")  # Write to log file
        pipe.close()

    def start_process(self, command, process_name, log_file):
        """Start a subprocess and capture logs."""
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if self.is_windows else 0

        # Initialize/clear the log file before starting
        with open(log_file, "w", encoding="utf-8") as log:
            log.write(f"Starting {process_name}...\n")

        # pylint: disable=consider-using-with
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
            start_new_session=not self.is_windows,
            creationflags=creation_flags,
        )

        print(f"Started {process_name} with PID {process.pid}")

        # Start streaming logs in separate threads
        stdout_thread = threading.Thread(target=self.stream_output, args=(process.stdout, log_file, process_name))
        stderr_thread = threading.Thread(target=self.stream_output, args=(process.stderr, log_file, process_name))
        stdout_thread.start()
        stderr_thread.start()

        return process

    def start_neuro_san(self):
        """Start the Neuro SAN server."""
        print("Starting Neuro SAN server...")
        command = [
            sys.executable,
            "-u",
            "-m",
            "neuro_san.service.main_loop.server_main_loop",
            "--port",
            str(self.args["server_grpc_port"]),
            "--http_port",
            str(self.args["server_http_port"]),
        ]
        self.server_process = self.start_process(command, "NeuroSan", "logs/server.log")
        print("NeuroSan server grpc started on port: ", self.args["server_grpc_port"])
        print("NeuroSan server http started on port: ", self.args["server_http_port"])

    def start_nsflow(self):
        """Start nsflow client."""
        print("Starting nsflow client...")
        command = [
            sys.executable,
            "-u",
            "-m",
            "uvicorn",
            "nsflow.backend.main:app",
            "--port",
            str(self.args["nsflow_port"]),
            "--reload",
        ]

        self.nsflow_process = self.start_process(command, "nsflow", "logs/nsflow.log")
        print("nsflow client started on port: ", self.args["nsflow_port"])

    def start_flask_web_client(self):
        """Start the Flask web client."""
        print("Starting Flask web client...")
        command = [
            sys.executable,
            "-u",
            "-m",
            "neuro_san_web_client.app",
            "--server-host",
            self.args["server_host"],
            "--server-port",
            str(self.args["server_grpc_port"]),
            "--web-client-port",
            str(self.args["web_client_port"]),
            "--thinking-file",
            self.args["thinking_file"],
        ]
        self.flask_webclient_process = self.start_process(command, "FlaskWebClient", "logs/webclient.log")
        print("Flask web client started on port: ", self.args["web_client_port"])

    # pylint: disable=unused-argument
    def signal_handler(self, signum, frame):
        """Handle termination signals to cleanly exit."""
        print("\nTermination signal received. Stopping all processes...")

        if self.server_process:
            print(f"\nStopping SERVER (PID {self.server_process.pid})...")
            if self.is_windows:
                self.server_process.terminate()
            else:
                os.killpg(os.getpgid(self.server_process.pid), signal.SIGKILL)

        if self.flask_webclient_process:
            print(f"Stopping WEB CLIENT (PID {self.flask_webclient_process.pid})...")
            if self.is_windows:
                self.flask_webclient_process.terminate()
            else:
                os.killpg(os.getpgid(self.flask_webclient_process.pid), signal.SIGKILL)

        if self.nsflow_process:
            print(f"Stopping NSFLOW (PID {self.nsflow_process.pid})...")
            if self.is_windows:
                self.nsflow_process.terminate()
            else:
                os.killpg(os.getpgid(self.nsflow_process.pid), signal.SIGKILL)

        sys.exit(0)

    def is_port_open(self, host: str, port: int, timeout=1.0) -> bool:
        """
        Check if a port is open on a given host.
        :return: True if the port is open, False otherwise.
        """
        # Create a socket and set a timeout
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            try:
                sock.connect((host, port))
                return True
            except (ConnectionRefusedError, TimeoutError, OSError):
                return False

    def _check_port_conflicts(self) -> list[str]:
        """Check if any of the ports are in use."""
        port_conflicts = []

        if not self.args["server_only"] and self.args["nsflow_host"] == "localhost":
            if self.is_port_open(self.args["nsflow_host"], self.args["nsflow_port"]):
                port_conflicts.append(f"NSFlow client port {self.args['nsflow_port']} is already in use.")

        if not self.args["client_only"] and self.args["server_host"] == "localhost":
            if self.is_port_open(self.args["server_host"], self.args["server_grpc_port"]):
                port_conflicts.append(f"Neuro-San server grpc port {self.args['server_grpc_port']} is already in use.")
            if self.is_port_open(self.args["server_host"], self.args["server_http_port"]):
                port_conflicts.append(f"Neuro-San server http port {self.args['server_http_port']} is already in use.")

        if self.args.get("use_flask_web_client"):
            if self.is_port_open("localhost", self.args["neuro_san_web_client_port"]):
                port_conflicts.append(
                    f"Flask web client port {self.args['neuro_san_web_client_port']} is already in use."
                )

        return port_conflicts

    def conditional_start_servers(self):
        """
        Start neuro-san, nsflow, and flask client based on conditions while running on localhost.
        Exit if any port is in use.
        """
        client_only = self.args["client_only"]
        server_only = self.args["server_only"]
        use_flask = self.args.get("use_flask_web_client", False)
        no_html = self.args.get("no_html", False)

        if client_only and server_only:
            print("Cannot use --client-only and --server-only together.")
            sys.exit(1)

        port_conflicts = self._check_port_conflicts()

        # Exit early if any conflict is found
        if port_conflicts:
            print("\n" + "=" * 50)
            for msg in port_conflicts:
                print(msg)
            print("=" * 50 + "\nExiting due to port conflicts.\n")
            sys.exit(1)

        # Start services only if ports are free
        if not server_only:
            if use_flask:
                if not no_html:
                    self.generate_html_files()
                self.start_flask_web_client()
                print("Flask web-client is now running.")
            else:
                self.start_nsflow()
                print("nsflow client is now running.")

        if not client_only:
            self.start_neuro_san()
            time.sleep(3)
            print("Neuro-San server is now running.")

    def run(self):
        """Run the Neuro SAN server and a client."""
        print("\nInitial Run Config:\n" + "\n".join(f"{key}: {value}" for key, value in self.args.items()) + "\n")

        # Set environment variables
        self.set_environment_variables()

        # Ensure logs directory exists
        os.makedirs("logs", exist_ok=True)

        # Set up signal handling for termination
        signal.signal(signal.SIGINT, self.signal_handler)  # Handle Ctrl+C
        if not self.is_windows:
            signal.signal(signal.SIGTERM, self.signal_handler)  # Handle kill command (not available on Windows)

        # Start all relevant processes
        self.conditional_start_servers()

        print("\n" + "=" * 50 + "\n")
        print("All processes now running.")
        print("Press Ctrl+C to stop any running processes.")
        print("\n" + "=" * 50 + "\n")

        # Wait on active processes to finish
        if self.nsflow_process:
            self.nsflow_process.wait()
        if self.server_process:
            self.server_process.wait()
        if self.flask_webclient_process:
            self.flask_webclient_process.wait()


if __name__ == "__main__":
    runner = NeuroSanRunner()
    runner.run()
