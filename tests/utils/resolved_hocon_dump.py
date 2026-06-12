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

from typing import Any

import argparse
import json

from neuro_san.internals.persistence.abstract_async_config_restorer import AbstractAsyncConfigRestorer


class ResolvedHoconDump:
    """
    Command line tool to read in a given HOCON file and dump the resolved values in its contents
    This allows you to be sure any hocon trickiness is working as expected, from environment variable
    substitution to variable replacement to string interpolation
    """

    def __init__(self):
        """
        Constructor
        """
        self. args = None

    def main(self):
        """
        Main entry point for command line user interaction
        """
        self.parse_args()

        restorer = AbstractAsyncConfigRestorer("a hocon file in isolation for")
        resolved_config: dict[str, Any] = restorer.restore(file_reference=self.args.hocon_file)
        print(json.dumps(resolved_config, indent=4, sort_keys=True))

    def parse_args(self):
        """
        Parse command line arguments
        """
        parser = argparse.ArgumentParser()
        parser.add_argument("hocon_file", type=str, help="HOCON file to read")
        self.args = parser.parse_args()


if __name__ == "__main__":
    ResolvedHoconDump().main()
