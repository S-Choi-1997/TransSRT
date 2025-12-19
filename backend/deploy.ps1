# TransSRT Deployment Script for Windows PowerShell
# Deploys the translation service to Google Cloud Functions Gen2

param(
    [switch]$SkipValidation
)

$ErrorActionPreference = "Stop"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "TransSRT Deployment Script" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Check if .env file exists
if (-not (Test-Path ".env")) {
    Write-Host "[ERROR] .env file not found!" -ForegroundColor Red
    exit 1
}

# Load environment variables from .env
Write-Host "Loading configuration from .env..."
Get-Content ".env" | ForEach-Object {
    if ($_ -match '^([^#][^=]+)=(.*)$') {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim()
        Set-Variable -Name $name -Value $value -Scope Script
    }
}

# Validate required variables
if ([string]::IsNullOrEmpty($GEMINI_API_KEY)) {
    Write-Host "[ERROR] GEMINI_API_KEY not set in .env" -ForegroundColor Red
    exit 1
}

if ([string]::IsNullOrEmpty($GEMINI_MODEL)) {
    Write-Host "[ERROR] GEMINI_MODEL not set in .env" -ForegroundColor Red
    exit 1
}

# Set defaults
if ([string]::IsNullOrEmpty($CHUNK_SIZE)) { $CHUNK_SIZE = "100" }
if ([string]::IsNullOrEmpty($MAX_CONCURRENT_REQUESTS)) { $MAX_CONCURRENT_REQUESTS = "5" }
if ([string]::IsNullOrEmpty($MAX_FILE_SIZE_MB)) { $MAX_FILE_SIZE_MB = "10" }
if ([string]::IsNullOrEmpty($CORS_ORIGINS)) { $CORS_ORIGINS = "*" }

# Display configuration
Write-Host ""
Write-Host "Deployment Configuration:" -ForegroundColor Yellow
Write-Host "  GEMINI_MODEL: $GEMINI_MODEL"
Write-Host "  CHUNK_SIZE: $CHUNK_SIZE"
Write-Host "  MAX_CONCURRENT_REQUESTS: $MAX_CONCURRENT_REQUESTS"
Write-Host "  MAX_FILE_SIZE_MB: $MAX_FILE_SIZE_MB"
Write-Host "  CORS_ORIGINS: $CORS_ORIGINS"
Write-Host ""

# Function settings
$FUNCTION_NAME = "translate-srt"
$REGION = "us-central1"
$RUNTIME = "python311"
$MEMORY = "512MB"
$TIMEOUT = "540s"

# Update Google Cloud Secret
Write-Host "Updating Google Cloud Secret Manager..." -ForegroundColor Yellow

try {
    # Check if secret exists
    $secretExists = gcloud secrets describe GEMINI_API_KEY 2>$null

    if ($LASTEXITCODE -eq 0) {
        Write-Host "Secret exists, updating to latest version..."
        $GEMINI_API_KEY | gcloud secrets versions add GEMINI_API_KEY --data-file=-
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[SUCCESS] Secret updated successfully" -ForegroundColor Green
        } else {
            Write-Host "[ERROR] Failed to update secret" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "Secret does not exist, creating..."
        $GEMINI_API_KEY | gcloud secrets create GEMINI_API_KEY --data-file=-
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[SUCCESS] Secret created successfully" -ForegroundColor Green
        } else {
            Write-Host "[ERROR] Failed to create secret" -ForegroundColor Red
            exit 1
        }
    }
} catch {
    Write-Host "[ERROR] Failed to update secret: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Deploying Cloud Function..." -ForegroundColor Yellow
Write-Host ""

# Deploy function (env vars are read from .env by the function itself via python-dotenv)
$deployCmd = @"
gcloud functions deploy $FUNCTION_NAME ``
    --gen2 ``
    --runtime=$RUNTIME ``
    --region=$REGION ``
    --source=. ``
    --entry-point=translate_srt ``
    --trigger-http ``
    --allow-unauthenticated ``
    --set-secrets=GEMINI_API_KEY=GEMINI_API_KEY:latest ``
    --env-vars-file=.env.yaml ``
    --timeout=$TIMEOUT ``
    --memory=$MEMORY
"@

# Create .env.yaml from .env for deployment
Write-Host "Creating .env.yaml from .env..."
@"
MAX_CONCURRENT_REQUESTS: '$MAX_CONCURRENT_REQUESTS'
CHUNK_SIZE: '$CHUNK_SIZE'
GEMINI_MODEL: '$GEMINI_MODEL'
MAX_FILE_SIZE_MB: '$MAX_FILE_SIZE_MB'
CORS_ORIGINS: '$CORS_ORIGINS'
"@ | Out-File -FilePath ".env.yaml" -Encoding UTF8

Invoke-Expression $deployCmd

# Clean up temp file
Remove-Item ".env.yaml" -ErrorAction SilentlyContinue

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "=========================================" -ForegroundColor Red
    Write-Host "[ERROR] Deployment failed!" -ForegroundColor Red
    Write-Host "=========================================" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=========================================" -ForegroundColor Green
Write-Host "[SUCCESS] Deployment successful!" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
Write-Host ""

# Get function URL
$FUNCTION_URL = gcloud functions describe $FUNCTION_NAME --region=$REGION --gen2 --format="value(serviceConfig.uri)"
Write-Host "Function URL: $FUNCTION_URL" -ForegroundColor Cyan

# Verify deployed environment variables
if (-not $SkipValidation) {
    Write-Host ""
    Write-Host "Verifying deployed configuration..." -ForegroundColor Yellow

    $DEPLOYED_MODEL = gcloud functions describe $FUNCTION_NAME --region=$REGION --gen2 --format="value(serviceConfig.environmentVariables.GEMINI_MODEL)"
    $DEPLOYED_CONCURRENT = gcloud functions describe $FUNCTION_NAME --region=$REGION --gen2 --format="value(serviceConfig.environmentVariables.MAX_CONCURRENT_REQUESTS)"
    $DEPLOYED_CHUNK_SIZE = gcloud functions describe $FUNCTION_NAME --region=$REGION --gen2 --format="value(serviceConfig.environmentVariables.CHUNK_SIZE)"

    Write-Host "  Deployed GEMINI_MODEL: $DEPLOYED_MODEL"
    Write-Host "  Deployed MAX_CONCURRENT_REQUESTS: $DEPLOYED_CONCURRENT"
    Write-Host "  Deployed CHUNK_SIZE: $DEPLOYED_CHUNK_SIZE"

    # Check if deployed values match expected
    $errors = 0

    if ($DEPLOYED_MODEL -ne $GEMINI_MODEL) {
        Write-Host "[WARNING] Deployed GEMINI_MODEL ($DEPLOYED_MODEL) doesn't match .env ($GEMINI_MODEL)" -ForegroundColor Yellow
        $errors++
    }

    if ($DEPLOYED_CONCURRENT -ne $MAX_CONCURRENT_REQUESTS) {
        Write-Host "[WARNING] Deployed MAX_CONCURRENT_REQUESTS ($DEPLOYED_CONCURRENT) doesn't match .env ($MAX_CONCURRENT_REQUESTS)" -ForegroundColor Yellow
        $errors++
    }

    if ($DEPLOYED_CHUNK_SIZE -ne $CHUNK_SIZE) {
        Write-Host "[WARNING] Deployed CHUNK_SIZE ($DEPLOYED_CHUNK_SIZE) doesn't match .env ($CHUNK_SIZE)" -ForegroundColor Yellow
        $errors++
    }

    if ($errors -eq 0) {
        Write-Host ""
        Write-Host "[SUCCESS] All checks passed!" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "[WARNING] Some configuration mismatches detected!" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Press any key to continue..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
