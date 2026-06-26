# chat

Chat with an agent network directly from the command line, without starting neuro-san and nsflow servers.
This command delegates to neuro-san's `AgentCli` (also available as `python -m neuro_san.client.agent_cli`).

By default it uses a **direct** (in-process library) connection, meaning no server needs to be running. For remote
agents, specify `--connection https` with `--host` and `--port`.

Under the hood this command delegates to neuro-san's `AgentCli`, so it stays in sync with the library's capabilities.

## Usage

```bash
# Interactive chat with an agent (direct/library connection, no server needed)
ns chat basic/music_nerd

# One-shot mode: send a prompt from a file and exit
ns chat basic/music_nerd --one-shot --first_prompt_file prompt.txt

# Connect to a running neuro-san server
ns chat basic/music_nerd --connection http --host localhost --port 8080

# List all available agents
ns chat --list

# List agents filtered by tag
ns chat --tag tool

# Test connectivity of an agent network
ns chat basic/music_nerd --connectivity
```

The command exits with code `0` on normal completion (including user-initiated Ctrl+C) and `1` on error.

## Options

| Option | Description |
|---|---|
| `AGENT` | Name of the agent network to chat with (positional, default: `esp_decision_assistant`). |
| `--connection` | Connection type: `direct` (library call, default), `http`, or `https`. |
| `--host` | Hostname of the neuro-san server (for http/https connections). |
| `--port` | Port of the neuro-san server. |
| `--one-shot` | Send one prompt and exit (non-interactive mode). |
| `--list` | List all available agents and exit (ignores AGENT argument). |

## Advanced options

These options are forwarded directly to `AgentCli` and do not appear in `ns chat --help`.
Use `python -m neuro_san.client.agent_cli --help` for the full reference.

| Option | Description |
|---|---|
| `--first_prompt_file FILE` | File containing the first user prompt. |
| `--sly_data JSON` | JSON string with out-of-band data for the agent. |
| `--minimal` | Receive only minimal messages from the server. |
| `--maximal` | Receive all messages (default). |
| `--connectivity` | Test network connectivity instead of chatting. |
| `--tokens` | Print token accounting with every response. |
| `--thinking_file FILE` | Path for agent thinking output (default: `/tmp/agent_thinking.txt`). |
| `--no_thinking_file` | Disable thinking file output entirely. |
| `--tag TAG` | List agents matching a specific tag. |
| `--tags` | List all available tags. |
| `--max_input N` | Maximum rounds of input before exiting. |
| `--timeout SECONDS` | Connection timeout in seconds. |
| `--response_output_file FILE` | File to capture the agent's response. |

## Examples

### Direct connection (no server needed)

```bash
ns chat basic/music_nerd
```

This starts an interactive chat loop. The agent's description is printed first, then you
are prompted for input. Type `quit` to exit, or press Ctrl+C.

### Scripted one-shot usage

```bash
echo "Who wrote Little Black Submarines?" > /tmp/prompt.txt
ns chat music_nerd --one-shot --first_prompt_file /tmp/prompt.txt
```

### Remote server connection

```bash
ns chat basic/music_nerd --connection https --host my-server.example.com --port 443
```
