"""
Q&A script that calls the real neuro-san agent network.
1. POST to neuro-san HTTP server on GPU (soothsayer agent network)
2. Extract the soothsayer's final response
3. Send spoken response to audio server
"""
import json
import sys
import urllib.parse
import urllib.request

GPU_HOST = "54.201.115.165"
GPU_PORT = "8090"
AGENT_NAME = "semantic_density"
SSH_KEY = "/home/ubuntu/.ssh/devin_gpu"
AUDIO_URL = "http://localhost:8765"


def call_agent_network(question):
    """Call the neuro-san agent network via SSH tunnel to the HTTP API."""
    import subprocess
    payload = json.dumps({"user_message": {"text": question}, "chat_context": {}})
    curl_cmd = (
        f"curl -s --max-time 300 -X POST "
        f"http://localhost:{GPU_PORT}/api/v1/{AGENT_NAME}/streaming_chat "
        f"-H 'Content-Type: application/json' "
        f"-d '{payload}'"
    )
    cmd = [
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-i", SSH_KEY, f"donn@{GPU_HOST}",
        curl_cmd,
    ]
    print(f"[neuro-san] Calling agent network: {question}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"SSH/curl failed: {result.stderr}")
    # Parse all JSON responses (streaming — each line is a JSON object)
    responses = []
    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if line.startswith("{"):
            responses.append(json.loads(line))
    if not responses:
        raise RuntimeError(f"No JSON in response: {result.stdout}")
    return responses


def speak(text):
    """Send text to the audio server for TTS."""
    encoded = urllib.parse.urlencode({"text": text, "voice": "nova"})
    url = f"{AUDIO_URL}/speak?{encoded}"
    req = urllib.request.Request(url, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            print(f"[audio] {result}")
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        print(f"[audio] Failed to speak: {exc}")


def main():
    question = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Who is the greatest soccer player to ever live?"
    print(f"\n{'='*60}")
    print(f"Question: {question}")
    print(f"{'='*60}\n")

    # Call the real neuro-san agent network
    responses = call_agent_network(question)

    # Extract chat history to show agent flow
    last_response = responses[-1]
    chat_context = last_response.get("response", {}).get("chat_context", {})
    histories = chat_context.get("chat_histories", [])

    # Show each agent's messages
    for history in histories:
        origin = history.get("origin", [{}])
        agent_name = origin[0].get("tool", "unknown") if origin else "unknown"
        for msg in history.get("messages", []):
            msg_type = msg.get("type", "")
            msg_origin = msg.get("origin", [{}])
            msg_agent = msg_origin[0].get("tool", agent_name) if msg_origin else agent_name
            if msg_type == "AI":
                print(f"[{msg_agent}] {msg['text']}")

    # The final text from the soothsayer
    final_text = last_response.get("response", {}).get("text", "")
    print(f"\n[soothsayer final] {final_text}")

    # Speak it
    print("\n[audio] Speaking response...")
    speak(final_text)
    print("[audio] Done!")


if __name__ == "__main__":
    main()
