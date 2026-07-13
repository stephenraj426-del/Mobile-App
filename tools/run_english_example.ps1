Set-Location "$PSScriptRoot\..\backend"

python -m production_lipsync.cli_generate `
  --lang en `
  --text "Hello, how are you today? This is a production lip sync check." `
  --piper-model "models/piper_voices/en/en_US-lessac-medium.onnx" `
  --piper-config "models/piper_voices/en/en_US-lessac-medium.onnx.json" `
  --job-id en_test_001
