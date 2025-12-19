"""
TransSRT Cloud Run Function
Main entry point for Korean-to-English subtitle translation service.
"""

import os
import logging
import re
import base64
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename
from io import BytesIO
import functions_framework
from dotenv import load_dotenv

from srt_parser import SRTParser, SRTEntry
from sbv_parser import SBVParser, SBVEntry
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

    filename_lower = file.filename.lower()
    if not (filename_lower.endswith('.srt') or filename_lower.endswith('.sbv')):
        return False, "Invalid file format. Only .srt and .sbv files are accepted"

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
    Output is always SRT format regardless of input format.

    Args:
        input_filename: Original filename (e.g., "movie.srt" or "captions.sbv")

    Returns:
        Output filename (e.g., "movie_en.srt")
    """
    filename_lower = input_filename.lower()
    if filename_lower.endswith('.srt'):
        base = input_filename[:-4]
        return f"{base}_en.srt"
    elif filename_lower.endswith('.sbv'):
        base = input_filename[:-4]
        return f"{base}_en.srt"  # Convert SBV to SRT format
    return f"{input_filename}_en.srt"


def detect_format(content: str) -> str:
    """
    Detect subtitle format (SRT or SBV).

    Args:
        content: Raw subtitle file content

    Returns:
        'srt' or 'sbv'
    """
    srt_parser = SRTParser()
    sbv_parser = SBVParser()

    # Try SRT first (more common)
    if srt_parser.validate(content):
        return 'srt'
    elif sbv_parser.validate(content):
        return 'sbv'
    else:
        return 'unknown'


def process_translation(content: str, filename: str = None) -> tuple[str, int]:
    """
    Process subtitle content translation (SRT or SBV format).

    Args:
        content: Raw subtitle file content
        filename: Optional filename for format detection hint

    Returns:
        (translated_content, entry_count)

    Raises:
        TranslationServiceError: If translation fails
    """
    import time
    overall_start = time.time()

    # Detect format
    file_format = detect_format(content)
    logger.info(f"Detected format: {file_format}")

    # Parse based on format
    try:
        parse_start = time.time()

        if file_format == 'sbv':
            sbv_parser = SBVParser()
            sbv_entries = sbv_parser.parse(content)

            # Convert SBV to SRT entries
            entries = []
            for sbv_entry in sbv_entries:
                srt_timestamp = sbv_parser.sbv_to_srt_timestamp(sbv_entry.timestamp)
                # Extract entry number from position (1-indexed)
                entry_num = len(entries) + 1
                entries.append(SRTEntry(
                    number=str(entry_num),
                    timestamp=srt_timestamp,
                    text=sbv_entry.text
                ))

            parse_time = time.time() - parse_start
            logger.info(f"[TIMING] SBV Parsing & Conversion: {parse_time:.3f}s ({len(entries)} entries)")

        elif file_format == 'srt':
            srt_parser = SRTParser()
            entries = srt_parser.parse(content)
            parse_time = time.time() - parse_start
            logger.info(f"[TIMING] SRT Parsing: {parse_time:.3f}s ({len(entries)} entries)")

        else:
            raise ValueError("Unable to detect subtitle format. File must be valid SRT or SBV format.")

    except ValueError as e:
        raise TranslationServiceError(
            message=str(e),
            code="INVALID_SUBTITLE_FORMAT",
            status_code=400
        )

    # Create chunks
    try:
        chunk_start = time.time()
        chunks = create_chunks(entries, chunk_size=CHUNK_SIZE)
        chunk_time = time.time() - chunk_start
        logger.info(f"[TIMING] Chunking: {chunk_time:.3f}s ({len(chunks)} chunks of size {CHUNK_SIZE})")
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
        translate_start = time.time()
        translated_chunks = translate_subtitles(
            chunks=chunks,
            api_key=GEMINI_API_KEY,
            model=GEMINI_MODEL,
            max_concurrent=MAX_CONCURRENT
        )
        translate_time = time.time() - translate_start
        logger.info(f"[TIMING] Translation: {translate_time:.3f}s ({len(translated_chunks)} chunks)")
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
    reassemble_start = time.time()
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
    reassemble_time = time.time() - reassemble_start
    logger.info(f"[TIMING] Reassembly: {reassemble_time:.3f}s ({len(translated_entries)} entries)")

    # Format output (always output as SRT format)
    try:
        format_start = time.time()
        srt_formatter = SRTParser()
        translated_content = srt_formatter.format_output(translated_entries)
        format_time = time.time() - format_start
        logger.info(f"[TIMING] Formatting: {format_time:.3f}s")
    except Exception as e:
        raise TranslationServiceError(
            message=f"Failed to format output: {e}",
            code="FORMAT_FAILED",
            status_code=500
        )

    overall_time = time.time() - overall_start
    logger.info(f"[TIMING] ========== TOTAL PROCESS TIME: {overall_time:.3f}s ==========")
    logger.info(f"[TIMING] Breakdown - Parse: {parse_time:.3f}s | Chunk: {chunk_time:.3f}s | Translate: {translate_time:.3f}s | Reassemble: {reassemble_time:.3f}s | Format: {format_time:.3f}s")

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
        # Debug logging
        logger.info(f"Request method: {request.method}")
        logger.info(f"Request content type: {request.content_type}")
        logger.info(f"Request files keys: {list(request.files.keys())}")
        logger.info(f"Request form keys: {list(request.form.keys())}")

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

        # Translate (pass filename for format detection hint)
        translated_content, entry_count = process_translation(content, original_filename)

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
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': CORS_ORIGINS,
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type',
        }
        return ('', 204, headers)

    # Route to appropriate handler
    path = request.path
    if path == '/health' or path == '/translate-srt/health':
        return jsonify({
            'status': 'healthy',
            'service': 'TransSRT',
            'version': '1.0.0'
        })

    # Accept JSON request with Base64 encoded file
    try:
        content_type = request.headers.get('Content-Type', '')

        # Validate content type
        if 'application/json' not in content_type:
            return jsonify({
                'error': {
                    'code': 'INVALID_REQUEST',
                    'message': 'Request must be application/json'
                }
            }), 400

        # Parse JSON data
        data = request.get_json()
        if not data:
            return jsonify({
                'error': {
                    'code': 'INVALID_REQUEST',
                    'message': 'Request body must be valid JSON'
                }
            }), 400

        logger.info(f"Received JSON request with keys: {list(data.keys())}")

        # Validate required fields
        if 'filename' not in data or 'content' not in data:
            return jsonify({
                'error': {
                    'code': 'INVALID_REQUEST',
                    'message': 'Request must include "filename" and "content" fields'
                }
            }), 400

        filename = data['filename']
        base64_content = data['content']

        # Validate file extension
        filename_lower = filename.lower()
        if not (filename_lower.endswith('.srt') or filename_lower.endswith('.sbv')):
            return jsonify({
                'error': {
                    'code': 'INVALID_FILE',
                    'message': 'File must be a .srt or .sbv file'
                }
            }), 400

        # Decode Base64 content
        try:
            file_data = base64.b64decode(base64_content)
        except Exception as e:
            return jsonify({
                'error': {
                    'code': 'INVALID_REQUEST',
                    'message': f'Invalid Base64 encoding: {str(e)}'
                }
            }), 400

        # Validate file size
        file_size = len(file_data)
        max_size = MAX_FILE_SIZE_MB * 1024 * 1024
        if file_size > max_size:
            return jsonify({
                'error': {
                    'code': 'INVALID_FILE',
                    'message': f'File size exceeds {MAX_FILE_SIZE_MB}MB limit'
                }
            }), 400

        # Decode file content - try multiple encodings
        file_content = None
        for encoding in ['utf-8', 'utf-8-sig', 'cp949', 'euc-kr']:
            try:
                file_content = file_data.decode(encoding)
                logger.info(f"Successfully decoded file with {encoding}")
                break
            except UnicodeDecodeError:
                continue

        if file_content is None:
            return jsonify({
                'error': {
                    'code': 'INVALID_FILE',
                    'message': 'Unable to decode file. Please ensure it is UTF-8 or EUC-KR encoded'
                }
            }), 400

        logger.info(f"Processing file: {filename} ({file_size} bytes)")

        # Translate (pass filename for format detection hint)
        translated_content, entry_count = process_translation(file_content, filename)

        # Generate output filename (use original filename directly)
        # Note: secure_filename removes non-ASCII characters, breaking Korean filenames
        # Since we're using Base64 JSON (not multipart), we can safely use original filename
        output_filename = generate_output_filename(filename)

        # Return as Base64 JSON response
        translated_bytes = translated_content.encode('utf-8')
        translated_base64 = base64.b64encode(translated_bytes).decode('utf-8')

        response = jsonify({
            'success': True,
            'filename': output_filename,
            'content': translated_base64,
            'entry_count': entry_count
        })
        response.headers.add('Access-Control-Allow-Origin', CORS_ORIGINS)
        logger.info(f"Successfully translated {entry_count} entries from {filename}")
        return response

    except TranslationServiceError as e:
        logger.error(f"{e.code}: {e.message}")
        response = jsonify({'error': {'code': e.code, 'message': e.message}})
        response.status_code = e.status_code
        response.headers.add('Access-Control-Allow-Origin', CORS_ORIGINS)
        return response
    except Exception as e:
        logger.error(f"Request handling error: {str(e)}", exc_info=True)
        response = jsonify({
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': f'Request handling failed: {str(e)}'
            }
        })
        response.status_code = 500
        response.headers.add('Access-Control-Allow-Origin', CORS_ORIGINS)
        return response


# For local testing
if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
