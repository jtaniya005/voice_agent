# Mission SSB Voice API (FastAPI + Gemini Live)

Standalone high-performance real-time conversational voice assistant backend microservice for Mission SSB, powered by Google Gemini Live Audio API (`gemini-2.5-flash-native-audio-preview-12-2025`).

This repository contains the pure backend API service, ready for 1-click deployment on **Render** (or any cloud/Docker provider).

---

## Architecture & Features

- **Gemini Live Bi-directional WebSocket**: Streams 16 kHz PCM microphone input upstream and streams back 24 kHz synthesized speech downstream.
- **FastAPI + Uvicorn ASGI Runner**: Low-latency async architecture with graceful lifespan management.
- **Pure ASGI Security Headers & CORS**: Supports cross-origin access (`ALLOWED_ORIGINS=*` by default) so it can be called from any external web app, mobile app, or frontend project.
- **Monitoring & Telemetry**: Built-in `/healthz` and `/readyz` endpoints for liveness/readiness probes.
- **Render Ready**: Native Python Web Service with `render.yaml` blueprint and dynamic `$PORT` binding.

```
External Project (React / Next.js / Mobile)
        │
        ├── HTTP GET  /docs, /healthz, /readyz
        └── WSS       /live (PCM Audio + JSON Events)
                │
         Mission SSB Voice API (FastAPI)
                │
          Gemini Live API (gemini-2.5-flash-native-audio-preview-12-2025)
```

---

## API Endpoints

| Endpoint | Protocol | Description |
| :--- | :--- | :--- |
| `GET /` | HTTP | Service metadata & root information |
| `GET /healthz` | HTTP | Telemetry, active sessions count, model, uptime |
| `GET /readyz` | HTTP | Readiness probe checking `GEMINI_API_KEY` configuration |
| `GET /docs` | HTTP | Interactive Swagger UI API documentation |
| `WS  /live` | WebSocket | Bi-directional real-time voice streaming endpoint |

---

## WebSocket Protocol (`/live`)

### 1. Handshake & Initialization
When your client opens a WebSocket connection to `wss://<YOUR-RENDER-URL>/live`:
- Server sends: `{"type": "ready"}`
- Client sends: `{"type": "greet"}` (to trigger the assistant's introductory voice greeting)

### 2. Audio Streaming
- **Upstream (Client ➔ Server)**: Send raw binary PCM 16-bit, 16 kHz, mono chunks from microphone.
- **Downstream (Server ➔ Client)**: Server sends raw binary PCM 16-bit, 24 kHz, mono chunks to play via Web Audio API.

### 3. Events Sent by Server
- `{"type": "ready"}` — Session connected to Gemini Live.
- `{"type": "transcript", "role": "assistant" | "user", "text": "..."}` — Speech-to-text transcript.
- `{"type": "interrupted"}` — User interrupted the assistant (stop playing audio queue immediately).
- `{"type": "turnComplete"}` — Assistant finished speaking current response.
- `{"type": "error", "code": "...", "message": "..."}` — Error notice.

---

## Deploy to Render (Step-by-Step)

### Option A: Standard Render Web Service (Recommended)
1. Push this repository to your **GitHub** / **GitLab**.
2. Log in to [Render Dashboard](https://dashboard.render.com).
3. Click **New +** ➔ **Web Service**.
4. Connect your repository.
5. Fill in the service details:
   - **Name**: `mission-ssb-voice-api`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
6. Under **Environment Variables**, add:
   - `GEMINI_API_KEY` = *[Your Google Gemini API Key]*
   - `GEMINI_MODEL` = `gemini-2.5-flash-native-audio-preview-12-2025`
   - `GEMINI_VOICE` = `Fenrir`
   - `ALLOWED_ORIGINS` = `*`
   - `ENVIRONMENT` = `production`
7. Click **Create Web Service**. Render will deploy your API and give you a live URL like:
   `https://mission-ssb-voice-api.onrender.com`

### Option B: Render Blueprint
Use the included `render.yaml` for automatic 1-click infrastructure deployment.

---

## Connecting from Another Project

Once deployed, use your Render URL in your other frontend / project:

```javascript
// HTTP Base URL: https://mission-ssb-voice-api.onrender.com
// WebSocket URL: wss://mission-ssb-voice-api.onrender.com/live

const ws = new WebSocket("wss://<YOUR-RENDER-DOMAIN>/live");

ws.onopen = () => {
  console.log("Connected to Mission SSB Voice Guide API");
};

ws.onmessage = async (event) => {
  if (event.data instanceof Blob) {
    // Binary PCM audio (24 kHz, 16-bit mono) from Gemini
    const pcmBuffer = await event.data.arrayBuffer();
    // Play buffer using Web Audio AudioContext...
  } else {
    // Control / transcript event
    const message = JSON.parse(event.data);
    if (message.type === "ready") {
      // Trigger voice greeting
      ws.send(JSON.stringify({ type: "greet" }));
    } else if (message.type === "transcript") {
      console.log(`[${message.role}]:`, message.text);
    } else if (message.type === "interrupted") {
      // Flush client audio playback buffer
    }
  }
};

// Send microphone chunk (16 kHz PCM 16-bit mono ArrayBuffer / Int16Array)
function sendAudioChunk(int16Chunk) {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(int16Chunk.buffer);
  }
}
```

---

## Local Development

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run local development server
python run.py
# Or: uvicorn app.main:app --reload --port 8000
```

- Swagger UI: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/healthz`
