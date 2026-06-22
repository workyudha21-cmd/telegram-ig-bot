from gtts import gTTS
import os

AUDIO_DIR = os.path.join(os.path.dirname(__file__), "..", "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

def generate_bismillah_audio():
    filepath = os.path.join(AUDIO_DIR, "bismillah.mp3")
    if os.path.exists(filepath):
        print(f"✅ bismillah.mp3 sudah ada")
        return
    
    print("📥 Generating Bismillah audio...")
    try:
        tts = gTTS(text="Bismillah ir-Rahman ir-Rahim", lang='ar', slow=False)
        tts.save(filepath)
        print(f"✅ bismillah.mp3 berhasil dibuat")
    except Exception as e:
        print(f"❌ Gagal generate audio: {e}")

if __name__ == "__main__":
    generate_bismillah_audio()
