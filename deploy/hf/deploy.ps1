# Deploy the MathCraft backend to Hugging Face Spaces (Windows / PowerShell).
#
# Usage:
#   $env:HF_TOKEN = "hf_xxx"
#   $env:HF_USER  = "yourname"
#   .\deploy\hf\deploy.ps1
#
# See deploy.sh for behavioral notes.

$ErrorActionPreference = 'Stop'

if (-not $env:HF_TOKEN -or -not $env:HF_USER) {
    Write-Error 'Set $env:HF_TOKEN and $env:HF_USER first.'
    exit 1
}

$HfSpace = if ($env:HF_SPACE) { $env:HF_SPACE } else { 'mathcraft' }
$RepoId  = "$($env:HF_USER)/$HfSpace"
$SpaceUrl = "https://huggingface.co/spaces/$RepoId"
$GitUrl   = "https://$($env:HF_USER):$($env:HF_TOKEN)@huggingface.co/spaces/$RepoId"

$RepoRoot   = (Resolve-Path "$PSScriptRoot\..\..").Path
$OverlayDir = "$RepoRoot\deploy\hf"
$StagingDir = New-Item -ItemType Directory -Path "$env:TEMP\mathcraft-hf-$(Get-Random)" -Force

try {
    Write-Host "-> Repo:      $RepoId"
    Write-Host "-> Staging:   $StagingDir"

    # 1. Create Space if missing.
    Write-Host "-> Ensuring Space exists..."
    $body = @{ type='space'; name=$HfSpace; private=$false; sdk='docker' } | ConvertTo-Json -Compress
    try {
        Invoke-RestMethod -Method Post -Uri 'https://huggingface.co/api/repos/create' `
            -Headers @{ Authorization = "Bearer $($env:HF_TOKEN)"; 'Content-Type'='application/json' } `
            -Body $body | Out-Null
    } catch {
        if ($_.ErrorDetails.Message -match 'already' -or $_.Exception.Response.StatusCode.value__ -eq 409) {
            Write-Host '   (already exists, ok)'
        } else { throw }
    }

    # 2. Assemble staging.
    Write-Host "-> Assembling files..."
    Copy-Item "$RepoRoot\backend\*" $StagingDir.FullName -Recurse -Force `
        -Exclude @('venv','__pycache__','data','.pytest_cache','.env')
    # Recursive __pycache__ scrub (Copy-Item -Exclude only matches at top level).
    Get-ChildItem $StagingDir.FullName -Recurse -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force
    Copy-Item "$OverlayDir\Dockerfile"     "$($StagingDir.FullName)\Dockerfile"     -Force
    Copy-Item "$OverlayDir\README.md"      "$($StagingDir.FullName)\README.md"      -Force
    Copy-Item "$OverlayDir\.gitattributes" "$($StagingDir.FullName)\.gitattributes" -Force

    # 3. Init git + push.
    Write-Host "-> Pushing to HF..."
    Push-Location $StagingDir.FullName
    try {
        git init -q -b main
        git config user.email "$($env:HF_USER)@users.noreply.huggingface.co"
        git config user.name  "$($env:HF_USER)"
        git add .
        git commit -q -m 'Deploy MathCraft backend'
        git remote add origin $GitUrl
        git push -f origin main
    } finally {
        Pop-Location
    }

    Write-Host ''
    Write-Host "OK Pushed. Build will start automatically."
    Write-Host "   Watch logs:           $SpaceUrl"
    Write-Host "   Health (when ready):  https://$($env:HF_USER)-$HfSpace.hf.space/api/health"
} finally {
    Remove-Item $StagingDir.FullName -Recurse -Force -ErrorAction SilentlyContinue
}
