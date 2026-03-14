# TTS Research — Deutsche Sprachsynthese für Community-App
**Datum:** 2026-03-14  
**Kontext:** Befreundeter Entwickler (Florians Bekannter), Community-App mit Vorlesefunktion

## Volumen
- 30–60 Artikel/Woche (Ø 45), 200–500 Wörter (Ø 350)
- ~380.000 Zeichen/Monat
- ~30 Stunden Audio/Monat

## Managed APIs — Preise (Stand März 2026)

### ElevenLabs
- Credits-System: 1 Credit = 1 Zeichen (Standard), 0,5 Credits (Turbo/Flash)
- Free: 10k Credits/Mo
- Starter: $5/Mo → 30k Credits
- Creator: $22/Mo → 100k Credits
- Pro: $99/Mo → 500k Credits
- **API Pay-as-you-go: ~$30/1M Zeichen → ~$11,40/Mo bei 380k Z**
- Beste Qualität, Voice Cloning möglich, multilingual v2.5

### Azure Neural TTS
- Neural Standard: ~$15/1M Z → ~$5,70/Mo
- HD Neural: ~$30/1M Z → ~$11,40/Mo
- **Free Tier: 500k Z/Monat kostenlos (deckt Volumen ab!)**
- de-DE: KatjaNeural, ConradNeural, AmalaNeural

### Google Cloud TTS
- WaveNet/Neural2: $16/1M Z → ~$6,10/Mo
- Chirp 3 HD: $30/1M Z → ~$11,40/Mo
- Free: 1M WaveNet-Z/Mo im ersten Jahr

### Amazon Polly
- Neural: $16/1M Z → ~$6,10/Mo
- Free: 5M Standard / 1M Neural im ersten Jahr

### OpenAI TTS-1
- ~$15/1M Z → ~$5,70/Mo
- Nicht für Deutsch optimiert — nicht empfohlen

## Self-Hosted

### Piper TTS ⭐ Top-Empfehlung
- Thorsten-High: beste dt. Open-Source-Stimme
- MIT-Lizenz, ~80MB Modell, läuft auf ARM64 CPU
- Docker-Container verfügbar
- Hetzner CX22: ~€4,50/Mo → Marginalkosten $0

### Coqui TTS (XTTS-v2)
- Zu langsam für CPU ohne GPU
- Projekt eingestellt (2024), CPML-Lizenz

### Kokoro (82M Param)
- Deutsch noch experimentell — nicht produktionsreif

## Webservice-Design

### Stack
- FastAPI (Python) + Piper oder Azure
- Cache: SQLite/Redis (pre-render beim Publizieren!)
- Storage: Cloudflare R2 (~$0/Mo bei diesem Volumen)
- Docker Compose

### API
```
POST /synthesize {text, article_id, voice?}
→ {audio_url, duration_seconds, cached, chars}
```

### Aufwand
~2,5–3 Entwicklertage für vollständigen Service

## Empfehlungen
1. **Sofort/kostenlos:** Azure Neural Free Tier (500k Z/Mo frei)
2. **Premium bis $25:** ElevenLabs API PAYG (~$11-12/Mo) — beste Qualität
3. **Langfristig/Zero-Cost:** Piper Self-Hosted auf Hetzner ARM64
4. **Hybrid-Favorit:** Piper Primary + Azure Fallback + aggressiver Cache
