# Task: POST /synthesize Route
Shortcode: TTS-B1
Stage: todo
Status: todo
Priority: P1
Definition of Done:
- Nimmt {text, article_id?, voice?, backend?, webhook_url?}
- Berechnet text_hash (SHA-256)
- Idempotenz-Check: article_id oder text_hash bereits done? → 200 + cached:true
- Neuer Job: audio_url deterministisch berechnen, Job in DB anlegen, in Queue stellen
- Response: 201 mit job_id, status, audio_url, poll_url
Depends on: TTS-A1, TTS-A2
