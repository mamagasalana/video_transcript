import whisper

# 1) Load a model
# Options: "tiny", "base", "small", "medium", "large"
# tiny/base = faster, worse accuracy; medium/large = slower, better accuracy
model = whisper.load_model("large   ")

# 2) Path to your video (e.g. the one you just downloaded)
video_path = "video.mp4"  # change this to your file

# 3) Run transcription
print("Transcribing... this may take a while.")
result = model.transcribe(video_path, language="zh" if "2025" else None)
# You can omit language=... and let it detect automatically:
# result = model.transcribe(video_path)

# 4) Print text
print("\n=== TRANSCRIPT ===\n")
print(result["text"])
