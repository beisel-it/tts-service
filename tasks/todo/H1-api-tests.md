# Task: API-Tests
Shortcode: TTS-H1
Stage: todo
Status: todo
Priority: P2
Definition of Done:
- pytest + httpx TestClient
- POST /synthesize: 201 new, 200 cached, 401 no auth, 422 bad input
- GET /jobs/{id}: 200 done, 404 unknown
- GET /health: 200
Depends on: TTS-B1, TTS-B2, TTS-B3, TTS-B4
