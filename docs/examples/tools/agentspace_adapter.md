# Agentspace

This agent network delegates to a Google Agentspace agent to interact with different data store connectors on google cloud.
It uses a CodedTool to call the Agentspace APIs.
See the [Agentspace documentation](https://cloud.google.com/agentspace/agentspace-enterprise/docs/overview) for more details.

---

## File

[agentspace_adapter.hocon](../../../registries/tools/agentspace_adapter.hocon)

---

## Prerequisites

- This agent is **disabled by default**. To test it:
    - Manually enable it in the `manifest.hocon` file.

### Steps to install and use agentspace-neurosan-adapter

- Setup your google cloud account
- Ensure that you have python 3.12 on your machine.
- You should have a google cloud account with access to vertexai, googleapis, accesstoken, discoveryengine. (Following
instructions assume that you have a service acccount that has all the necessary access)
- Download and install google cloud CLI by following these [instructions](https://cloud.google.com/sdk/docs/install-sdk)
    - Install python if prompted.
- Source from your zshrc profile:

    ```bash
    source ~/.zshrc
    ```

- Initiate google cloud

    ```bash
    gcloud init
    ```

    - Note: Select your own google cloud account
- For individual access (Authenticate on browser if needed):

    ```bash
    gcloud auth application-default login
    ```

    ```bash
    export GOOGLE_APPLICATION_CREDENTIALS=$HOME/.config/gcloud/application_default_credentials.json
    ```

- For service account access (Authenticate on browser if needed):

    ```bash
    export SERVICE_ACCT_EMAIL="your google cloud service_account"
    gcloud config set auth/impersonate_service_account $SERVICE_ACCT_EMAIL
    gcloud auth application-default login --impersonate-service-account=$SERVICE_ACCT_EMAIL
    ```

    ```bash
    GOOGLE_APPLICATION_CREDENTIALS=$HOME/.config/gcloud/application_default_credentials.json
    ```

- Source again from your zshrc profile:

    ```bash
    source ~/.zshrc
    ```

- Along with the rest of requirements that come with this repo, install `google-cloud-discoveryengine` in your virtual environment

    ```bash
    python -m pip install google-cloud-discoveryengine
    ```

---

## Description

Agentspace is an agent network that communicates with a Google Agentspace agent to answer
questions about any data store connector configured with the agent.

---

## Example conversation

```text
Human: What is the percent representation of each state in the customer profile data?
AI: Sure, I can help with that. I can calculate the percent representation of each state in the customer profile data you
provided.

Here's the breakdown:

California: 20%
Florida: 10%
Illinois: 10%
New Mexico: 10%
New York: 20%
Oklahoma: 10%
Tennessee: 10%
Texas: 10%
Important Note: This is based on the 10 customer profiles you gave me. If you have more data, the percentages would likely
change!
```

By default, if not configured, the agentspace tool will return responses from the dummy dataset.

---

## Configuration

The following environment variables should be set in order to connect to the Agentspace agent:

- **GOOGLE_APPLICATION_CREDENTIALS**: The application_default_credentials.json obtained from the GCP account
- **SERVICE_ACCT_EMAIL**: The email ID registered for GCP
- **ENGINE_ID**: The ID of the agentspace app that you created in Agentspace. Use your own agent/engine_id created using
your service account.  
- **GCP_PROJECT_ID**: Your GCP project ID
- **GCP_LOCATION**: Your Agentspace agent app location. Potential Values: "global", "us", "eu"

You can use the `.env` file to manage these environment variables.
The `.env` file should be in the root of your project directory.
Warning: Do not commit this `.env` file to your version control system (e.g., Git) as it contains sensitive information.

---
