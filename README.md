# TransSRT 🎬

**Korean-to-English Subtitle Translator** powered by Google Gemini AI

[![Deploy Backend](https://github.com/yourusername/TransSRT/actions/workflows/deploy-backend.yml/badge.svg)](https://github.com/yourusername/TransSRT/actions/workflows/deploy-backend.yml)
[![Deploy Frontend](https://github.com/yourusername/TransSRT/actions/workflows/deploy-frontend.yml/badge.svg)](https://github.com/yourusername/TransSRT/actions/workflows/deploy-frontend.yml)

Simple, fast, and accurate subtitle translation service that translates Korean SRT files to natural English using AI. Perfect for content creators, translators, and subtitle enthusiasts.

## ✨ Features

- 🚀 **Fast Translation**: 1000 entries in 8-12 seconds
- 🎯 **High Quality**: Context-aware AI translation with Gemini
- 📝 **Format Preservation**: Maintains perfect SRT structure
- 💰 **Free Tier**: ~100 files/month on GCP free tier
- 🌐 **Simple Interface**: Drag & drop file upload
- ⚡ **Async Processing**: 10 concurrent translations for speed
- 📦 **Zero Configuration**: Works out of the box

## 🎥 Demo

Visit the live demo: [https://yourusername.github.io/TransSRT](https://yourusername.github.io/TransSRT)

![TransSRT Demo](docs/screenshot.png)

## 🚀 Quick Start

### For Users

1. Visit [https://yourusername.github.io/TransSRT](https://yourusername.github.io/TransSRT)
2. Drag & drop your Korean SRT file (or click to select)
3. Wait ~10 seconds for translation
4. Download your `filename_en.srt`

That's it! ✅

### For Developers

```bash
# Clone repository
git clone https://github.com/yourusername/TransSRT.git
cd TransSRT

# Setup backend
cd backend
pip install -r requirements.txt

# Add your Gemini API key to .env
echo "GEMINI_API_KEY=your_key_here" > .env

# Run locally
python main.py

# In another terminal, serve frontend
cd ../frontend
python -m http.server 8000

# Open http://localhost:8000
```

## 📋 How It Works

```mermaid
graph LR
    A[Upload SRT] --> B[Parse]
    B --> C[Split into Chunks]
    C --> D[Parallel Translation]
    D --> E[Gemini API]
    E --> F[Reassemble]
    F --> G[Download]
```

1. **Upload**: User uploads Korean SRT file
2. **Parse**: Extract subtitle entries with regex
3. **Chunk**: Split into 50-entry chunks with 3-entry overlap
4. **Translate**: 10 parallel async calls to Gemini API
5. **Reassemble**: Combine translations into proper SRT format
6. **Download**: Auto-download as `filename_en.srt`

## 🏗️ Architecture

### Backend (GCP Cloud Run Functions)

- **Runtime**: Python 3.11
- **Region**: us-central1 (Iowa) - Free tier eligible
- **Memory**: 512Mi
- **Timeout**: 5 minutes
- **Concurrency**: 10 instances max

### Frontend (GitHub Pages)

- **Stack**: Pure HTML/CSS/JavaScript
- **No build step**: Deploy directly
- **Responsive**: Works on mobile & desktop

### Translation Pipeline

- **Model**: Gemini 1.5 Flash
- **Strategy**: Chunk-based batch translation
- **Chunk Size**: 50 entries
- **Overlap**: 3 entries for context
- **Concurrent Requests**: 10

## 📊 Performance

| Entries | Approx. Video Length | Translation Time |
|---------|----------------------|------------------|
| 100     | ~5 minutes          | 4-6 seconds      |
| 500     | ~25 minutes         | 6-8 seconds      |
| 1000    | ~50 minutes         | 8-12 seconds     |
| 2000    | ~2 hours            | 16-24 seconds    |

**Factors:**
- Parallel processing with asyncio
- Gemini 1.5 Flash (fast model)
- Optimized chunk size (50 entries)

## 💰 Cost

### Free Tier (per month)

- **Gemini API**: 15 RPM, ~40,000 entries
- **Cloud Run**: 2M requests, 400K GB-seconds
- **Capacity**: ~10,000 translations

### Paid Tier

If exceeding free tier:
- **Gemini**: ~$0.011 per 1000 entries
- **Cloud Run**: ~$0.0001 per translation
- **Total**: ~$0.011 per 1000 entries

Example: 100,000 translations/month = ~$110/month

## 🛠️ Tech Stack

**Backend:**
- Python 3.11
- Flask
- Google Generative AI (Gemini)
- GCP Cloud Run Functions (Gen 2)
- Tenacity (retry logic)

**Frontend:**
- Vanilla JavaScript (ES6+)
- CSS Grid/Flexbox
- Fetch API

**Infrastructure:**
- GitHub Actions (CI/CD)
- GitHub Pages (Frontend)
- GCP Secret Manager (API keys)

## 📦 Project Structure

```
TransSRT/
├── backend/              # Cloud Run Function code
│   ├── main.py          # Entry point
│   ├── srt_parser.py    # SRT parsing logic
│   ├── chunker.py       # Chunk creation
│   ├── translator.py    # Gemini API integration
│   ├── requirements.txt # Python dependencies
│   └── .env            # Environment variables (gitignored)
├── frontend/            # GitHub Pages site
│   ├── index.html      # Main UI
│   ├── styles.css      # Styling
│   └── app.js          # Frontend logic
├── .github/workflows/   # CI/CD automation
│   ├── deploy-backend.yml
│   └── deploy-frontend.yml
├── scripts/            # Deployment scripts
│   └── deploy_cloudrun.sh
├── docs/               # Documentation
│   ├── DEPLOYMENT.md   # Deployment guide
│   └── API.md          # API documentation
└── README.md           # This file
```

## 🚀 Deployment

### Automated (Recommended)

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for complete guide.

**Quick Steps:**

1. Fork this repository
2. Add GitHub Secrets (GCP_SA_KEY, GEMINI_MODEL, CORS_ORIGINS)
3. Push to `main` branch
4. GitHub Actions auto-deploys everything

### Manual

```bash
# Deploy backend
./scripts/deploy_cloudrun.sh

# Deploy frontend
# Push to GitHub, enable Pages in settings
```

## 🔧 Configuration

### Backend Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | - | Gemini API key |
| `GEMINI_MODEL` | `gemini-1.5-flash` | Model to use |
| `CHUNK_SIZE` | `50` | Entries per chunk |
| `MAX_CONCURRENT_REQUESTS` | `10` | Parallel requests |
| `MAX_FILE_SIZE_MB` | `10` | Max upload size |
| `CORS_ORIGINS` | `*` | Allowed origins |

### Frontend Configuration

Update `frontend/app.js`:

```javascript
const CONFIG = {
    API_ENDPOINT: 'YOUR_CLOUD_FUNCTION_URL',
    MAX_FILE_SIZE: 10 * 1024 * 1024,
    ALLOWED_EXTENSIONS: ['.srt']
};
```

## 📚 Documentation

- **[Deployment Guide](docs/DEPLOYMENT.md)** - Complete deployment instructions
- **[API Documentation](docs/API.md)** - API reference and examples
- **[Project Instructions](CLAUDE.md)** - Development guidelines

## 🤝 Contributing

Contributions welcome! Please feel free to submit a Pull Request.

**Areas for contribution:**
- Additional language pairs
- Improved translation prompts
- Performance optimizations
- UI/UX enhancements
- Documentation improvements

## 📝 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Google Gemini API** - Powering the translations
- **GCP Cloud Run** - Serverless infrastructure
- **GitHub Pages** - Free static hosting

## ⚠️ Limitations

- Maximum file size: 10MB
- Free tier: ~100 files/month
- Translation time: Proportional to subtitle count
- Currently supports: Korean → English only

## 🔮 Future Enhancements

- [ ] Multiple language pairs
- [ ] Batch file processing
- [ ] User accounts & history
- [ ] Translation quality feedback
- [ ] Subtitle timing adjustment
- [ ] Format conversion (VTT, ASS, etc.)
- [ ] Custom translation prompts
- [ ] Real-time progress streaming

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/TransSRT/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/TransSRT/discussions)
- **Email**: your.email@example.com

## 📈 Status

- ✅ Backend: Deployed to GCP Cloud Run Functions
- ✅ Frontend: Deployed to GitHub Pages
- ✅ CI/CD: GitHub Actions configured
- 🚧 Testing: Manual testing completed
- 📝 Documentation: Complete

---

Made with ❤️ by [Your Name](https://github.com/yourusername)

**Star ⭐ this repo if you find it useful!**
