#!/usr/bin/env python3
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

"""
WebSocket audio streaming server for the FedEx Day demo.

Exposes a /speak endpoint that generates TTS via OpenAI and streams
the audio to all connected browser clients via WebSocket.

Usage:
    python demo_audio_server.py

    Then open the public URL in a browser to connect.
    POST /speak?text=Hello&voice=nova to send narration.
"""

import logging
import os
from typing import Set

from fastapi import FastAPI
from fastapi import Query
from fastapi import WebSocket
from fastapi import WebSocketDisconnect
from fastapi.responses import HTMLResponse
from openai import AsyncOpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Demo Audio Server")

# Connected WebSocket clients
connected_clients: Set[WebSocket] = set()

# OpenAI client (uses OPENAI_API_KEY from environment)
openai_client = AsyncOpenAI()

# Default voice
DEFAULT_VOICE = "nova"

# HTML page served to browsers for audio playback
PLAYER_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Semantic Density Demo — Audio</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #1a1a2e;
            color: #e0e0e0;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
        }
        h1 {
            color: #00d4ff;
            font-size: 1.5em;
            margin-bottom: 10px;
        }
        #status {
            color: #4caf50;
            font-size: 1.1em;
            margin: 10px 0;
        }
        #transcript {
            background: #16213e;
            border-radius: 12px;
            padding: 20px;
            max-width: 600px;
            width: 100%;
            min-height: 200px;
            max-height: 400px;
            overflow-y: auto;
            margin-top: 20px;
        }
        .transcript-entry {
            padding: 8px 0;
            border-bottom: 1px solid #2a2a4a;
            animation: fadeIn 0.3s ease-in;
        }
        .transcript-entry:last-child { border-bottom: none; }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(5px); }
            to { opacity: 1; transform: translateY(0); }
        }
        #unlock-btn {
            background: #00d4ff;
            color: #1a1a2e;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 1.1em;
            cursor: pointer;
            margin: 20px 0;
        }
        #unlock-btn:hover { background: #00b8d4; }
        #unlock-btn.hidden { display: none; }
    </style>
</head>
<body>
    <h1>Semantic Density Demo</h1>
    <div id="status">Connecting...</div>
    <button id="unlock-btn" onclick="unlockAudio()">Click to Enable Audio</button>
    <div id="transcript"></div>

    <script>
        let audioContext = null;
        let audioUnlocked = false;
        const audioQueue = [];
        let isPlaying = false;

        function unlockAudio() {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            audioUnlocked = true;
            document.getElementById('unlock-btn').classList.add('hidden');
            document.getElementById('status').textContent = 'Audio enabled — waiting for narration...';
            processQueue();
        }

        function addTranscript(text) {
            const div = document.getElementById('transcript');
            const entry = document.createElement('div');
            entry.className = 'transcript-entry';
            entry.textContent = text;
            div.appendChild(entry);
            div.scrollTop = div.scrollHeight;
        }

        async function playAudio(arrayBuffer) {
            if (!audioContext) return;
            try {
                const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
                const source = audioContext.createBufferSource();
                source.buffer = audioBuffer;
                source.connect(audioContext.destination);
                source.onended = () => {
                    isPlaying = false;
                    processQueue();
                };
                source.start(0);
                isPlaying = true;
            } catch (e) {
                console.error('Audio decode error:', e);
                isPlaying = false;
                processQueue();
            }
        }

        function processQueue() {
            if (isPlaying || audioQueue.length === 0) return;
            const next = audioQueue.shift();
            playAudio(next);
        }

        // WebSocket connection
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${protocol}//${location.host}/ws`);
        ws.binaryType = 'arraybuffer';

        ws.onopen = () => {
            document.getElementById('status').textContent =
                audioUnlocked ? 'Connected — waiting for narration...' : 'Connected — click button to enable audio';
        };

        ws.onmessage = (event) => {
            if (typeof event.data === 'string') {
                // Text message = transcript
                addTranscript(event.data);
                document.getElementById('status').textContent = 'Speaking...';
            } else {
                // Binary message = audio data
                audioQueue.push(event.data);
                if (audioUnlocked) processQueue();
            }
        };

        ws.onclose = () => {
            document.getElementById('status').textContent = 'Disconnected';
            document.getElementById('status').style.color = '#f44336';
        };
    </script>
</body>
</html>
"""


@app.get("/")
async def get_player():
    """Serve the audio player HTML page."""
    return HTMLResponse(PLAYER_HTML)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket connections from browser clients."""
    await websocket.accept()
    connected_clients.add(websocket)
    logger.info("Client connected. Total clients: %d", len(connected_clients))
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_clients.discard(websocket)
        logger.info("Client disconnected. Total clients: %d", len(connected_clients))


@app.post("/speak")
async def speak(
    text: str = Query(..., description="Text to speak"),
    voice: str = Query(DEFAULT_VOICE, description="OpenAI TTS voice"),
):
    """Generate TTS and stream to all connected clients."""
    if not connected_clients:
        return {"status": "no_clients", "message": "No browser clients connected"}

    logger.info("Speaking: %s (voice=%s)", text[:60], voice)

    # Generate TTS audio
    response = await openai_client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text,
        response_format="mp3",
    )

    audio_bytes = response.content

    # Broadcast transcript text and audio to all connected clients
    disconnected = set()
    for client in connected_clients:
        try:
            await client.send_text(text)
            await client.send_bytes(audio_bytes)
        except (ConnectionError, RuntimeError):
            disconnected.add(client)

    connected_clients.difference_update(disconnected)

    return {
        "status": "ok",
        "text": text,
        "voice": voice,
        "audio_bytes": len(audio_bytes),
        "clients": len(connected_clients),
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("DEMO_AUDIO_PORT", "8765"))
    uvicorn.run(app, host="0.0.0.0", port=port)
