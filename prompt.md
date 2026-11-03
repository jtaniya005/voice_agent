# Integration Prompt for Landing Page AI Voice Assistant

Use this prompt with any AI coding assistant (Cursor, ChatGPT, Claude, Antigravity) or share it with your frontend developer to integrate the voice assistant into your website's landing page.

---

```markdown
I want to add a real-time conversational AI Voice Assistant widget to the landing page of my website.

My voice backend API is already deployed and live on Render:
- WebSocket URL: wss://voice-agent-q4f0.onrender.com/live
- Health Check: https://voice-agent-q4f0.onrender.com/healthz

Please build a modern, high-converting Voice Assistant component on the landing page (either as a Hero section interactive card or a floating bottom-right widget) with the following specifications:

### 1. UI & User Experience Requirements:
- Modern glassmorphic or dark/light aesthetic matching a premium landing page.
- "Talk to AI Voice Mentor" / "Start Voice Chat" CTA button.
- When active:
  - Show a pulsating voice visualizer / audio wave animation while listening or speaking.
  - Live captions / transcript display showing what the AI and the user are saying in real time.
  - Clear Mute Mic and Disconnect buttons.
  - Status indicator (Connecting, Listening, Speaking, Disconnected).

### 2. Audio & WebSocket Technical Protocol:
- **WebSocket Endpoint**: `wss://voice-agent-q4f0.onrender.com/live`
- **Microphone Capture (Client -> Server)**:
  - Capture user audio at 16,000 Hz (16 kHz), 16-bit Linear PCM, 1 channel (mono).
  - Stream raw binary chunks through the WebSocket while user is unmuted.
- **Audio Playback (Server -> Client)**:
  - Server streams binary chunks of 24,000 Hz (24 kHz), 16-bit Linear PCM, 1 channel (mono).
  - Play back these audio buffers smoothly with zero jitter/gap using Web Audio API (`AudioContext`).
- **JSON Control & Event Frames**:
  - When server sends `{"type": "ready"}`, client should send `{"type": "greet"}` to initiate the mentor's greeting.
  - When server sends `{"type": "transcript", "role": "assistant" | "user", "text": "..."}`, display it as live captions.
  - When server sends `{"type": "interrupted"}`, immediately stop and clear the current audio playback queue (barge-in support).
  - When server sends `{"type": "turnComplete"}`, indicate that the AI has finished its turn.
  - When user clicks Disconnect, send `{"type": "end"}` and close the WebSocket cleanly.

Please provide the complete, clean, self-contained component code (with audio processor worklet/script if needed) and explain how to embed it into my landing page.
```
