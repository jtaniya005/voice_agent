import asyncio
import base64
import json
import uuid
from typing import Any, Dict, Optional
from fastapi import WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types

from app.core.config import Settings
from app.core.knowledge import GREETING_TRIGGER, SYSTEM_PROMPT
from app.core.logger import logger
from app.services.session_manager import SessionManager
from app.skills import (
    create_initial_state,
    prompt_manager,
    transition_skill,
)


class GeminiLiveService:
    """
    Industry-standard service managing bi-directional live streaming sessions
    between the client WebSocket and the Google Gemini Live API.
    Enhanced with LangGraph state orchestration and modular skills.
    """

    def __init__(self, settings: Settings, session_manager: SessionManager):
        self.settings = settings
        self.session_manager = session_manager
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.candidate_state = create_initial_state(language="hinglish")

    def _build_tools_config(self) -> types.Tool:
        """
        Registers real-time function calling tools for dynamic SSB skill switching.
        Domain restricted strictly to SSB (Services Selection Board).
        """
        return types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="switch_skill",
                    description=(
                        "Call this when the conversation shifts focus to an SSB skill: "
                        "'roadmap' (5-day SSB stages, OIR, PPDT, GTO, Psych), "
                        "'checklist' (reporting items, documents, kit), "
                        "'mock_interview' (15 OLQ parameters, IO interview details), "
                        "'motivation' (defense battle cries, overcoming screening fears), or "
                        "'onboarding' (SSB Journey portal overview & briefing)."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "new_skill": types.Schema(
                                type=types.Type.STRING,
                                description="The detected SSB skill: 'roadmap', 'checklist', 'mock_interview', 'motivation', or 'onboarding'",
                            ),
                            "reason": types.Schema(
                                type=types.Type.STRING,
                                description="Brief reason for switching SSB skill",
                            ),
                        },
                        required=["new_skill"],
                    ),
                ),
            ]
        )

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

        # 2. Configure Gemini Live Audio session with tools & modular system prompt
        skill_tool = self._build_tools_config()
        active_system_prompt = prompt_manager.get_unified_mentor_prompt(language="hinglish")

        # Support ?voice= query param or default to Aoede (light, clear female voice)
        query_voice = None
        if hasattr(websocket, "query_params") and websocket.query_params:
            query_voice = websocket.query_params.get("voice")
        voice_to_use = query_voice or (
            "Aoede" if self.settings.GEMINI_VOICE in ["Fenrir", "", None] else self.settings.GEMINI_VOICE
        )
        logger.info(f"{log_prefix} Initializing Gemini Live session with model: {self.settings.GEMINI_MODEL} | Voice: {voice_to_use}")

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=types.Content(parts=[types.Part.from_text(text=active_system_prompt)]),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_to_use)
                )
            ),
            tools=[skill_tool],
        )

        try:
            # Wrap entire session in timeout watchdog
            async with asyncio.timeout(self.settings.MAX_SESSION_SECONDS):
                async with self.client.aio.live.connect(
                    model=self.settings.GEMINI_MODEL,
                    config=config,
                ) as gemini_session:
                    logger.info(f"{log_prefix} Gemini Live session established.")

                    # Notify browser client that session is ready
                    await websocket.send_json({
                        "type": "ready",
                        "portal": "SSB Journey",
                        "current_skill": self.candidate_state.get("current_skill", "onboarding"),
                    })

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
        greeting_cooldown_until = 0.0
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
                if asyncio.get_running_loop().time() < greeting_cooldown_until:
                    continue
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

            # Text frame = JSON control message
            elif "text" in message and message["text"]:
                try:
                    control = json.loads(message["text"])
                    cmd_type = control.get("type")

                    if cmd_type == "greet":
                        logger.info(f"{log_prefix} Triggering assistant greeting...")
                        greeting_cooldown_until = asyncio.get_running_loop().time() + 1.5
                        await gemini_session.send(input=GREETING_TRIGGER, end_of_turn=True)

                    elif cmd_type == "switch_skill":
                        # Client initiated skill switch (e.g. user clicked a skill tab on UI)
                        target_skill = control.get("skill", "roadmap")
                        logger.info(f"{log_prefix} Client requested skill switch to: {target_skill}")
                        self.candidate_state = transition_skill(
                            self.candidate_state,
                            intent=target_skill,
                            reason="Client requested skill switch",
                        )
                        await websocket.send_json({
                            "type": "skill_switched",
                            "skill": self.candidate_state.get("current_skill", target_skill),
                            "reason": "Client UI selection",
                        })

                    elif cmd_type == "set_details":
                        # Client updated details via form
                        details = control.get("details", {})
                        self.candidate_state = transition_skill(
                            self.candidate_state,
                            details=details,
                            reason="Client updated details",
                        )
                        c_info = self._get_candidate_info_dict()
                        await websocket.send_json({
                            "type": "candidate_updated",
                            "details": c_info,
                            "is_complete": bool(c_info.get("name") and c_info.get("target_entry")),
                        })

                    elif cmd_type == "end":
                        logger.info(f"{log_prefix} Client requested graceful session end.")
                        break

                except json.JSONDecodeError:
                    logger.warning(f"{log_prefix} Received invalid JSON text frame: {message['text']}")

    async def _downstream_pump(self, websocket: WebSocket, gemini_session: any, log_prefix: str) -> None:
        """
        Streams audio responses, speech transcriptions, function call handling,
        and status events from Gemini Live back to the browser WebSocket client.
        """
        try:
            async for server_msg in gemini_session.receive():
                # 1. Handle Function Calls / Tools
                tool_call = getattr(server_msg, "tool_call", None)
                if tool_call and getattr(tool_call, "function_calls", None):
                    for call in tool_call.function_calls:
                        if call.name == "switch_skill":
                            new_skill = str(call.args.get("new_skill", "roadmap")).lower().strip()
                            reason = str(call.args.get("reason", "Conversation topic shifted"))
                            logger.info(f"{log_prefix} Tool switch_skill triggered -> {new_skill} ({reason})")

                            # Execute LangGraph transition
                            self.candidate_state = transition_skill(
                                self.candidate_state,
                                intent=new_skill,
                                reason=reason,
                            )

                            # Notify frontend
                            await websocket.send_json({
                                "type": "skill_switched",
                                "skill": self.candidate_state.get("current_skill", new_skill),
                                "reason": reason,
                            })

                            # Confirm tool response to Gemini Live session
                            await gemini_session.send(
                                input=types.LiveClientToolResponse(
                                    function_responses=[
                                        types.FunctionResponse(
                                            name=call.name,
                                            id=call.id,
                                            response={"status": "switched", "current_skill": new_skill},
                                        )
                                    ]
                                )
                            )

                        elif call.name == "save_candidate_details":
                            args = call.args or {}
                            logger.info(f"{log_prefix} Tool save_candidate_details triggered with: {args}")

                            # Execute LangGraph state update
                            self.candidate_state = transition_skill(
                                self.candidate_state,
                                details=args,
                                reason="Extracted from candidate speech",
                            )

                            c_info = self._get_candidate_info_dict()
                            is_complete = bool(c_info.get("name") and c_info.get("target_entry"))

                            # Broadcast candidate details update to frontend
                            await websocket.send_json({
                                "type": "candidate_updated",
                                "details": c_info,
                                "is_complete": is_complete,
                            })

                            # Confirm silent tool response to Gemini
                            await gemini_session.send(
                                input=types.LiveClientToolResponse(
                                    function_responses=[
                                        types.FunctionResponse(
                                            name=call.name,
                                            id=call.id,
                                            response={"status": "recorded"},
                                        )
                                    ]
                                )
                            )

                # 2. Server Content: Audio and Transcripts
                sc = server_msg.server_content
                if not sc:
                    continue

                # Stream synthesized audio chunks (24 kHz PCM16)
                if sc.model_turn and sc.model_turn.parts:
                    for part in sc.model_turn.parts:
                        # Ignore internal thinking/reasoning parts so thoughts are never shown to user
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
                            clean_text = part.text.strip()
                            if clean_text:
                                await websocket.send_json({
                                    "type": "transcript",
                                    "role": "assistant",
                                    "text": clean_text,
                                })

                # Interruption event (barge-in detected)
                if sc.interrupted:
                    await websocket.send_json({"type": "interrupted"})

                # Speech-to-text transcriptions
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

                # Turn complete event
                if sc.turn_complete:
                    c_info = self._get_candidate_info_dict()
                    await websocket.send_json({
                        "type": "turnComplete",
                        "current_skill": self.candidate_state.get("current_skill", "onboarding"),
                        "details": c_info,
                    })

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"{log_prefix} Downstream pump finished with {type(e).__name__}: {e}")

    def _get_candidate_info_dict(self) -> Dict[str, Optional[str]]:
        return {
            "name": self.candidate_state.get("candidate_name"),
            "target_entry": self.candidate_state.get("target_entry"),
            "ssb_board": self.candidate_state.get("ssb_board"),
            "attempt_type": self.candidate_state.get("attempt_type"),
        }
