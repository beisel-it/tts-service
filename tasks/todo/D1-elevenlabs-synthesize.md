# Task: ElevenLabs Backend — synthesize()
Shortcode: TTS-D1
Stage: todo
Status: todo
Priority: P1
Definition of Done:
- POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}
- Model: eleven_multilingual_v2
- Output: mp3_44100_128
- Auth: xi-api-key Header aus Config
- Gibt rohe MP3-Bytes zurück
- Implementiert TTSBackend ABC
Depends on: TTS-A1
