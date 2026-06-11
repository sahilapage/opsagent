from __future__ import annotations
import json
import base64
import structlog
from fastapi import WebSocket, WebSocketDisconnect
from agents.orchestrator import run_agent
from voice.stt import transcribe_audio
from voice.tts import text_to_speech

log = structlog.get_logger()


async def voice_ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    log.info("voice_ws_connected")
    user_id = "default"
    session_id = None

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            msg_type = message.get("type")

            # Set user context
            if msg_type == "init":
                user_id = message.get("user_id", "default")
                session_id = message.get("session_id")
                await websocket.send_text(json.dumps({
                    "type": "ready",
                    "message": "Voice session started"
                }))

            # Handle text query
            elif msg_type == "text":
                task = message.get("text", "")
                await websocket.send_text(json.dumps({
                    "type": "thinking",
                    "message": "Processing..."
                }))

                result = run_agent(task=task, user_id=user_id, session_id=session_id)
                answer = result.get("answer", "I could not process that.")

                # Send text response
                await websocket.send_text(json.dumps({
                    "type": "text_response",
                    "answer": answer,
                    "agent_used": result.get("agent_used"),
                    "session_id": result.get("session_id"),
                }))

                # Send audio response
                try:
                    audio_bytes = text_to_speech(answer)
                    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                    await websocket.send_text(json.dumps({
                        "type": "audio_response",
                        "audio_b64": audio_b64,
                        "format": "mp3",
                    }))
                except Exception as e:
                    log.error("tts_error", error=str(e))
                    await websocket.send_text(json.dumps({
                        "type": "tts_error",
                        "message": str(e)
                    }))

            # Handle audio query
            elif msg_type == "audio":
                audio_b64 = message.get("audio_b64", "")
                audio_bytes = base64.b64decode(audio_b64)

                await websocket.send_text(json.dumps({
                    "type": "transcribing",
                    "message": "Transcribing audio..."
                }))

                # STT
                try:
                    transcript = transcribe_audio(audio_bytes)
                    await websocket.send_text(json.dumps({
                        "type": "transcript",
                        "text": transcript,
                    }))
                except Exception as e:
                    await websocket.send_text(json.dumps({
                        "type": "stt_error",
                        "message": str(e)
                    }))
                    continue

                # Run agent
                await websocket.send_text(json.dumps({
                    "type": "thinking",
                    "message": "Processing..."
                }))
                result = run_agent(task=transcript, user_id=user_id, session_id=session_id)
                answer = result.get("answer", "I could not process that.")

                await websocket.send_text(json.dumps({
                    "type": "text_response",
                    "answer": answer,
                    "agent_used": result.get("agent_used"),
                    "transcript": transcript,
                }))

                # TTS
                try:
                    audio_bytes = text_to_speech(answer)
                    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                    await websocket.send_text(json.dumps({
                        "type": "audio_response",
                        "audio_b64": audio_b64,
                        "format": "mp3",
                    }))
                except Exception as e:
                    log.error("tts_error", error=str(e))

    except WebSocketDisconnect:
        log.info("voice_ws_disconnected")
    except Exception as e:
        log.error("voice_ws_error", error=str(e))
        await websocket.close()
