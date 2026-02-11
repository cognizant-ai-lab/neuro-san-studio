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

   Keep this container running in a separate shell or background process, we will be using it.

   Note: There are extra instructions beyond this point for setting up the OpenFGA server
   with authentication and/or profiling. These steps are not really relevant for this example.

3. Install the Python requirements for the Neuro SAN OpenFGA Authorization plugin in your virtual environment.

```bash
pip install -r plugins/authorization/openfga/requirements.txt
```

4. Install the fga command line tool.

   Note that this script:
    * is linux-specific (Windows people: mods welcome for the larger audience!)
    * will need to be run as root 
    * will install to /usr/bin/fga.

```bash
sudo plugins/authorization/openfga/install_fga_cli.sh
```

5. Take the sample authorization policy model and transform it so it can be loaded into the OpenFGA server. 

    # Validate the fga file
    fga model validate --file sample_authorization_model.fga

    # Transform the .fga DSL to a JSON description which is importable by the OpenFGA API
    fga model transform --file sample_authorization_model.fga | python -m json.tool > sample_authorization_model.json
