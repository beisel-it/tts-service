# Task: Job-Queue (SQLite polling)
Shortcode: TTS-C1
Stage: todo
Status: todo
Priority: P1
Definition of Done:
- claim_next_job(): atomisches SELECT + UPDATE status=processing
- release_job_failed(): status=failed, error setzen, retry_count++
- complete_job(): status=done, audio_url, duration, completed_at setzen
Depends on: TTS-A2
