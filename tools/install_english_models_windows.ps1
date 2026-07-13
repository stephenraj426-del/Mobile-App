Set-Location "$PSScriptRoot\..\backend"

Write-Host "Downloading MFA English model names into MFA cache..."
mfa model download acoustic english_mfa
mfa model download dictionary english_mfa

Write-Host "Now download a Piper English .onnx voice and .onnx.json config into:"
Write-Host "backend\models\piper_voices\en\"
Write-Host "Expected default filenames:"
Write-Host "en_US-lessac-medium.onnx"
Write-Host "en_US-lessac-medium.onnx.json"
