# Copy Cat

The **Copy Cat** agent is a small network designed to demonstrate the capabilities of agents creating agents
using Neuro SAN's Reservations API.

---

## File

[copy_cat.hocon](../../../registries/experimental/copy_cat.hocon)

---

## Description

The Copy Cat agent network provides a very simple example as to how an agent
network can create another agent network by use of the Neuro SAN Reservations API.

You give it a network that already exists in the manifest, like "basic/hello_world.hocon"
and it will create a temporary copy of it. Copy Cat will optionally call
the new network depending on the input received.

The new temporary network exists only in memory for the duration that a single server lives.
It has a limited lifespan, as the server will remove it from availablilty after
a prescribed amount of time.  There are no additions to the filesystem, nor any additions
to the manifiest.hocon.  The intent is that this is a clean mechanism for agents to create
other agents that can scale up safely.

By convention, any agent network that creates a temporary network should return a
reference to it via a specific key in the sly_data called "agent_reservations".
The value set for this key is a list of dictionaries describing newly created networks,
which contain information about their names and how long they are available for.
The idea is that if a generic client like nsflow or MAUI can expect this particular key
to have this information in it, then any generic UI can provide new affordances to the
new networks for its users.

Temporary networks names will have a particular format to them.  There is a
human-readable prefix string, which has certain character limitations to it,
and there is a UUID suffix that helps guarantee uniqueness across multiple servers.

---

## Prerequisites

This agent network requires the following setup:

### Python Dependencies

Nothing special.

### Environment Variables

```bash
export AGENT_TEMPORARY_NETWORK_UPDATE_PERIOD_SECONDS=5
```

This environment variable controls the frequency that the server will check for
new and/or expired temporary networks. The default is 0, implying that temporary networks
are not allowed on the server (a reasonable precaution for most servers).

---

## Example Conversation

### Human

```text
Please make a copy of the basic/hello_world.hocon file.

When you are done copying it, call the new agent with the following text:
'From earth, I approach a new planet and wish to send a short 2-word greeting to the new orb.'
```

This is an example of pointing copycat at an existing agent network - hello_world - and then
immediately calling the new temporary agent.

### AI

```text
Hello, world!
```

This is the ideal result from a call to hello_world. We were really calling the temporary
copy of the agent, but it returns us the same results.  As with the existing hello_world agent,
it's only so predictable. Your mileage will vary here.

```json
sly_data: {
    "agent_reservations": [
        {
            "expiration_time": 1659753044,
            "lifetime_in_seconds": 300.0,
            "reservation_id": "copy_cat-hello_world-01234567-89ab-cdef-0123-456789abcdef",
        }
    ]
}
```

The Copy Cat agent creates only a single network, but your own riffs are allowed to create multiple
new temporary networks within a single call. This is why the sly_data agent_reservations value is
a list.  Each element of the list is a dictionary describing a single temporary network each of which
contains the following keys:

* The expiration_time is the UTC time at which the temporary agent will be removed from the server.
* The lifetime_in_seconds is the amount of wall-clock time the temporary agent will remain active.
* The reservation_id is the string name by which the server(s) can refer to the temporary network.
  These names will consist of a human-readable prefix and a UUID suffix for uniqueness.

---

## Architecture Overview

### Frontman Agent: copy_cat

- Main entry point for user inquiry. Requires at least a valid network name to copy.

- Interprets natural language queries and delegates tasks to the copyist tool.

### Tool: copyist

This agent is a CodedTool that performs the required work of:

1. Checking for network name validity, given the system it is running on.
2. Creating a temporary copy of the target network by reading the hocon file from the filesystem.
3. Creating the temporary network via the ReservationUtil.wait_for_one() helper method.
4. Assmebling the sly_data response per the convention described above.
5. Optionally calling the temporary network with input the front man's parsing of the request
   In order to do this successfully, the CodedTool must derive from both BranchActivation and CodedTool
   ot gain access to the use_reservation() method.

#### Tool Arguments and Parameters

- `agent_name`: The name of the agent to copy

- `call_text`: An optional string to pass as input to the new agent.

---

## Debugging Hints

When developing or debugging with OpenAI models, keep the following in mind:

- **API Key Validation**: Ensure your `OPENAI_API_KEY` is valid and has access to preview tools.

- **Rate Limits**: Be aware of API rate limits that may affect LLM calling frequency.

- **Turn on server processing of temporary networks**: Set `AGENT_TEMPORARY_NETWORK_UPDATE_PERIOD_SECONDS` as above.

### Common Issues

- **Import Errors**: Ensure langchain-openai is installed

- **Authentication Failures**: Verify API key is set and valid

- **Model Errors**: Confirm the specified GPT model is accessible

- **AGENT_TEMPORARY_NETWORK_UPDATE_PERIOD_SECONDS not set Errors**: Ensure the environment variable is set as described above

- **Agent network .hocon file not found Errors**: Look for typos in your network name you wanted to copy.
  Be sure the .hocon file exists in the filesystem.  If you have copy/pasted this example be sure the
  registries_dir variable in the copyist.py has the correct path_to_basis to your own AGENT_MANIFEST_FILE.


---

## Resources

- [Coded Tools Implementation Guide](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/user_guide.md#coded-tools)
  Learn how to implement and integrate custom coded tools in Neuro-SAN Studio.

- [ReservationUtil helper class](https://github.com/cognizant-ai-lab/neuro-san/blob/main/neuro_san/internals/reservations/reservation_util.py)
  Learn how to use the ReservationUtil helper class in Neuro-SAN.  This is the simplest entrypoint into createing temporary networks and it is what the copyist tool uses.

- [Reservationist.py interface class](https://github.com/cognizant-ai-lab/neuro-san/blob/main/neuro_san/interfaces/reservationist.py)
  The system object to call that is passed in as an argument for your coded tool to create temporary agent reservations with.  Class comments here describe its intended use if you want more complicated uses cases that are afforded in ReservationUtil.

- [Reservation.py interface class](https://github.com/cognizant-ai-lab/neuro-san/blob/main/neuro_san/interfaces/reservation.py)
  The basis for information returned from the system about Reservations for temporary networks.

