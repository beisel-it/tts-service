# Task: Lokales Storage-Modul
Shortcode: TTS-A3
Stage: todo
Status: todo
Priority: P1
Definition of Done:
- File schreiben: audio-bytes → /data/audio/{hash[:8]}/{hash}.mp3
- Public URL generieren aus config.public_base_url
- Cleanup-Funktion: Files älter als N Tage löschen
- Nginx-Config-Snippet für /audio/ static serving

## Steps
- storage/local.py schreiben
- Verzeichnis-Handling (mkdir -p)
- Cleanup via Last-Modified-Check
