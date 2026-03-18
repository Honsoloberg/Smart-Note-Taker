import subprocess
from vosk import Model, KaldiRecognizer, SetLogLevel
import re
from tqdm import tqdm

def transcribe(audio_file: str) -> str:
    return vosk_transcribe(audio_file)

SetLogLevel(-1)
model = None

def set_model():
    global model
    if not model:
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
    
    rec = KaldiRecognizer(model, 16000)

    # Critical performance flags
    rec.SetWords(False)
    rec.SetPartialWords(False)

    duration = get_audio_duration(audio_file)
    bytes_per_second = 16000 * 2  # 16kHz * 16-bit mono
    total_bytes = int(duration * bytes_per_second)

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

    with tqdm(
        total=total_bytes,
        unit="B",
        unit_scale=True,
        desc="Transcribing",
    ) as pbar:

        while True:
            data = process.stdout.read(4000)
            if not data:
                break

            rec.AcceptWaveform(data)
            pbar.update(len(data))

    print("Finalizing...")

    # FinalResult() still returns JSON, but it's now *tiny*
    final = rec.FinalResult()
    print("got final result")
    # Fast extraction of "text" without json.loads
    match = re.search(r'"text"\s*:\s*"([^"]*)"', final)
    text = match.group(1) if match else ""

    print("Done")
    return text