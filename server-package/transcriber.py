import subprocess
from vosk import Model, KaldiRecognizer, SetLogLevel
import re
from tqdm import tqdm

def transcribe(audio_file: str) -> str:
    return vosk_transcribe(audio_file)

SetLogLevel(-1)
model = None
_TEXT_RE = re.compile(r'"text"\s*:\s*"([^"]*)"')


def set_model():
    global model
    if model is None:
        model = Model(lang="en-us")


def get_audio_duration(audio_file: str) -> float:
    """Get duration in seconds using ffprobe"""
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_file
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    return float(result.stdout.strip())


def vosk_transcribe(audio_file: str) -> str:
    set_model()

    duration = get_audio_duration(audio_file)
    bytes_per_second = 16000 * 2  # 16kHz * 16-bit mono
    total_bytes = int(duration * bytes_per_second)

    # TC2 micro memory-friendly settings
    segment_duration = 300  # seconds
    segment_bytes = int(segment_duration * bytes_per_second)
    block_size = 65536  # larger read size reduces syscall overhead

    process = subprocess.Popen(
        [
            "ffmpeg",
            "-loglevel", "error",
            "-i", audio_file,
            "-ar", "16000",
            "-ac", "1",
            "-f", "s16le",
            "-"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL
    )

    all_text = []
    buffer = bytearray()

    with tqdm(
        total=total_bytes,
        unit="B",
        unit_scale=True,
        desc="Transcribing",
    ) as pbar:

        while True:
            data = process.stdout.read(block_size)
            if not data:
                break

            buffer.extend(data)
            pbar.update(len(data))

            while len(buffer) >= segment_bytes:
                segment = bytes(buffer[:segment_bytes])
                txt = _transcribe_segment(segment)
                if txt:
                    all_text.append(txt)
                del buffer[:segment_bytes]

    if buffer:
        txt = _transcribe_segment(bytes(buffer))
        if txt:
            all_text.append(txt)

    process.wait()

    return " ".join(all_text)


def _transcribe_segment(audio_data: bytes) -> str:
    """Transcribe a single audio segment and free recognizer memory immediately."""
    rec = KaldiRecognizer(model, 16000)
    rec.SetWords(False)
    rec.SetPartialWords(False)

    # Feed in smaller chunks for less memory pressure inside Vosk
    for chunk_start in range(0, len(audio_data), 32000):
        chunk = audio_data[chunk_start:chunk_start + 32000]
        rec.AcceptWaveform(chunk)

    final = rec.FinalResult()
    match = _TEXT_RE.search(final)
    text = match.group(1) if match else ""

    del rec
    return text