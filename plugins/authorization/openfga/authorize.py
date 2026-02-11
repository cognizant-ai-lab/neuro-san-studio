
from typing import Any
from typing import Dict
from typing import List

from argparse import ArgumentParser
from os import environ

from neuro_san.internals.graph.persistence.registry_manifest_restorer import RegistryManifestRestorer
from neuro_san.service.authorization.factory.authorizer_factory import AuthorizerFactory
from neuro_san.service.authorization.interfaces.authorizer import Authorizer


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

    def run(self):
        """
        Workhorse outline method.
        """
        network_names: List[str] = self.get_network_names()
        user_names: List[str] = self.get_user_names()

        authorizer: Authorizer = AuthorizerFactory.create_authorizer()
        print(f"Using Authorizer: {authorizer.__class__.__name__}")

        self.change_authorization(authorizer, network_names, user_names)

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
        for storage in storages:
            networks.extend(storage.keys())

        return networks

    def get_user_names(self) -> List[str]:
        """
        :return: the names of the users to authorize
        """
        user_names: List[str] = self.args.user.split(" ")
        return user_names

    def change_authorization(self, authorizer: Authorizer, network_names: List[str], user_names: List[str]):
        """
        :param authorizer: the authorizer to use
        :param network_names: the names of the networks to authorize
        :param user_names: the names of the users to authorize
        """

        # Find the action/relations to authorize
        actions: str = environ.get("AGENT_AUTHORIZER_ALLOW_ACTION", "read")
        relations: List[str] = actions.split(" ")

        # Loop through all the networks as resources to authorize for the user(s)
        for network_name in network_names:

            resource: Dict[str, Any] = {
                "type": environ.get("AGENT_AUTHORIZER_RESOURCE_KEY", "AgentNetwork"),
                "id": network_name
            }

            # Loop through all the users
            for user_name in user_names:

                actor: Dict[str, Any] = {
                    "type": environ.get("AGENT_AUTHORIZER_ACTOR_KEY", "User"),
                    "id": user_name
                }

                # Loop through all the relations to grant/revoke
                for relation in relations:
                    if self.args.grant:
                        authorizer.grant(actor, relation, resource)
                    else:
                        authorizer.revoke(actor, relation, resource)

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
        # What agent are we talking to?
        arg_parser.add_argument("--user", type=str, default=environ.get("USER"),
                                help="""
Name of the user to authorize. This can be a space separated list of multiple users to authorize at once.
""")
        arg_parser.add_argument("--network", type=str, default=None,
                                help="""
Optional name of the agent network to authorize.
This can be a space separated list of multiple networks to authorize at once.
When not set, we authorize all the networks in the default manifest from the AGENT_MANIFEST_FILE env var.
""")

        arg_parser.add_argument("--grant", default=True, dest="grant", action="store_true",
                                help="""
Operation of this run is to grant authorization for given user(s) and network(s).
""")
        arg_parser.add_argument("--revoke", default=False, dest="grant", action="store_false",
                                help="""
Operation of this run is to revoke authorization for given user(s) and network(s).
""")

    def main(self):
        """
        Main entry point for command line user interaction
        """
        self.parse_args()
        self.run()


if __name__ == "__main__":
    Authorize().main()
