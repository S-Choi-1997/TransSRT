"""
TransSRT Cloud Run Function
Main entry point for Korean-to-English subtitle translation service.
"""

import os
import logging
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename
from io import BytesIO
import functions_framework
from dotenv import load_dotenv

from srt_parser import SRTParser, SRTEntry
from chunker import create_chunks
from translator import translate_subtitles, TranslationError

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from environment variables
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')
CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', '50'))
MAX_CONCURRENT = int(os.getenv('MAX_CONCURRENT_REQUESTS', '10'))
MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE_MB', '10'))
CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*')

# Flask app
app = Flask(__name__)


class TranslationServiceError(Exception):
    """Custom exception for service errors."""
    def __init__(self, message: str, code: str, status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(self.message)


def validate_file(file) -> tuple[bool, str]:
    """
    Validate uploaded file.

    Returns:
        (is_valid, error_message)
    """
    if not file:
        return False, "No file provided"

    if file.filename == '':
        return False, "No file selected"

    if not file.filename.lower().endswith('.srt'):
        return False, "Invalid file format. Only .srt files are accepted"

    # Check file size
    file.seek(0, 2)  # Seek to end
    size = file.tell()
    file.seek(0)  # Reset to beginning

    max_size = MAX_FILE_SIZE_MB * 1024 * 1024
    if size > max_size:
        return False, f"File size exceeds {MAX_FILE_SIZE_MB}MB limit"

    return True, ""


def generate_output_filename(input_filename: str) -> str:
    """
    Generate output filename with _en suffix.

    Args:
        input_filename: Original filename (e.g., "movie.srt")

    Returns:
        Output filename (e.g., "movie_en.srt")
    """
    if input_filename.lower().endswith('.srt'):
        base = input_filename[:-4]
        return f"{base}_en.srt"
    return f"{input_filename}_en.srt"


def process_translation(content: str) -> tuple[str, int]:
    """
    Process SRT content translation.

    Args:
        content: Raw SRT file content

    Returns:
        (translated_content, entry_count)

    Raises:
        TranslationServiceError: If translation fails
    """
    # Parse SRT
    parser = SRTParser()

    try:
        entries = parser.parse(content)
        logger.info(f"Parsed {len(entries)} SRT entries")
    except ValueError as e:
        raise TranslationServiceError(
            message=str(e),
            code="INVALID_SRT_FORMAT",
            status_code=400
        )

    # Create chunks
    try:
        chunks = create_chunks(entries, chunk_size=CHUNK_SIZE)
        logger.info(f"Created {len(chunks)} chunks (size={CHUNK_SIZE})")
    except Exception as e:
        raise TranslationServiceError(
            message=f"Failed to create chunks: {e}",
            code="CHUNKING_FAILED",
            status_code=500
        )

    # Translate chunks
    if not GEMINI_API_KEY:
        raise TranslationServiceError(
            message="Gemini API key not configured",
            code="MISSING_API_KEY",
            status_code=500
        )

    try:
        translated_chunks = translate_subtitles(
            chunks=chunks,
            api_key=GEMINI_API_KEY,
            model=GEMINI_MODEL,
            max_concurrent=MAX_CONCURRENT
        )
        logger.info(f"Translated {len(translated_chunks)} chunks")
    except TranslationError as e:
        raise TranslationServiceError(
            message=str(e),
            code="TRANSLATION_FAILED",
            status_code=500
        )
    except Exception as e:
        error_msg = str(e).lower()
        if 'rate limit' in error_msg or '429' in error_msg:
            raise TranslationServiceError(
                message="Rate limit exceeded. Please try again later.",
                code="RATE_LIMIT_EXCEEDED",
                status_code=429
            )
        elif 'timeout' in error_msg:
            raise TranslationServiceError(
                message="Translation timed out. File may be too large.",
                code="TIMEOUT",
                status_code=504
            )
        else:
            raise TranslationServiceError(
                message=f"Translation failed: {e}",
                code="TRANSLATION_FAILED",
                status_code=500
            )

    # Reassemble translated entries
    translated_entries = []
    for i, chunk in enumerate(chunks):
        translations = translated_chunks[i]
        for j, entry in enumerate(chunk.entries):
            if j < len(translations):
                translated_entry = SRTEntry(
                    number=entry.number,
                    timestamp=entry.timestamp,
                    text=translations[j]
                )
                translated_entries.append(translated_entry)

    # Format output
    try:
        translated_content = parser.format_output(translated_entries)
        logger.info(f"Formatted {len(translated_entries)} translated entries")
    except Exception as e:
        raise TranslationServiceError(
            message=f"Failed to format output: {e}",
            code="FORMAT_FAILED",
            status_code=500
        )

    return translated_content, len(translated_entries)


@app.route('/translate', methods=['POST', 'OPTIONS'])
def translate():
    """
    Main translation endpoint.

    Accepts: multipart/form-data with 'file' field
    Returns: Translated SRT file or error JSON
    """
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', CORS_ORIGINS)
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST')
        return response

    try:
        # Validate file
        if 'file' not in request.files:
            raise TranslationServiceError(
                message="No file part in request",
                code="NO_FILE",
                status_code=400
            )

        file = request.files['file']
        is_valid, error_msg = validate_file(file)

        if not is_valid:
            raise TranslationServiceError(
                message=error_msg,
                code="INVALID_FILE",
                status_code=400
            )

        # Read file content
        original_filename = secure_filename(file.filename)
        content = file.read().decode('utf-8')
        logger.info(f"Processing file: {original_filename}")

        # Translate
        translated_content, entry_count = process_translation(content)

        # Generate output filename
        output_filename = generate_output_filename(original_filename)

        # Create response
        output_buffer = BytesIO(translated_content.encode('utf-8'))
        output_buffer.seek(0)

        response = send_file(
            output_buffer,
            mimetype='application/x-subrip',
            as_attachment=True,
            download_name=output_filename
        )

        # Add CORS headers
        response.headers.add('Access-Control-Allow-Origin', CORS_ORIGINS)
        logger.info(f"Successfully translated {entry_count} entries")

        return response

    except TranslationServiceError as e:
        logger.error(f"Translation service error: {e.message} ({e.code})")
        response = jsonify({
            'error': {
                'code': e.code,
                'message': e.message
            }
        })
        response.status_code = e.status_code
        response.headers.add('Access-Control-Allow-Origin', CORS_ORIGINS)
        return response

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        response = jsonify({
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': f'An unexpected error occurred: {str(e)}'
            }
        })
        response.status_code = 500
        response.headers.add('Access-Control-Allow-Origin', CORS_ORIGINS)
        return response


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'TransSRT',
        'version': '1.0.0'
    })


# Cloud Run Functions entry point
@functions_framework.http
def translate_srt(request):
    """
    Cloud Run Function entry point.

    Args:
        request: Flask request object

    Returns:
        Flask response object
    """
    with app.request_context(request.environ):
        return app.full_dispatch_request()


# For local testing
if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
