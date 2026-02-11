# OpenFGA Authorization Plugin

This plugin integrates a Neuro SAN server with an [OpenFGA](https://openfga.dev/) server for
controlling authorization access for agents.

## Clarifications - Authentation vs Authorization

Note that _authorization_ - the ability to determine permission to access a resource (in
Neuro SAN's case an agent network) - is not to be confused with _authentication_ -
the ability to determine a user's identity.

Authentication/user identity verification, while an important part of any trusted system,
is _not_ a responsibility within the core capabilities of a Neuro SAN server.

Most often a Neuro SAN server is a single component in a larger cluster deployment where
authentication is handled is handled upon any request entering the cluster. 
Consider a chat with your friendly neighborhood dev-ops professional if what you are
really interested in is authentication.

## Features

- **Role-Based Access Control** - Control per-user authorization for per-agent access.
- **Open Source Standards** - OpenFGA is a freely available authorization server.
- **Container Based** - OpenFGA is a container image completely separate from the Neuro SAN server.
- **Database-Persisted** - The most common OpenFGA implementations are persisted with a Postgres database.

## Installation

This example supports the installation steps for running an OpenFGA authorization server
in a Docker container.

1. Follow the instructions to create a docker instance running OpenFGA:

   https://openfga.dev/docs/getting-started/setup-openfga/docker#step-by-step

   By the end of this phase, the container will be running with a 'memory' based storage engine.
   Output will look something like:

```
2026-02-11T01:05:42.584Z	INFO	using 'memory' storage engine
2026-02-11T01:05:42.584Z	WARN	authentication is disabled
2026-02-11T01:05:42.584Z	WARN	gRPC TLS is disabled, serving connections using insecure plaintext
2026-02-11T01:05:42.584Z	INFO	📈 starting prometheus metrics server on '0.0.0.0:2112'
2026-02-11T01:05:42.584Z	INFO	starting openfga service...

...

2026-02-11T01:05:42.585Z	INFO	🚀 starting gRPC server on '[::]:8081'...
2026-02-11T01:05:42.586Z	WARN	HTTP TLS is disabled, serving connections using insecure plaintext
2026-02-11T01:05:42.586Z	INFO	🛝 starting openfga playground on http://localhost:3000/playground
2026-02-11T01:05:42.586Z	INFO	🚀 starting HTTP server on '0.0.0.0:8080'...
```

    Ctrl-C to stop the container to continue to the next step.

2. The base examples on that OpenFGA setup page will have you choose between Postgres, MySQL,
   and SQLite as databases.  At this level, it doesn't really matter what you choose, but if
   you are just starting out, SQLite is the lightest-weight overall. Follow the directions here:

   https://openfga.dev/docs/getting-started/setup-openfga/docker#using-sqlite

   For the last step, to start the server, we do not want the OpenFGA server taking up
   the same HTTP port as the Neuro SAN server, so we forward the local port 8082 to the container
   port 8080 by doing this instead:

```bash
docker run --name openfga --network=bridge \
    -p 3000:3000 -p 8082:8080 -p 8081:8081 \
    -v openfga:/home/nonroot \
    -u nonroot \
    openfga/openfga run \
    --datastore-engine sqlite \
    --datastore-uri 'file:/home/nonroot/openfga.db'
```

   Keep this container running in a separate shell or background process, we will be using it.

   Note: There are extra instructions beyond this point for setting up the OpenFGA server
   with authentication and/or profiling. These steps are not really relevant for this example.

3. Install the Python requirements for the Neuro SAN OpenFGA Authorization plugin in your virtual environment.

```bash
pip install -r plugins/authorization/openfga/requirements.txt
```

4. Set some environment variables that enable the use of the OpenFGA server for Authorization.

```bash
# Where the OpenFGA grpc server is running
export FGA_API_URL=http://localhost:8082

# The file containing the authorization policy
export FGA_POLICY_FILE=plugins/authorization/openfga/sample_authorization_model.json

# The name of the authorization store to use
export AGENT_FGA_STORE_NAME=default

# What class neuro-san server should use for authorization
export AGENT_AUTHORIZER=neuro_san.service.authorization.openfga.open_fga_authorizer.OpenFgaAuthorizer

# The request metadata field to use as the user id for authorization
export AGENT_AUTHORIZER_ACTOR_ID_METADATA_KEY=user_id

# Below: Different keys correspond to aspects of the authorization policy that is defined in the .fga file

# The type defined in the authorization policy (.fga file) for a user
export AGENT_AUTHORIZER_ACTOR_KEY=User

# The type defined in the authorization policy (.fga file) for an agent network
export AGENT_AUTHORIZER_RESOURCE_KEY=AgentNetwork

# The type defined in the authorization policy (.fga file) for read permissions
export AGENT_AUTHORIZER_ALLOW_ACTION=read
```

5. Run your neuro-san server.



## Extra Credit: Modifying the OpenFGA Policy Model

1. Install the fga command line tool.

   Note that this script:
    * is linux-specific (Windows people: mods welcome for the larger audience!)
    * will need to be run as root 
    * will install to /usr/bin/fga.

```bash
sudo plugins/authorization/openfga/install_fga_cli.sh
```

2. Use the fga CLI tool to validate the authorization policy model file

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

3. Use the fga CLI tool to transform the authorization policy model file into a JSON format
   ingestible by the OpenFGA API.

```bash
    # Transform the .fga DSL to a JSON description which is importable by the OpenFGA API
    fga model transform --file plugins/authorization/openfga/sample_authorization_model.fga | python -m json.tool > plugins/authorization/openfga/sample_authorization_model.json
```

   There will not be any real output from this step, but the file sample_authorization_model.json
   will be (re-)created in the plugins/authorization/openfga directory.

4. Re-run your neuro-san server with the same env vars as described in previous sections
