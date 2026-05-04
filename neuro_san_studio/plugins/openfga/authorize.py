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

import asyncio
from argparse import ArgumentParser
from asyncio import Future
from asyncio import gather
from logging import basicConfig
from os import environ
from typing import Any
from typing import Dict
from typing import List

from neuro_san.internals.authorization.factory.authorizer_factory import AuthorizerFactory
from neuro_san.internals.authorization.interfaces.authorizer import Authorizer
from neuro_san.internals.graph.persistence.registry_manifest_restorer import RegistryManifestRestorer


class Authorize:
    """
    Command line tool for authorizing particular users for one or more elements of a manifest file
    using the Authorizer class defined by AGENT_AUTHORIZER.

    This assumes you already have your authorization server running.
    """

    def __init__(self):
        """
        Constructor
        """
        # These come from the arg parser
        self.args: Any = None

        # Make the logging in the lower-level code which is also used in the server show up by
        # default in this manual-use app..
        basicConfig(level="INFO")

    def run(self):
        """
        Workhorse outline method.
        """
        network_names: List[str] = self.get_network_names()
        user_names: List[str] = self.get_user_names()

        authorizer: Authorizer = AuthorizerFactory.create_authorizer()
        print(f"Using Authorizer: {authorizer.__class__.__name__}")

        asyncio.run(self.change_authorization(authorizer, network_names, user_names))

    def get_network_names(self) -> List[str]:
        """
        :return: the names of the networks in the manifest(s)
        """
        networks: List[str] = []

        if self.args.network:
            networks = self.args.network.split(" ")
            return networks

        restorer = RegistryManifestRestorer()
        storages: Dict[str, Dict[str, Any]] = restorer.restore()

        storage: Dict[str, Any] = None
        for storage in storages.values():
            networks.extend(storage.keys())

        return networks

    def get_user_names(self) -> List[str]:
        """
        :return: the names of the users to authorize
        """
        user_names: List[str] = self.args.user.split(" ")
        return user_names

    async def change_authorization(self, authorizer: Authorizer, network_names: List[str], user_names: List[str]):
        """
        :param authorizer: the authorizer to use
        :param network_names: the names of the networks to authorize
        :param user_names: the names of the users to authorize
        """

        # Find the action/relations to authorize
        actions: str = environ.get("AGENT_AUTHORIZER_ALLOW_ACTION", "read")
        relations: List[str] = actions.split(" ")
        resource_type: str = environ.get("AGENT_AUTHORIZER_RESOURCE_KEY", "AgentNetwork")
        actor_type: str = environ.get("AGENT_AUTHORIZER_ACTOR_KEY", "User")

        async with authorizer as auth:
            # Gather everything to do together so as to save on clients
            coroutines: List[Future] = []

            # Loop through all the networks as resources to authorize for the user(s)
            for network_name in network_names:
                resource: Dict[str, Any] = {"type": resource_type, "id": network_name}

                # Loop through all the users
                for user_name in user_names:
                    actor: Dict[str, Any] = {"type": actor_type, "id": user_name}

                    # Loop through all the relations to grant/revoke
                    for relation in relations:
                        coroutines.append(self.authorize_one(auth, actor, relation, resource))

            await gather(*coroutines)

    async def authorize_one(
        self, authorizer: Authorizer, actor: Dict[str, Any], relation: str, resource: Dict[str, Any]
    ) -> bool:
        """
        :param authorizer: the authorizer to use
        :param actor: the actor to authorize
        :param relation: the relation to authorize
        :param resource: the resource to authorize
        :return: True if successful. False otherwise
        """

        message: str = f"{actor['type']}:{actor['id']} {relation} on {resource['type']}:{resource['id']}"
        succeeded: bool = False
        if self.args.grant:
            print(f"Attempting to grant {message}")
            succeeded = await authorizer.grant(actor, relation, resource)
            success_message: str = "succeeded" if succeeded else "already existed"
            print(f"Grant for {message} {success_message}")
        else:
            print(f"Attempting to revoke {message}")
            succeeded = await authorizer.revoke(actor, relation, resource)
            success_message: str = "succeeded" if succeeded else "already existed"
            print(f"Revoke for {message} {success_message}")

        return succeeded

    def parse_args(self):
        """
        Parse command line arguments into member variables
        """
        arg_parser = ArgumentParser()
        self.add_args(arg_parser)
        self.args = arg_parser.parse_args()

    def add_args(self, arg_parser: ArgumentParser):
        """
        Adds arguments.  Allows subclasses a chance to add their own.
        :param arg_parser: The ArgumentParser to add.
        """
        default_user: str = environ.get("USER")
        default_manifest: str = environ.get("AGENT_MANIFEST_FILE")

        # What agent are we talking to?
        arg_parser.add_argument(
            "--user",
            type=str,
            default=default_user,
            help=f"""
Name of the user to authorize.
This can be a space separated list of multiple users to authorize at once.
When not set, this reverts to the USER env var which is currently '{default_user}'.
""",
        )
        arg_parser.add_argument(
            "--network",
            type=str,
            default=None,
            help=f"""
Optional name of the agent network to authorize.
This can be a space separated list of multiple networks to authorize at once.
When not set, we authorize all the networks in the default manifest from the AGENT_MANIFEST_FILE
env var which is currently '{default_manifest}'.
""",
        )

        arg_parser.add_argument(
            "--grant",
            default=True,
            dest="grant",
            action="store_true",
            help="""
Operation of this run is to grant authorization for given user(s) and network(s).
This is the default operation.
""",
        )
        arg_parser.add_argument(
            "--revoke",
            default=False,
            dest="grant",
            action="store_false",
            help="""
Operation of this run is to revoke authorization for given user(s) and network(s).
""",
        )

    def main(self):
        """
        Main entry point for command line user interaction
        """
        self.parse_args()
        self.run()


if __name__ == "__main__":
    Authorize().main()
