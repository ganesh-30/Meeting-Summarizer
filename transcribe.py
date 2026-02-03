import whisper
import os

model = None

def load_whisper_model():
    """Load Whisper model (lazy loading)"""
    global model
    if model is None:
        model = whisper.load_model("medium")
    return model

def transcribe_audio_file(audio_file_path):
    """
    Transcribe a single audio or video file and save transcript to data/transcripts folder.
    Whisper can handle both audio and video files directly by extracting audio automatically.
    
    Args:
        audio_file_path (str): Full path to the audio/video file to transcribe
        
    Returns:
        str: Path to the saved transcript file, or None if error
    """
    TRANSCRIPT_DIR = os.path.join("data", "transcripts")
    
    if not os.path.exists(TRANSCRIPT_DIR):
        os.makedirs(TRANSCRIPT_DIR)
    
    try:
        if not os.path.exists(audio_file_path):
            print(f"Error: File not found: {audio_file_path}")
            return None
        
        file_ext = os.path.splitext(audio_file_path)[1].lower()
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v', '.3gp']
        audio_extensions = ['.mp3', '.wav', '.m4a', '.flac', '.aac', '.ogg', '.wma']
        
        is_video = file_ext in video_extensions
        is_audio = file_ext in audio_extensions
        
        if not (is_video or is_audio):
            print(f"Warning: Unrecognized file extension: {file_ext}. Attempting to transcribe anyway...")
        
        file_type = "video" if is_video else "audio"
        print(f"Transcribing {file_type} file: {audio_file_path}...")
        
        model = load_whisper_model()
        
        result = model.transcribe(audio_file_path)
        
        transcript_text = result["text"]

        base_name = os.path.splitext(os.path.basename(audio_file_path))[0]
        out_file = os.path.join(TRANSCRIPT_DIR, f"{base_name}.txt")
        
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(transcript_text)
        
        print(f"Transcript saved to {out_file}")
        return out_file
        
    except Exception as e:
        print(f"Error transcribing file: {e}")
        import traceback
        traceback.print_exc()
        return None


