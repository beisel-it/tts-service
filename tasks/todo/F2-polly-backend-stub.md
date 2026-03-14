# Task: Polly Backend Stub
Shortcode: TTS-F2
Stage: todo
Status: ready-for-research
Priority: P2
Depends on: TTS-A1, TTS-F1

## Definition of Done

### File Created
- `app/backends/polly.py` — PollyBackend class (stub)

### Class Requirements
PollyBackend class:
- ✅ Inherits from `TTSBackend` (from `app.backends.base`)
- ✅ Implements `async def synthesize(text: str, voice_id: str, output_format: str = "mp3_44100_128") -> bytes`
  - `raise NotImplementedError("Polly backend not yet implemented")`
- ✅ Implements `def list_voices() -> list[VoiceInfo]`
  - `raise NotImplementedError("Polly backend not yet implemented")`
- ✅ Implements `@property def name() -> str`
  - Returns `"polly"`
- ✅ Docstring with reference to architecture spec section 4.3 (Amazon Polly)

### Reference Information
From architecture spec (section 4.3):
- AWS SDK: boto3 polly.synthesize_speech()
- Voices: Vicki (de-DE), Daniel (de-DE), Neural engine
- Output: mp3
- Phase 2 — implementation deferred, stub provides interface only

## Implementation Steps

1. Create `app/backends/polly.py`
   - Define `PollyBackend(TTSBackend)` class
   - Import necessary types from base.py
   - Docstring references architecture section 4.3

2. Implement abstract methods (all raise NotImplementedError)
   - `synthesize()` — async, returns bytes
   - `list_voices()` — returns list[VoiceInfo]
   - `name` property — returns "polly"

3. Include Phase-2 comment with implementation hints
   - Boto3 integration path
   - Voice ID mapping
   - Error handling placeholders

4. Update `app/backends/__init__.py` if not already done
   - Ensure PollyBackend is imported and exported

## Dependencies & Blockers
- ✅ Depends on: TTS-A1 (Config), TTS-F1 (Base stub pattern)
- ⏳ Blocks: None (Phase 2 work)
- No blockers identified

## Notes
- Architecture spec: Section 4.3 (Amazon Polly Backend)
- Part of Phase-2 backend stubs; Phase 1 focuses on ElevenLabs only
- Stub must follow exact same pattern as Azure and Piper stubs
- Implementation code is provided in architecture section 4.3 for reference
