/**
 * TransSRT Frontend
 * Handles file upload, API communication, and UI updates
 */

// Configuration
const CONFIG = {
    // Production endpoint (Cloud Run Service URL)
    API_ENDPOINT: 'https://translate-srt-mbi34yrklq-uc.a.run.app/translate',
    // API_ENDPOINT: 'http://localhost:8080/translate',  // Local development
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
    updateProgress(0, 'Reading file...');

    try {
        // Read file as ArrayBuffer
        const arrayBuffer = await file.arrayBuffer();

        // Convert to Base64
        updateProgress(10, 'Encoding file...');
        const uint8Array = new Uint8Array(arrayBuffer);
        let binaryString = '';
        for (let i = 0; i < uint8Array.length; i++) {
            binaryString += String.fromCharCode(uint8Array[i]);
        }
        const base64Content = btoa(binaryString);

        // Create JSON payload
        const payload = {
            filename: file.name,
            content: base64Content
        };

        // Update progress
        updateProgress(30, 'Uploading to server...');

        // Make API request with timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), CONFIG.REQUEST_TIMEOUT);

        const response = await fetch(CONFIG.API_ENDPOINT, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload),
            signal: controller.signal
        });

        clearTimeout(timeoutId);

        // Update progress
        updateProgress(60, 'Translating subtitles...');

        // Check response
        if (!response.ok) {
            // Try to parse error JSON
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                const errorData = await response.json();
                throw new Error(errorData.error?.message || 'Translation failed');
            } else {
                throw new Error(`Server error: ${response.status} ${response.statusText}`);
            }
        }

        // Parse JSON response
        updateProgress(80, 'Processing translation...');
        const result = await response.json();

        if (!result.success) {
            throw new Error('Translation failed: No success flag in response');
        }

        // Decode Base64 content
        const translatedBinary = atob(result.content);
        const translatedBytes = new Uint8Array(translatedBinary.length);
        for (let i = 0; i < translatedBinary.length; i++) {
            translatedBytes[i] = translatedBinary.charCodeAt(i);
        }
        const blob = new Blob([translatedBytes], { type: 'application/x-subrip' });

        // Get filename from response
        const filename = result.filename || file.name.replace('.srt', '_en.srt');

        // Update progress
        updateProgress(100, 'Translation complete!');

        // Store results
        translatedBlob = blob;
        translatedFilename = filename;

        // Show success with entry count
        const successMsg = `Translated ${result.entry_count} subtitle entries`;
        setTimeout(() => {
            showSuccess(filename, successMsg);
        }, 500);

    } catch (error) {
        console.error('Translation error:', error);

        let errorMessage = 'An unexpected error occurred.';

        if (error.name === 'AbortError') {
            errorMessage = 'Translation timed out. Your file may be too large.';
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
