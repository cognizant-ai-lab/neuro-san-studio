# OpenFGA Authorization Plugin

This plugin integrates a Neuro SAN server with an [OpenFGA](https://openfga.dev/) server for
controlling authorization access for agents.

## Clarifications

### Authentation != Authorization

Note that _authorization_ - the ability to determine permission to access a resource (in
Neuro SAN's case an agent network) - is not to be confused with _authentication_ -
the ability to determine a user's identity.

Authentication/user identity verification, while an important part of any trusted system,
is _not_ a responsibility within the core capabilities of a Neuro SAN server.

Most often a Neuro SAN server is a single component in a larger cluster deployment where
authentication is handled upon any request entering the cluster.
Consider a chat with your friendly neighborhood dev-ops professional if what you are
really interested in is authentication.

## Features

- **Role-Based Access Control** - Control per-user authorization for per-agent access.
- **Open Source Standards** - OpenFGA is a freely available authorization server.
- **Container Based** - OpenFGA is a container image completely separate from the Neuro SAN server.
- **Database-Persisted** - The most common OpenFGA implementations are persisted with a Postgres database.

## Prerequisites

You need to have docker already installed and running on your system.

## Installation

This example supports the installation steps for running an OpenFGA authorization server
in a Docker container.

1. Install the Python requirements for the Neuro SAN OpenFGA Authorization plugin in your virtual environment.

```bash
pip install -r plugins/authorization/openfga/requirements.txt
```

2. We encapsulate the starting of a SQLite-based OpenFGA server in the following script:

```bash
./plugins/authorization/openfga/run_openfga_server.sh
```

   Your output will look something like:

```
Docker version 29.2.1, build #######
Using default tag: latest
latest: Pulling from openfga/openfga
Digest: sha256:################################################################
Status: Image is up to date for openfga/openfga:latest
docker.io/openfga/openfga:latest
9d3e4887daf6
neuro_san_openfga
neuro_san_openfga
2026-02-11T05:02:03.731Z	INFO	db info	{"current version": 0}
2026-02-11T05:02:03.731Z	INFO	running all migrations
2026-02-11T05:02:03.738Z	INFO	migration done
2026-02-11T05:02:04.629Z	INFO	using 'sqlite' storage engine
2026-02-11T05:02:04.629Z	WARN	authentication is disabled
2026-02-11T05:02:04.629Z	WARN	gRPC TLS is disabled, serving connections using insecure plaintext
2026-02-11T05:02:04.629Z	INFO	📈 starting prometheus metrics server on '0.0.0.0:2112'
2026-02-11T05:02:04.630Z	INFO	starting openfga service...

...

2026-02-11T05:02:04.630Z	INFO	🚀 starting gRPC server on '[::]:8081'...
2026-02-11T05:02:04.631Z	WARN	HTTP TLS is disabled, serving connections using insecure plaintext
2026-02-11T05:02:04.631Z	INFO	🛝 starting openfga playground on http://localhost:3000/playground
2026-02-11T05:02:04.631Z	INFO	🚀 starting HTTP server on '0.0.0.0:8080'...
```

   This script will continue to run with the OpenFGA server running until you Ctrl-C it.
   Keep this going. We will be using it in subsequent steps.


3. In another shell, but using the same virtual environment, set some environment variables that
enable the use of the OpenFGA server for authorization within your Neuro SAN server:

```bash
# What class neuro-san server should use for authorization
export AGENT_AUTHORIZER=neuro_san.internals.authorization.openfga.open_fga_authorizer.OpenFgaAuthorizer

# The request metadata field to use as the user id for authorization
export AGENT_AUTHORIZER_ACTOR_ID_METADATA_KEY=user_id

# See authorization results. In production you would not want to set this at all.
export AGENT_DEBUG_AUTH=true

# Below: Different keys correspond to aspects of the authorization policy that is defined in the .fga file

# The type defined in the authorization policy (.fga file) for a user
export AGENT_AUTHORIZER_ACTOR_KEY=User

# The type defined in the authorization policy (.fga file) for an agent network
export AGENT_AUTHORIZER_RESOURCE_KEY=AgentNetwork

# The type defined in the authorization policy (.fga file) for read permissions
export AGENT_AUTHORIZER_ALLOW_RELATION=read

# Where the OpenFGA HTTP server is running
export FGA_API_URL=http://localhost:8082

# The file containing the authorization policy
export FGA_POLICY_FILE=plugins/authorization/openfga/sample_authorization_model.json

# The name of the authorization store to use
export FGA_STORE_NAME=default

```

4. In a shell with the same virtual env and environment variables set,
   run the authorize.py utility to get initial permissions into the OpenFGA database for your user.
   Without any arguments, it will read in the manifest and authorize the current user for each network.
   This command is given from the neuro-san-studio repo top-level directory.

```bash
python plugins/authorization/openfga/authorize.py
```

    You will see the results of reading in the manifest and authorizing the current user for each network.

    If you run this script again against the same authorization database, you might see the OpenFGA
    server give some errors about "tuple to be written already existed or the tuple to be deleted did not exist".
    This can be OK because the server will report when obect relations already exist.
    The authorize.py app will report whether it created relations or they were already there.

5. In a shell with the same virtual env and environment variables set,
   now run your neuro-san server.

   This command is given from the neuro-san-studio repo top-level directory.

```bash
python -m neuro_san.service.main_loop.server_main_loop
```

6. In yet another shell, try running a listing of the agents against your running Neuro SAN server
   with your existing user.

```bash
python -m neuro_san.client.agent_cli --http --list
```
    You should get a complete list of the agents that you have access as all networks
    should be authorized for your user.

7. Now try running the same as above but with a different user id.

```bash
USER="bogus" python -m neuro_san.client.agent_cli --http --list
```

    This bogus user should not be able to see any of the agents.  Your output should be empty.

```
Available agents:
{
    "agents": []
}
```

## Extra Credit

For any of the below extra credit exercizes, you will need the fga command line tool.

To install the fga command line tool use the script below if you are running on linux.

```bash
sudo plugins/authorization/openfga/install_fga_cli.sh
```

Note that this script:
    * is linux-specific (Windows people: mods welcome for the larger audience!)
    * will need to be run as root
    * will install to /usr/bin/fga.

If you are not running on linux you will have to figure out your own way of getting the fga command line
tool installed.  See https://openfga.dev/docs/getting-started/cli for more info.

### Modifying the OpenFGA Policy Model

1. Use the fga CLI tool to validate the authorization policy model file

```bash
    # Validate the fga file
    fga model validate --file plugins/authorization/openfga/sample_authorization_model.fga
```

   Output will look something like:

```
{
  "is_valid":true
}
```

2. Use the fga CLI tool to transform the authorization policy model file into a JSON format
   ingestible by the OpenFGA API.

```bash
    # Transform the .fga DSL to a JSON description which is importable by the OpenFGA API
    fga model transform --file plugins/authorization/openfga/sample_authorization_model.fga | python -m json.tool > plugins/authorization/openfga/sample_authorization_model.json
```

   There will not be any real output from this step, but the file sample_authorization_model.json
   will be (re-)created in the plugins/authorization/openfga directory.

3. Re-run your OpenFGA and neuro-san servers with the same env vars as described in previous sections

### Run tests on the OpenFGA model

It is possible to create tests for an OpenFGA model to be sure that the relations
are defined correctly.  We have included one test with this example. To run it:

```bash
    fga model test --tests plugins/authorization/openfga/agent_network_access_test.fga.yml
```

---

## Debugging Hints

### Common Issues

- run_openfga_server.sh: line 42: docker: command not found

    This means you need to install Docker on your system.
    See the Docker installation links in the Resources section below.

---

## Resources

- [OpenFGA documentation](https://openfga.dev/docs/fga)
  Extensive documentation on OpenFGA capabilities and configuration.

- [Oso's Authorization Academy](https://www.osohq.com/academy)
  An excellent resource describing the basics concepts of Authorization and several different
  authorization models.

  Oso itself is a paid authorization service with free trials available supporting a company of lovely
  and helpful people trying to make authorization easier for everyone. (OpenFGA itself is free, but no picnic.)
  Maybe if demand is there we will add an Oso implementation of the Authorizer interface.

- Docker Installation on various platforms:

    - [Install Docker Desktop on Linux](https://docs.docker.com/desktop/setup/install/linux/)
    - [Install Docker Desktop on Mac](https://docs.docker.com/desktop/setup/install/mac-install/)
    - [Install Docker Desktop on Windows](https://docs.docker.com/desktop/setup/install/windows-install/)

- [The Neuro SAN Dockerfile](https://github.com/cognizant-ai-lab/neuro-san/blob/main/neuro_san/deploy/Dockerfile)
  has the documentation for each of the environment variables mentioned above.

- [The Neuro SAN Authorizer interface](https://github.com/cognizant-ai-lab/neuro-san/blob/main/neuro_san/internals/authorization/interfaces/authorizer.py)
  contains documentation and examples for each of the methods of the Authorizer interface

- [The OpenFGA implementation of the Authorizer interface](https://github.com/cognizant-ai-lab/neuro-san/blob/main/neuro_san/internals/authorization/openfga/open_fga_authorizer.py)
  Seeing the details of the OpenFGA implementation can give you some ideas as to how to extend it for your own purposes.
  It's worth noting that we have used an extended version of the OpenFGA Authorizer and supplied schema
  to allow for many other objects under authorization control, including special users, and storing information
  about authorization models that evolve over time. Go wild.
