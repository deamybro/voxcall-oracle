from __future__ import annotations

import asyncio
import os
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

TranscriptCallback = Callable[[str], Awaitable[None]]
CHUNK_SIZE = 4096


async def replay_demo(callback: TranscriptCallback, delay: float = 1.25) -> None:
    chunks = [
        "[CEO] Nvidia delivered record data center revenue and raised guidance for next quarter.",
        "[CFO] Gross margin expansion remained strong, with demand accelerating across enterprise customers.",
        "[Analyst] Can you comment on supply constraints and whether the guidance includes that risk?",
        "[CEO] Supply remains tight but improving, and we expect continued growth through the second half.",
    ]
    for chunk in chunks:
        await callback(chunk)
        await asyncio.sleep(delay)


async def start_listening(callback: TranscriptCallback) -> None:
    api_key = os.getenv("SPEECHMATICS_API_KEY")
    if not api_key:
        await replay_demo(callback)
        return

    try:
        from speechmatics.rt import (
            AsyncClient,
            AudioEncoding,
            AudioFormat,
            Microphone,
            ServerMessageType,
            TranscriptionConfig,
            TranscriptResult,
        )
    except ImportError as exc:
        raise RuntimeError("speechmatics-rt is not installed. Run `pip install -r requirements.txt`.") from exc

    client = AsyncClient(api_key=api_key)
    microphone = Microphone(sample_rate=16000, chunk_size=CHUNK_SIZE)
    config = TranscriptionConfig(
        language="en",
        enable_partials=False,
        max_delay=2,
    )

    @client.on(ServerMessageType.ADD_TRANSCRIPT)
    def on_final(message):
        result = TranscriptResult.from_message(message)
        text = result.metadata.transcript
        if text:
            speaker = getattr(result.metadata, "speaker", None) or "speaker"
            asyncio.create_task(callback(f"[{speaker}] {text}"))

    audio_format = AudioFormat(
        encoding=AudioEncoding.PCM_S16LE,
        chunk_size=CHUNK_SIZE,
        sample_rate=16000,
    )
    if not microphone.start():
        await client.close()
        raise RuntimeError("Microphone could not start. Check PyAudio and audio device access.")

    try:
        await client.start_session(transcription_config=config, audio_format=audio_format)
        while True:
            await client.send_audio(await microphone.read(CHUNK_SIZE))
    finally:
        microphone.stop()
        await client.close()


async def transcribe_audio_file(path: str | Path) -> list[str]:
    api_key = os.getenv("SPEECHMATICS_API_KEY")
    if not api_key:
        return [
            "[CEO] Demo upload mode active because SPEECHMATICS_API_KEY is not configured.",
            "[CFO] Revenue beat expectations and guidance was raised for the next quarter.",
        ]

    try:
        from speechmatics.batch import AsyncClient, JobConfig, JobType, TranscriptionConfig
    except ImportError as exc:
        raise RuntimeError("speechmatics-batch is not installed. Run `pip install -r requirements.txt`.") from exc

    async with AsyncClient(api_key=api_key) as client:
        config = JobConfig(
            type=JobType.TRANSCRIPTION,
            transcription_config=TranscriptionConfig(
                language="en",
                diarization="speaker",
            ),
        )
        job = await client.submit_job(str(path), config=config)
        result = await client.wait_for_completion(
            job.id,
            polling_interval=2.0,
            timeout=300.0,
        )

    lines: list[str] = []
    current_speaker = None
    current_words: list[str] = []

    for item in getattr(result, "results", []) or []:
        alternatives = getattr(item, "alternatives", None) or []
        if not alternatives:
            continue
        alternative = alternatives[0]
        speaker = getattr(alternative, "speaker", None) or "speaker"
        content = getattr(alternative, "content", "")
        if not content:
            continue
        if speaker != current_speaker and current_words:
            lines.append(f"[{current_speaker}] {' '.join(current_words)}")
            current_words = []
        current_speaker = speaker
        current_words.append(content)

    if current_words:
        lines.append(f"[{current_speaker}] {' '.join(current_words)}")

    transcript_text = getattr(result, "transcript_text", "")
    if not lines and transcript_text:
        for chunk in _chunk_transcript_text(transcript_text):
            lines.append(f"[speaker] {chunk}")

    return lines


def _chunk_transcript_text(transcript_text: str, max_chars: int = 260) -> list[str]:
    text = " ".join(transcript_text.split())
    if not text:
        return []

    chunks: list[str] = []
    current = ""
    for sentence in re_split_sentences(text):
        candidate = f"{current} {sentence}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks


def re_split_sentences(text: str) -> list[str]:
    import re

    parts = re.split(r"(?<=[.!?])\s+", text)
    return [part.strip() for part in parts if part.strip()]


async def transcribe_uploaded_bytes(filename: str, data: bytes) -> list[str]:
    suffix = Path(filename).suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        return await transcribe_audio_file(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
