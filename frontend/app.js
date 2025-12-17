/**
 * TransSRT Frontend
 * Handles file upload, API communication, and UI updates
 */

// Configuration
const CONFIG = {
    // Production endpoint (Cloud Run Function URL - no path needed)
    API_ENDPOINT: 'https://translate-srt-mbi34yrklq-uc.a.run.app',
    // API_ENDPOINT: 'http://localhost:8080',  // Local development
    MAX_FILE_SIZE: 10 * 1024 * 1024, // 10MB
    ALLOWED_EXTENSIONS: ['.srt'],
    REQUEST_TIMEOUT: 5 * 60 * 1000  // 5 minutes
};

// DOM Elements
const elements = {
    uploadSection: document.getElementById('upload-section'),
    progressSection: document.getElementById('progress-section'),
    successSection: document.getElementById('success-section'),
    errorSection: document.getElementById('error-section'),

    dropZone: document.getElementById('drop-zone'),
    fileInput: document.getElementById('file-input'),
    fileSelectBtn: document.getElementById('file-select-btn'),

    progressFill: document.getElementById('progress-fill'),
    progressText: document.getElementById('progress-text'),

    successMessage: document.getElementById('success-message'),
    downloadBtn: document.getElementById('download-btn'),
    translateAnotherBtn: document.getElementById('translate-another-btn'),

    errorMessage: document.getElementById('error-message'),
    retryBtn: document.getElementById('retry-btn')
};

// State
let currentFile = null;
let translatedBlob = null;
let translatedFilename = null;

/**
 * Initialize app
 */
function initializeApp() {
    // File select button
    elements.fileSelectBtn.addEventListener('click', () => {
        elements.fileInput.click();
    });

    // File input change
    elements.fileInput.addEventListener('change', handleFileSelect);

    // Drag and drop
    elements.dropZone.addEventListener('click', () => {
        elements.fileInput.click();
    });

    elements.dropZone.addEventListener('dragover', handleDragOver);
    elements.dropZone.addEventListener('dragleave', handleDragLeave);
    elements.dropZone.addEventListener('drop', handleDrop);

    // Button actions
    elements.downloadBtn.addEventListener('click', downloadFile);
    elements.translateAnotherBtn.addEventListener('click', resetUI);
    elements.retryBtn.addEventListener('click', retryTranslation);

    console.log('TransSRT initialized');
}

/**
 * Handle file selection from input
 */
function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) {
        processFile(file);
    }
}

/**
 * Handle drag over event
 */
function handleDragOver(event) {
    event.preventDefault();
    event.stopPropagation();
    elements.dropZone.classList.add('drag-over');
}

/**
 * Handle drag leave event
 */
function handleDragLeave(event) {
    event.preventDefault();
    event.stopPropagation();
    elements.dropZone.classList.remove('drag-over');
}

/**
 * Handle file drop event
 */
function handleDrop(event) {
    event.preventDefault();
    event.stopPropagation();
    elements.dropZone.classList.remove('drag-over');

    const files = event.dataTransfer.files;
    if (files.length > 0) {
        processFile(files[0]);
    }
}

/**
 * Validate file
 */
function validateFile(file) {
    // Check if file exists
    if (!file) {
        return { valid: false, error: 'No file selected' };
    }

    // Check file extension
    const fileName = file.name.toLowerCase();
    const hasValidExtension = CONFIG.ALLOWED_EXTENSIONS.some(ext =>
        fileName.endsWith(ext)
    );

    if (!hasValidExtension) {
        return {
            valid: false,
            error: 'Invalid file format. Please upload an SRT file.'
        };
    }

    // Check file size
    if (file.size > CONFIG.MAX_FILE_SIZE) {
        const sizeMB = (CONFIG.MAX_FILE_SIZE / (1024 * 1024)).toFixed(0);
        return {
            valid: false,
            error: `File size exceeds ${sizeMB}MB limit.`
        };
    }

    return { valid: true };
}

/**
 * Process selected file
 */
function processFile(file) {
    // Validate
    const validation = validateFile(file);
    if (!validation.valid) {
        showError(validation.error);
        return;
    }

    currentFile = file;
    uploadAndTranslate(file);
}

/**
 * Upload file and translate
 */
async function uploadAndTranslate(file) {
    // Show progress
    showSection('progress');
    updateProgress(0, 'Step 1/5: Reading file...');
    console.log('[TransSRT] Starting upload and translate process');
    console.log('[TransSRT] File:', file.name, 'Size:', file.size, 'bytes');

    try {
        // Read file as ArrayBuffer
        console.log('[TransSRT] Step 1: Reading file as ArrayBuffer...');
        const arrayBuffer = await file.arrayBuffer();
        console.log('[TransSRT] ArrayBuffer size:', arrayBuffer.byteLength);

        // Convert to Base64
        updateProgress(10, 'Step 2/5: Encoding file to Base64...');
        console.log('[TransSRT] Step 2: Converting to Base64...');
        const uint8Array = new Uint8Array(arrayBuffer);
        let binaryString = '';
        for (let i = 0; i < uint8Array.length; i++) {
            binaryString += String.fromCharCode(uint8Array[i]);
        }
        const base64Content = btoa(binaryString);
        console.log('[TransSRT] Base64 content length:', base64Content.length);

        // Create JSON payload
        const payload = {
            filename: file.name,
            content: base64Content
        };
        console.log('[TransSRT] Payload created, filename:', payload.filename);

        // Update progress
        updateProgress(20, 'Step 3/5: Sending to server and translating (may take 1-3 minutes)...');
        console.log('[TransSRT] Step 3: Making API request to:', CONFIG.API_ENDPOINT);
        console.log('[TransSRT] Request timeout:', CONFIG.REQUEST_TIMEOUT, 'ms');

        // Make API request with timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), CONFIG.REQUEST_TIMEOUT);

        const requestStartTime = Date.now();
        const response = await fetch(CONFIG.API_ENDPOINT, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload),
            signal: controller.signal
        });

        clearTimeout(timeoutId);
        const requestDuration = Date.now() - requestStartTime;
        console.log('[TransSRT] Response received in', requestDuration, 'ms');
        console.log('[TransSRT] Response status:', response.status, response.statusText);
        console.log('[TransSRT] Response headers:', Object.fromEntries(response.headers.entries()));

        // Update progress (response received)
        updateProgress(80, 'Step 4/5: Processing translated content...');

        // Check response
        if (!response.ok) {
            console.error('[TransSRT] Response not OK:', response.status);
            // Try to parse error JSON
            const contentType = response.headers.get('content-type');
            console.log('[TransSRT] Error response content-type:', contentType);
            if (contentType && contentType.includes('application/json')) {
                const errorData = await response.json();
                console.error('[TransSRT] Error data:', errorData);
                throw new Error(errorData.error?.message || 'Translation failed');
            } else {
                const errorText = await response.text();
                console.error('[TransSRT] Error text:', errorText);
                throw new Error(`Server error: ${response.status} ${response.statusText}`);
            }
        }

        // Parse JSON response
        console.log('[TransSRT] Step 4: Parsing JSON response...');
        const result = await response.json();
        console.log('[TransSRT] Result:', {
            success: result.success,
            filename: result.filename,
            entry_count: result.entry_count,
            content_length: result.content?.length
        });

        if (!result.success) {
            console.error('[TransSRT] Success flag is false');
            throw new Error('Translation failed: No success flag in response');
        }

        // Decode Base64 content
        console.log('[TransSRT] Decoding Base64 content...');
        const translatedBinary = atob(result.content);
        const translatedBytes = new Uint8Array(translatedBinary.length);
        for (let i = 0; i < translatedBinary.length; i++) {
            translatedBytes[i] = translatedBinary.charCodeAt(i);
        }
        const blob = new Blob([translatedBytes], { type: 'application/x-subrip' });
        console.log('[TransSRT] Blob created, size:', blob.size);

        // Get filename from response
        const filename = result.filename || file.name.replace('.srt', '_en.srt');
        console.log('[TransSRT] Output filename:', filename);

        // Update progress
        updateProgress(100, 'Step 5/5: Complete! Translated ' + result.entry_count + ' subtitle entries.');

        // Store results
        translatedBlob = blob;
        translatedFilename = filename;

        // Show success with entry count
        const successMsg = `Translated ${result.entry_count} subtitle entries`;
        console.log('[TransSRT] Translation successful!', successMsg);
        setTimeout(() => {
            showSuccess(filename, successMsg);
        }, 500);

    } catch (error) {
        console.error('[TransSRT] Translation error:', error);
        console.error('[TransSRT] Error name:', error.name);
        console.error('[TransSRT] Error message:', error.message);
        console.error('[TransSRT] Error stack:', error.stack);

        let errorMessage = 'An unexpected error occurred.';

        if (error.name === 'AbortError') {
            errorMessage = 'Translation timed out. Your file may be too large.';
            console.error('[TransSRT] Request aborted/timed out');
        } else if (error.message) {
            errorMessage = error.message;
        }

        showError(errorMessage);
    }
}

/**
 * Update progress bar and text
 */
function updateProgress(percentage, text) {
    elements.progressFill.style.width = `${percentage}%`;
    elements.progressText.textContent = text;
}

/**
 * Download translated file
 */
function downloadFile() {
    if (!translatedBlob || !translatedFilename) {
        console.error('No file to download');
        return;
    }

    // Create download link
    const url = URL.createObjectURL(translatedBlob);
    const a = document.createElement('a');
    a.href = url;
    a.download = translatedFilename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    console.log('File downloaded:', translatedFilename);
}

/**
 * Show specific section
 */
function showSection(section) {
    // Hide all sections
    elements.uploadSection.classList.add('hidden');
    elements.progressSection.classList.add('hidden');
    elements.successSection.classList.add('hidden');
    elements.errorSection.classList.add('hidden');

    // Show requested section
    switch (section) {
        case 'upload':
            elements.uploadSection.classList.remove('hidden');
            break;
        case 'progress':
            elements.progressSection.classList.remove('hidden');
            break;
        case 'success':
            elements.successSection.classList.remove('hidden');
            break;
        case 'error':
            elements.errorSection.classList.remove('hidden');
            break;
    }
}

/**
 * Show success state
 */
function showSuccess(filename, additionalMsg = '') {
    let message = `Your file "${filename}" has been translated successfully.`;
    if (additionalMsg) {
        message += ` ${additionalMsg}`;
    }
    elements.successMessage.textContent = message;
    showSection('success');
}

/**
 * Show error state
 */
function showError(message) {
    elements.errorMessage.textContent = message;
    showSection('error');
}

/**
 * Reset UI to initial state
 */
function resetUI() {
    currentFile = null;
    translatedBlob = null;
    translatedFilename = null;
    elements.fileInput.value = '';
    updateProgress(0, '');
    showSection('upload');
}

/**
 * Retry translation with current file
 */
function retryTranslation() {
    if (currentFile) {
        uploadAndTranslate(currentFile);
    } else {
        resetUI();
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeApp);
} else {
    initializeApp();
}
