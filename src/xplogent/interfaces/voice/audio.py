"""Voice I/O: record → Whisper STT → agent → TTS.

All audio dependencies are optional (install the ``voice`` extra). Each helper
degrades to a clear message if its backend is missing, so importing this module
never fails.
"""

from __future__ import annotations

import asyncio

_SAMPLE_RATE = 16000
_whisper_model = None


def record(seconds: int = 6, sample_rate: int = _SAMPLE_RATE):
    """Record from the default microphone. Returns (samples, rate) or None."""
    try:
        import sounddevice as sd  # type: ignore
    except ImportError:
        print("Install the voice extra: pip install 'xplogent[voice]'")
        return None
    print(f"🎙  recording {seconds}s…")
    audio = sd.rec(int(seconds * sample_rate), samplerate=sample_rate, channels=1, dtype="float32")
    sd.wait()
    return audio.flatten(), sample_rate


def transcribe(samples, sample_rate: int = _SAMPLE_RATE) -> str:
    """Transcribe audio samples with faster-whisper."""
    global _whisper_model
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError:
        return ""
    if _whisper_model is None:
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = _whisper_model.transcribe(samples, sampling_rate=sample_rate)
    return " ".join(seg.text for seg in segments).strip()


def speak(text: str) -> None:
    """Speak text aloud via pyttsx3 (offline)."""
    try:
        import pyttsx3  # type: ignore
    except ImportError:
        print(f"[tts unavailable] {text}")
        return
    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()


async def voice_loop(runtime, seconds: int = 6) -> None:
    """Push-to-talk loop: Enter to record, agent replies, answer is spoken."""
    print("Voice mode. Press Enter to talk, type 'q' then Enter to quit.")
    while True:
        cmd = await asyncio.to_thread(input, "[Enter to speak] ")
        if cmd.strip().lower() == "q":
            break
        captured = await asyncio.to_thread(record, seconds)
        if not captured:
            return
        samples, rate = captured
        text = await asyncio.to_thread(transcribe, samples, rate)
        if not text:
            print("(didn't catch that)")
            continue
        print(f"you said: {text}")
        answer = await runtime.agent.run(text)
        print(f"xplogent: {answer}")
        await asyncio.to_thread(speak, answer)
