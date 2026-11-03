import asyncio
import base64
import json
import uuid
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types

from app.core.config import Settings
from app.core.knowledge import GREETING_TRIGGER, SYSTEM_PROMPT
from app.core.logger import logger
from app.services.session_manager import SessionManager


class GeminiLiveService:
    """
    Industry-standard service managing bi-directional live streaming sessions
    between the client WebSocket and the Google Gemini Live API.
    """

    def __init__(self, settings: Settings, session_manager: SessionManager):
        self.settings = settings
        self.session_manager = session_manager
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    async def handle_connection(self, websocket: WebSocket) -> None:
        session_id = uuid.uuid4().hex[:8]
        log_prefix = f"[{session_id}]"

        # 1. Enforce max concurrent sessions limit
        if not await self.session_manager.can_accept():
            logger.warning(f"{log_prefix} Concurrency cap reached. Rejecting connection.")
            await websocket.close(code=1013, reason="Server busy: max sessions limit reached")
            return

        await websocket.accept()
        await self.session_manager.register(session_id, websocket)

        # 2. Configure Gemini Live Audio session
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=types.Content(parts=[types.Part.from_text(SYSTEM_PROMPT)]),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self.settings.GEMINI_VOICE)
                )
            ),
        )

        logger.info(f"{log_prefix} Initializing Gemini Live session with model: {self.settings.GEMINI_MODEL}")

        try:
            # Wrap entire session in timeout watchdog
            async with asyncio.timeout(self.settings.MAX_SESSION_SECONDS):
                async with self.client.aio.live.connect(
                    model=self.settings.GEMINI_MODEL,
                    config=config,
                ) as gemini_session:
                    logger.info(f"{log_prefix} Gemini Live session established.")

                    # Notify browser client that session is ready
                    await websocket.send_json({"type": "ready"})

                    # Run bi-directional audio/event pumps concurrently
                    async with asyncio.TaskGroup() as tg:
                        upstream_task = tg.create_task(
                            self._upstream_pump(websocket, gemini_session, log_prefix)
                        )
                        downstream_task = tg.create_task(
                            self._downstream_pump(websocket, gemini_session, log_prefix)
                        )

        except TimeoutError:
            logger.info(f"{log_prefix} Session reached max duration limit ({self.settings.MAX_SESSION_SECONDS}s).")
            try:
                await websocket.send_json({
                    "type": "error",
                    "code": "session_limit",
                    "message": "Session time limit reached.",
                })
                await websocket.close(code=1000, reason="Session limit reached")
            except Exception:
                pass

        except WebSocketDisconnect:
            logger.info(f"{log_prefix} Client disconnected cleanly.")

        except Exception as e:
            logger.error(f"{log_prefix} Unexpected error in session: {type(e).__name__}: {e}")
            try:
                await websocket.send_json({
                    "type": "error",
                    "code": "upstream_error",
                    "message": "The voice service encountered an error. Please try again.",
                })
                await websocket.close(code=1011, reason="Internal server error")
            except Exception:
                pass

        finally:
            await self.session_manager.unregister(session_id)
            logger.info(f"{log_prefix} Session teardown complete.")

    async def _upstream_pump(self, websocket: WebSocket, gemini_session: any, log_prefix: str) -> None:
        """
        Receives binary PCM audio chunks and JSON control commands from the browser
        and routes them into the Gemini Live session.
        """
        while True:
            try:
                message = await websocket.receive()
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.warning(f"{log_prefix} Error reading client frame: {e}")
                break

            # Binary frame = 16 kHz mono PCM16 audio from client microphone
            if "bytes" in message and message["bytes"]:
                raw_pcm = message["bytes"]
                try:
                    await gemini_session.send(
                        input=types.LiveClientRealtimeInput(
                            media_chunks=[types.Blob(data=raw_pcm, mime_type="audio/pcm;rate=16000")]
                        )
                    )
                except Exception as e:
                    logger.warning(f"{log_prefix} Failed to send audio chunk to Gemini: {e}")
                    break

            # Text frame = JSON control message (e.g. {"type": "greet"} or {"type": "end"})
            elif "text" in message and message["text"]:
                try:
                    control = json.loads(message["text"])
                    cmd_type = control.get("type")

                    if cmd_type == "greet":
                        logger.info(f"{log_prefix} Triggering assistant greeting...")
                        await gemini_session.send(input=GREETING_TRIGGER, end_of_turn=True)
                    elif cmd_type == "end":
                        logger.info(f"{log_prefix} Client requested graceful session end.")
                        break
                except json.JSONDecodeError:
                    logger.warning(f"{log_prefix} Received invalid JSON text frame: {message['text']}")

    async def _downstream_pump(self, websocket: WebSocket, gemini_session: any, log_prefix: str) -> None:
        """
        Streams audio responses, speech transcriptions, and status events from Gemini Live
        back to the browser WebSocket client.
        """
        try:
            async for server_msg in gemini_session.receive():
                sc = server_msg.server_content
                if not sc:
                    continue

                # 1. Stream synthesized audio chunks (24 kHz PCM16)
                if sc.model_turn and sc.model_turn.parts:
                    for part in sc.model_turn.parts:
                        # CRITICAL: Ignore internal thinking/reasoning parts so thoughts are never shown to user
                        if getattr(part, "thought", False):
                            continue

                        # Stream audio PCM data
                        if part.inline_data and part.inline_data.data:
                            audio_data = part.inline_data.data
                            if isinstance(audio_data, str):
                                audio_bytes = base64.b64decode(audio_data)
                            else:
                                audio_bytes = audio_data

                            await websocket.send_bytes(audio_bytes)

                        # Stream text transcript if present in parts
                        if part.text:
                            # Strip out any markdown header artifacts if present
                            clean_text = part.text.strip()
                            if clean_text:
                                await websocket.send_json({
                                    "type": "transcript",
                                    "role": "assistant",
                                    "text": clean_text,
                                })

                # 2. Interruption event (barge-in detected)
                if sc.interrupted:
                    await websocket.send_json({"type": "interrupted"})

                # 3. Speech-to-text transcriptions (if supported by active model)
                input_tx = getattr(sc, "input_transcription", None)
                if input_tx and getattr(input_tx, "text", None):
                    await websocket.send_json({
                        "type": "transcript",
                        "role": "user",
                        "text": input_tx.text,
                    })

                output_tx = getattr(sc, "output_transcription", None)
                if output_tx and getattr(output_tx, "text", None):
                    await websocket.send_json({
                        "type": "transcript",
                        "role": "assistant",
                        "text": output_tx.text,
                    })

                # 4. Turn complete event
                if sc.turn_complete:
                    await websocket.send_json({"type": "turnComplete"})

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"{log_prefix} Downstream pump finished with {type(e).__name__}: {e}")

