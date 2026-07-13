cd ..\backend
.\.venv\Scripts\Activate.ps1
python -m production_lipsync.cli_generate `
  --lang ta `
  --text "வணக்கம். இன்று நாம் ஆங்கிலம் பயிலலாம்." `
  --ref-audio prompts/ta_ref.wav `
  --ref-text "உங்கள் தமிழ் reference audioவில் பேசப்பட்ட சரியான உரை இங்கே வர வேண்டும்" `
  --job-id ta_test_001
