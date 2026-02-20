# CoverSight API Test Script (PowerShell)
# Run with: .\scripts\test_api.ps1
# Ensure server is running: python run.py

$baseUrl = "http://localhost:8000"

Write-Host "=== CoverSight API Tests ===" -ForegroundColor Cyan

# 1. Health check
Write-Host "`n1. GET /health" -ForegroundColor Yellow
Invoke-RestMethod -Uri "$baseUrl/health" -Method Get | ConvertTo-Json

# 2. Root
Write-Host "`n2. GET /" -ForegroundColor Yellow
Invoke-RestMethod -Uri "$baseUrl/" -Method Get | ConvertTo-Json

# 3. Transcribe audio (requires samples\test_audio.wav - run create_test_audio.py first)
if (Test-Path "samples\test_audio.wav") {
    Write-Host "`n3. POST /transcribe/audio" -ForegroundColor Yellow
    $response = Invoke-RestMethod -Uri "$baseUrl/transcribe/audio" -Method Post -Form @{ file = Get-Item "samples\test_audio.wav" }
    $response | ConvertTo-Json
} else {
    Write-Host "`n3. Skipping transcribe test - run: python scripts\create_test_audio.py" -ForegroundColor Yellow
}

Write-Host "`nDone." -ForegroundColor Green
