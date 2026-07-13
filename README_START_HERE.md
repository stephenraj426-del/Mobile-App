# English + Indic 18-Sprite Production Lip-Sync Starter

This project gives you a production-style local pipeline for checking avatar lip-sync quality:

```text
text -> open-source TTS -> MFA/IndicMFA forced alignment -> TextGrid -> 18-sprite lipsync.json -> Unity playback
```

Supported languages in this code package:

```text
English, Tamil, Malayalam, Hindi, Telugu, Kannada
```

The language stack is intentionally stable:

```text
English:
  Piper TTS -> MFA english_mfa -> English ARPABET phone to 18-sprite viseme map

Tamil/Malayalam/Hindi/Telugu/Kannada:
  IndicF5 TTS -> IndicMFA/MFA -> script/akshara to 18-sprite viseme map
```

Unity does not know about language or phonemes. Unity only receives:

```text
audio/avatar.wav
lipsync/lipsync.json
```

## Output folder

Every run creates:

```text
backend/runs/<job_id>/
  audio/avatar.wav
  align/aligned.TextGrid
  lipsync/lipsync.json
  lipsync/qa_report.json
  corpus/utt_0001.lab
  corpus/utt_0001.wav
```

## Install Python backend

Recommended: Python 3.10.

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Install Montreal Forced Aligner

After installing MFA, this must work:

```bash
mfa version
```

For English alignment, download MFA English models:

```bash
mfa model download acoustic english_mfa
mfa model download dictionary english_mfa
```

For Indian-language alignment, download IndicMFA model/dictionary files and place them in:

```text
backend/models/indicmfa/ta/
backend/models/indicmfa/ml/
backend/models/indicmfa/hi/
backend/models/indicmfa/te/
backend/models/indicmfa/kn/
```

Then edit `backend/config/languages.json` with the exact IndicMFA filenames.

## English TTS setup

Install Piper separately and confirm:

```bash
piper --help
```

Place a Piper English voice model here:

```text
backend/models/piper_voices/en/en_US-lessac-medium.onnx
backend/models/piper_voices/en/en_US-lessac-medium.onnx.json
```

You may use a different Piper voice filename, but then pass `--piper-model` and `--piper-config` in the command.

## Indian-language TTS setup

Install IndicF5:

```bash
pip install git+https://github.com/ai4bharat/IndicF5.git
```

IndicF5 needs reference voice audio and the exact transcript of that audio. Put reference WAVs here:

```text
backend/prompts/ta_ref.wav
backend/prompts/ml_ref.wav
backend/prompts/hi_ref.wav
backend/prompts/te_ref.wav
backend/prompts/kn_ref.wav
```

## Run English check

Windows PowerShell:

```powershell
cd backend
python -m production_lipsync.cli_generate ^
  --lang en ^
  --text "Hello, how are you today? This is a production lip sync check." ^
  --piper-model "models/piper_voices/en/en_US-lessac-medium.onnx" ^
  --piper-config "models/piper_voices/en/en_US-lessac-medium.onnx.json" ^
  --job-id en_test_001
```

Linux/macOS:

```bash
cd backend
python -m production_lipsync.cli_generate \
  --lang en \
  --text "Hello, how are you today? This is a production lip sync check." \
  --piper-model "models/piper_voices/en/en_US-lessac-medium.onnx" \
  --piper-config "models/piper_voices/en/en_US-lessac-medium.onnx.json" \
  --job-id en_test_001
```

Output:

```text
backend/runs/en_test_001/audio/avatar.wav
backend/runs/en_test_001/lipsync/lipsync.json
backend/runs/en_test_001/lipsync/qa_report.json
```

## Run Tamil check

```powershell
cd backend
python -m production_lipsync.cli_generate ^
  --lang ta ^
  --text "வணக்கம். இன்று நாம் ஆங்கிலம் பயிலலாம்." ^
  --ref-audio prompts/ta_ref.wav ^
  --ref-text "உங்கள் தமிழ் reference audioவில் பேசப்பட்ட சரியான உரை இங்கே வர வேண்டும்" ^
  --job-id ta_test_001
```

## Unity setup

1. Copy `unity/Assets/Scripts/ProductionLipSyncPlayer.cs` into your Unity project.
2. Put generated files here:

```text
Assets/StreamingAssets/LipSync/en_test_001/avatar.wav
Assets/StreamingAssets/LipSync/en_test_001/lipsync.json
```

3. Add `ProductionLipSyncPlayer` to your avatar GameObject.
4. Assign:
   - `AudioSource`
   - `Mouth Renderer`
   - 18 mouth sprites in exact order `0..17`
   - optional `Mouth Anchor` transform for jaw movement
5. Set `streamingAssetsJobFolder` to `LipSync/en_test_001` or your job folder.
6. Press Play.

## 18 sprite order expected by Unity

```text
0  REST_CLOSED
1  A_OPEN
2  E_WIDE
3  U_ROUND
4  O_ROUND
5  AI_WIDE
6  MBP_CLOSE
7  FV_W
8  DENTAL_TDN
9  RETRO_TDN
10 KG
11 SZ_SH_CH
12 L
13 R
14 Y
15 SMALL_OPEN
16 MEDIUM_OPEN
17 BIG_OPEN
```

## Important production rule

The same normalized text must go to both TTS and MFA. Do not align with different text than the audio actually speaks. That is the main reason production lip-sync fails.

## Skipping TTS or alignment for debugging

You can reuse an existing WAV:

```bash
python -m production_lipsync.cli_generate --lang en --text "Hello" --job-id en_test_001 --skip-tts
```

You can reuse an existing TextGrid:

```bash
python -m production_lipsync.cli_generate --lang en --text "Hello" --job-id en_test_001 --skip-tts --skip-align
```

For `--skip-tts`, the WAV must already be at:

```text
backend/runs/<job_id>/audio/avatar.wav
```

For `--skip-align`, the TextGrid must already be at:

```text
backend/runs/<job_id>/align/aligned.TextGrid
```
