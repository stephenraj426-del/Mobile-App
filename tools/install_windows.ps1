# Run from indic_lipsync_production\backend or double-click/run this file from tools.
Set-Location "$PSScriptRoot\..\backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install git+https://github.com/ai4bharat/IndicF5.git

Write-Host "Install Montreal Forced Aligner separately, then run: mfa version"
Write-Host "For English alignment run: mfa model download acoustic english_mfa ; mfa model download dictionary english_mfa"
Write-Host "For English TTS install Piper separately and place a Piper voice .onnx + .onnx.json in backend\models\piper_voices\en\"
