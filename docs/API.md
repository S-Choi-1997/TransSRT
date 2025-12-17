

# TransSRT API Documentation

RESTful API for translating Korean SRT subtitle files to English using Google Gemini AI.

## Base URL

```
https://us-central1-YOUR-PROJECT-ID.cloudfunctions.net/translate-srt
```

## Authentication

No authentication required. The API is public and rate-limited by:
- Cloud Run Functions: Per-instance concurrency limits
- Gemini API: 15 requests per minute (free tier)

## Endpoints

### POST /translate

Translate a Korean SRT file to English.

#### Request

**Content-Type:** `multipart/form-data`

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | File | Yes | SRT file to translate (max 10MB) |

**Example (curl):**

```bash
curl -X POST \
  -F 'file=@movie.srt' \
  https://us-central1-transsrt.cloudfunctions.net/translate-srt/translate
```

**Example (JavaScript):**

```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);

const response = await fetch('https://your-function-url/translate', {
    method: 'POST',
    body: formData
});

if (response.ok) {
    const blob = await response.blob();
    // Download file
} else {
    const error = await response.json();
    console.error(error);
}
```

#### Response (Success)

**Status Code:** `200 OK`

**Content-Type:** `application/x-subrip`

**Headers:**
```
Content-Disposition: attachment; filename="movie_en.srt"
Access-Control-Allow-Origin: *
```

**Body:** Binary SRT file content

**Example Response Headers:**
```
HTTP/1.1 200 OK
Content-Type: application/x-subrip
Content-Disposition: attachment; filename="연락올까-영어_en.srt"
Content-Length: 12345
```

#### Response (Error)

**Content-Type:** `application/json`

**Error Response Structure:**

```json
{
    "error": {
        "code": "ERROR_CODE",
        "message": "Human-readable error message"
    }
}
```

**Error Codes:**

| Code | Status | Description |
|------|--------|-------------|
| `NO_FILE` | 400 | No file provided in request |
| `INVALID_FILE` | 400 | File validation failed (size, format) |
| `INVALID_SRT_FORMAT` | 400 | SRT file format is malformed |
| `FILE_TOO_LARGE` | 413 | File exceeds 10MB limit |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests, try again later |
| `TRANSLATION_FAILED` | 500 | Translation service error |
| `TIMEOUT` | 504 | Request timed out (file too large) |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

**Example Error Response:**

```json
{
    "error": {
        "code": "INVALID_SRT_FORMAT",
        "message": "Could not parse SRT file. Please verify format."
    }
}
```

### GET /health

Health check endpoint.

#### Request

```bash
curl https://your-function-url/health
```

#### Response

**Status Code:** `200 OK`

**Content-Type:** `application/json`

```json
{
    "status": "healthy",
    "service": "TransSRT",
    "version": "1.0.0"
}
```

## Rate Limits

### Free Tier Limits

**Gemini API:**
- 15 requests per minute
- Automatically handled with exponential backoff
- Returns 429 if limit exceeded

**Cloud Run Functions:**
- 10 concurrent requests per instance
- Auto-scales up to 10 instances
- Total: ~100 concurrent requests

### Handling Rate Limits

When rate limit is exceeded (429 status):

1. **Exponential Backoff:**
   - Wait 2 seconds, retry
   - Wait 4 seconds, retry
   - Give up after 3 attempts

2. **Client-Side Queuing:**
   - Queue requests on frontend
   - Process sequentially
   - Show wait time to user

**Example:**

```javascript
async function translateWithRetry(file, maxRetries = 3) {
    for (let i = 0; i < maxRetries; i++) {
        try {
            const response = await fetch(API_URL, {
                method: 'POST',
                body: createFormData(file)
            });

            if (response.status === 429) {
                const waitTime = Math.pow(2, i) * 1000;
                await new Promise(resolve => setTimeout(resolve, waitTime));
                continue;
            }

            return response;
        } catch (error) {
            if (i === maxRetries - 1) throw error;
        }
    }
}
```

## File Format

### Input Format

**Required:**
- File extension: `.srt`
- Encoding: UTF-8
- Format: Standard SRT or single-line SRT

**Supported SRT Formats:**

**Standard SRT:**
```
1
00:00:01,000 --> 00:00:03,000
안녕하세요

2
00:00:03,500 --> 00:00:05,000
반갑습니다
```

**Single-line SRT:**
```
1 00:00:01,000 --> 00:00:03,000 안녕하세요
2 00:00:03,500 --> 00:00:05,000 반갑습니다
```

### Output Format

**Standard SRT format with English translations:**

```
1
00:00:01,000 --> 00:00:03,000
Hello

2
00:00:03,500 --> 00:00:05,000
Nice to meet you
```

**Filename Convention:**
- Input: `movie.srt`
- Output: `movie_en.srt`

## Translation Details

### Process Flow

1. **Upload:** Client uploads SRT file
2. **Validation:** Check file size, format, extension
3. **Parsing:** Extract subtitle entries with regex
4. **Chunking:** Split into chunks of 50 entries
5. **Translation:** Parallel async translation with Gemini
6. **Reassembly:** Combine translated chunks
7. **Return:** Send translated SRT file

### Performance

**Typical Processing Times:**

| Entries | Chunks | Time |
|---------|--------|------|
| 100 | 2 | 4-6 sec |
| 500 | 10 | 6-8 sec |
| 1000 | 20 | 8-12 sec |
| 2000 | 40 | 16-24 sec |

**Factors affecting speed:**
- Number of subtitle entries
- Gemini API response time
- Network latency
- Concurrent requests

### Translation Quality

**Gemini Model:** `gemini-1.5-flash`

**Features:**
- Natural, conversational English
- Context-aware translation (3-entry overlap between chunks)
- Preserves timing and format
- Maintains cultural context where appropriate

## CORS Configuration

**Default (Development):**
```
Access-Control-Allow-Origin: *
```

**Production (Recommended):**
```
Access-Control-Allow-Origin: https://yourusername.github.io
```

Configure via environment variable:
```bash
gcloud functions deploy translate-srt \
  --update-env-vars CORS_ORIGINS=https://yourusername.github.io
```

## Error Handling Best Practices

### Client-Side

1. **Validate before upload:**
   ```javascript
   if (file.size > 10 * 1024 * 1024) {
       alert('File too large');
       return;
   }
   if (!file.name.endsWith('.srt')) {
       alert('Invalid format');
       return;
   }
   ```

2. **Handle all error codes:**
   ```javascript
   if (!response.ok) {
       const error = await response.json();
       switch (error.code) {
           case 'RATE_LIMIT_EXCEEDED':
               showMessage('Too busy, try again in a minute');
               break;
           case 'INVALID_SRT_FORMAT':
               showMessage('Invalid SRT file');
               break;
           // ... handle other codes
       }
   }
   ```

3. **Implement timeout:**
   ```javascript
   const controller = new AbortController();
   setTimeout(() => controller.abort(), 5 * 60 * 1000);

   fetch(url, { signal: controller.signal });
   ```

### Server-Side

- All errors include proper HTTP status codes
- Error messages are user-friendly
- Detailed errors logged server-side
- Automatic retry for transient failures

## Security

### Input Validation

**File checks:**
- Extension whitelist: `.srt` only
- Size limit: 10MB
- Content validation: Must parse as valid SRT

**No sensitive data:**
- API is stateless
- Files not stored
- Processed in-memory only

### Rate Limiting

**Prevents abuse:**
- Per-IP rate limiting (Cloud Run built-in)
- Gemini API quota enforcement
- Max concurrent requests: 10 per instance

## Monitoring

### Key Metrics

**Track these metrics:**
- Request count
- Success rate
- Average latency
- Error rate by code
- Gemini API usage

**View in Cloud Console:**
```
https://console.cloud.google.com/functions/details/us-central1/translate-srt
```

### Logging

**View logs:**
```bash
gcloud functions logs read translate-srt \
  --region=us-central1 \
  --gen2 \
  --limit=50
```

**Log levels:**
- `INFO`: Normal operations
- `WARNING`: Rate limits, retries
- `ERROR`: Translation failures, server errors

## Examples

### Complete Translation Flow

```javascript
async function translateSubtitle(file) {
    try {
        // 1. Validate
        if (!file.name.endsWith('.srt')) {
            throw new Error('Invalid file format');
        }

        // 2. Upload
        const formData = new FormData();
        formData.append('file', file);

        // 3. Request
        const response = await fetch(API_ENDPOINT, {
            method: 'POST',
            body: formData,
            signal: AbortSignal.timeout(5 * 60 * 1000)
        });

        // 4. Handle response
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error.message);
        }

        // 5. Download
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);

        const a = document.createElement('a');
        a.href = url;
        a.download = file.name.replace('.srt', '_en.srt');
        a.click();

        URL.revokeObjectURL(url);

        return { success: true };

    } catch (error) {
        console.error('Translation failed:', error);
        return { success: false, error: error.message };
    }
}
```

### Testing with curl

```bash
# Basic translation
curl -X POST \
  -F 'file=@test.srt' \
  -o 'test_en.srt' \
  https://your-function-url/translate

# With verbose output
curl -X POST \
  -F 'file=@test.srt' \
  -v \
  https://your-function-url/translate

# Health check
curl https://your-function-url/health
```

## Support

- **Issues:** GitHub Issues
- **Documentation:** [DEPLOYMENT.md](DEPLOYMENT.md)
- **API Changes:** Check release notes

## Changelog

### v1.0.0 (2025-01-01)

- Initial API release
- POST /translate endpoint
- GET /health endpoint
- Gemini 1.5 Flash integration
- 50-entry chunking with 3-entry overlap
- 10 concurrent requests
- Comprehensive error handling
