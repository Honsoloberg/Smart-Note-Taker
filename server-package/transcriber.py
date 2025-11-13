from faster_whisper import WhisperModel
import torch
# import whisperx

def whisperx_transcribe(model_name: str, audio_file: str) -> str:
    batch_size = 10

    device = "cpu" if torch.cuda.is_available() else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
    # Load model
    model = whisperx.load_model(
        model_name, 
        device, 
        compute_type=compute_type, 
        task="transcribe",
        )

    # Transcribe audio
    result = model.transcribe(audio_file, batch_size=batch_size, verbose=False)

    # The result is a dict with segments + text
    return result["text"]

def transcribe_faster_whisper(audio_file: str) -> str:
    # batch_size = 8

    device = "cpu" if torch.cuda.is_available() else "cpu"
    
    compute_type = "float16" if device == "cuda" else "int8"
    # Load model
    model = WhisperModel(
        "small", 
        device, 
        compute_type=compute_type,
    )

    # Transcribe audio
    # result = model.transcribe(audio_file, vad_filter=False)
    segments, info = model.transcribe(audio_file, beam_size=5)

    print("Detected language '%s' with probability %f" % (info.language, info.language_probability))

    text = ""
    for segment in segments:
        print("[%.2fs -> %.2fs] %s" % (segment.start, segment.end, segment.text))
        text += segment.text
    # The result is a dict with segments + text
    return text

def transcribe(audio_file: str) -> str:
    return transcribe_faster_whisper(audio_file)