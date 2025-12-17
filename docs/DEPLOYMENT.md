# TransSRT Deployment Guide

Complete guide for deploying TransSRT to GCP Cloud Run Functions and GitHub Pages.

## Prerequisites

1. **Google Cloud Account**
   - Free tier available
   - Credit card required for verification

2. **Gemini API Key**
   - Get it from: https://ai.google.dev/gemini-api
   - Free tier: 15 requests per minute

3. **GitHub Account**
   - For hosting frontend on GitHub Pages

4. **Tools**
   - `gcloud` CLI: https://cloud.google.com/sdk/docs/install
   - Git
   - Python 3.11+ (for local testing)

## Deployment Methods

### Option 1: Automated Deployment (GitHub Actions)

#### Step 1: Setup GCP Service Account

```bash
# Set your project ID
export PROJECT_ID="transsrt"

# Create service account
gcloud iam service-accounts create transsrt-deployer \
  --display-name="TransSRT Deployer" \
  --project=$PROJECT_ID

# Grant necessary roles
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:transsrt-deployer@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/cloudfunctions.developer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:transsrt-deployer@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

# Create and download key
gcloud iam service-accounts keys create transsrt-sa-key.json \
  --iam-account=transsrt-deployer@$PROJECT_ID.iam.gserviceaccount.com

# The JSON key will be used in GitHub Secrets
```

#### Step 2: Store Gemini API Key in Secret Manager

```bash
# Store API key
echo "YOUR_GEMINI_API_KEY" | gcloud secrets create gemini-api-key \
  --data-file=- \
  --replication-policy="automatic" \
  --project=$PROJECT_ID

# Grant function access
gcloud secrets add-iam-policy-binding gemini-api-key \
  --member="serviceAccount:$PROJECT_ID@appspot.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=$PROJECT_ID
```

#### Step 3: Configure GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions

Add the following secrets:

1. **GCP_SA_KEY**: Contents of `transsrt-sa-key.json`
2. **GEMINI_MODEL**: `gemini-1.5-flash`
3. **CORS_ORIGINS**: Your GitHub Pages URL (e.g., `https://yourusername.github.io`)

#### Step 4: Enable GitHub Pages

1. Go to repository Settings → Pages
2. Source: GitHub Actions
3. Save

#### Step 5: Push and Deploy

```bash
git add .
git commit -m "Initial commit"
git push origin main
```

GitHub Actions will automatically:
- Deploy backend to Cloud Run Functions
- Deploy frontend to GitHub Pages

### Option 2: Manual Deployment

#### Step 1: Run Deployment Script

```bash
# Make script executable (if not already)
chmod +x scripts/deploy_cloudrun.sh

# Set your GCP project ID (optional, defaults to "transsrt")
export GCP_PROJECT_ID="your-project-id"

# Run deployment
./scripts/deploy_cloudrun.sh
```

The script will:
1. Authenticate with GCP
2. Create/select project
3. Enable required APIs
4. Setup Gemini API key in Secret Manager
5. Deploy Cloud Run Function
6. Display function URL

#### Step 2: Update Frontend Configuration

Edit `frontend/app.js`:

```javascript
const CONFIG = {
    API_ENDPOINT: 'https://YOUR-FUNCTION-URL',  // Update this
    // ...
};
```

#### Step 3: Deploy Frontend

**Option A: GitHub Pages (recommended)**

```bash
# Push to GitHub
git add .
git commit -m "Deploy frontend"
git push origin main

# Enable GitHub Pages in repository settings
```

**Option B: Alternative hosting**

Upload the `frontend/` directory contents to any static hosting service:
- Netlify
- Vercel
- Cloudflare Pages
- etc.

## Configuration

### Environment Variables

Backend environment variables (set during deployment):

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | - | Gemini API key (from Secret Manager) |
| `GEMINI_MODEL` | `gemini-1.5-flash` | Gemini model to use |
| `CHUNK_SIZE` | `50` | Subtitles per chunk |
| `MAX_CONCURRENT_REQUESTS` | `10` | Max parallel API calls |
| `MAX_FILE_SIZE_MB` | `10` | Max upload size |
| `CORS_ORIGINS` | `*` | Allowed origins |

### Frontend Configuration

Update `frontend/app.js`:

```javascript
const CONFIG = {
    API_ENDPOINT: 'YOUR_CLOUD_FUNCTION_URL',
    MAX_FILE_SIZE: 10 * 1024 * 1024,
    ALLOWED_EXTENSIONS: ['.srt'],
    REQUEST_TIMEOUT: 5 * 60 * 1000
};
```

## Local Testing

### Backend

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export GEMINI_API_KEY="your-api-key"
export GEMINI_MODEL="gemini-1.5-flash"

# Run locally
python main.py

# Test endpoint
curl -X POST -F 'file=@test.srt' http://localhost:8080/translate
```

### Frontend

```bash
cd frontend

# Serve with Python
python -m http.server 8000

# Or use any static server
npx serve .

# Open http://localhost:8000
```

## Monitoring

### View Logs

```bash
# Real-time logs
gcloud functions logs read translate-srt \
  --region=us-central1 \
  --gen2 \
  --limit=50

# Follow logs
gcloud functions logs tail translate-srt \
  --region=us-central1 \
  --gen2
```

### View Metrics

Visit Google Cloud Console:
https://console.cloud.google.com/functions/details/us-central1/translate-srt

## Troubleshooting

### Function Deployment Fails

**Error: "API not enabled"**
```bash
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

**Error: "Permission denied"**
- Check service account has necessary roles
- Verify you're authenticated: `gcloud auth list`

### Function Returns 500 Error

**Check logs:**
```bash
gcloud functions logs read translate-srt --region=us-central1 --gen2 --limit=10
```

**Common issues:**
1. Gemini API key not set or invalid
2. Secret Manager permissions not configured
3. Dependency installation failed

### CORS Errors in Frontend

Update `CORS_ORIGINS` environment variable:

```bash
gcloud functions deploy translate-srt \
  --update-env-vars CORS_ORIGINS=https://yourusername.github.io \
  --region=us-central1 \
  --gen2
```

### Rate Limit Errors

Gemini free tier: 15 RPM

Solutions:
1. Reduce `MAX_CONCURRENT_REQUESTS` to 5
2. Upgrade to paid tier
3. Implement request queuing

## Cost Estimation

### Free Tier Limits (per month)

**Gemini API:**
- 15 requests per minute
- ~40,000 subtitle entries

**Cloud Run Functions:**
- 2M invocations
- 400,000 GB-seconds compute
- 200,000 GHz-seconds compute
- 5GB egress (North America)

**Estimated Capacity:**
- ~10,000 translations per month (within free tier)
- Average file: 1000 entries

### Paid Tier Costs

**Gemini API (if exceeding free tier):**
- Input: $0.075 per 1M tokens
- Output: $0.30 per 1M tokens
- ~$0.011 per 1000 entries

**Cloud Run:**
- Compute: $0.00002400 per GB-second
- Requests: $0.40 per million
- Egress: $0.12 per GB

**Example monthly cost for 100,000 translations:**
- Gemini: ~$110
- Cloud Run: ~$10
- Total: ~$120/month

## Updating

### Update Backend

```bash
# Edit files in backend/

# Deploy
gcloud functions deploy translate-srt \
  --region=us-central1 \
  --gen2

# Or push to GitHub (if using Actions)
git push origin main
```

### Update Frontend

```bash
# Edit files in frontend/

# Push to GitHub
git push origin main

# GitHub Pages will auto-deploy
```

## Security Best Practices

1. **Never commit .env or API keys**
   - Use Secret Manager for production
   - .env is gitignored

2. **Restrict CORS origins**
   - Set specific domain instead of `*`
   - Update after frontend is deployed

3. **Monitor usage**
   - Set up billing alerts
   - Monitor Cloud Functions metrics

4. **Rate limiting**
   - Configure `MAX_CONCURRENT_REQUESTS`
   - Implement frontend rate limiting if needed

## Support

- **Documentation**: [README.md](../README.md)
- **API Reference**: [API.md](API.md)
- **Issues**: GitHub Issues
- **Gemini API**: https://ai.google.dev/gemini-api/docs
- **Cloud Functions**: https://cloud.google.com/functions/docs

## Next Steps

1. Test the deployed function
2. Verify frontend can connect to backend
3. Translate a test SRT file
4. Monitor logs and metrics
5. Optimize based on usage patterns
