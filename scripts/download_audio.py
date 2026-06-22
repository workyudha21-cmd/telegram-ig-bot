import requests
import os

AUDIO_DIR = os.path.join(os.path.dirname(__file__), "..", "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

AUDIO_SOURCES = {
    "bismillah.mp3": "https://cdn.pixabay.com/audio/2024/11/28/audio_d5470ad553.mp3",
}

def download_audio():
    for filename, url in AUDIO_SOURCES.items():
        filepath = os.path.join(AUDIO_DIR, filename)
        if os.path.exists(filepath):
            print(f"✅ {filename} sudah ada")
            continue
        
        print(f"📥 Downloading {filename}...")
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            with open(filepath, 'wb') as f:
                f.write(response.content)
            print(f"✅ {filename} berhasil didownload ({len(response.content)} bytes)")
        except Exception as e:
            print(f"❌ Gagal download {filename}: {e}")

if __name__ == "__main__":
    download_audio()
