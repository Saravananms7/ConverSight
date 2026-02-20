# Test the /transcribe/audio endpoint
# Requires: server running (python run.py), .env with DEEPGRAM_API_KEY

$baseUrl = "http://localhost:8000"
$audioFile = "samples\test_audio.wav"

# Create test audio if it doesn't exist
if (-not (Test-Path $audioFile)) {
    Write-Host "Creating test audio file..." -ForegroundColor Yellow
    python scripts\create_test_audio.py
}

if (-not (Test-Path $audioFile)) {
    Write-Host "Error: No audio file. Run: python scripts\create_test_audio.py" -ForegroundColor Red
    exit 1
}

Write-Host "Testing POST /transcribe/audio with $audioFile" -ForegroundColor Cyan
Write-Host ""

$response = Invoke-RestMethod -Uri "$baseUrl/transcribe/audio" `
    -Method Post `
    -Form @{ file = Get-Item $audioFile }

$response | ConvertTo-Json
