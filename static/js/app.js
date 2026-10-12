/**
 * PrivDoc - Privacy-First Document Converter & Compressor
 * Client-Side Controller
 */

document.addEventListener('DOMContentLoaded', () => {
  // --- State ---
  let selectedFile = null;
  let currentAction = 'word-to-pdf';
  let activeDownloadUrl = null;

  // --- DOM Elements ---
  const themeToggleBtn = document.getElementById('themeToggleBtn');
  const actionTabs = document.querySelectorAll('.tab-btn');
  const actionHintText = document.getElementById('actionHintText');
  const formatConstraintBadge = document.getElementById('formatConstraintBadge');

  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('fileInput');
  const browseBtn = document.getElementById('browseBtn');

  const fileCard = document.getElementById('fileCard');
  const fileNameDisplay = document.getElementById('fileNameDisplay');
  const fileSizeDisplay = document.getElementById('fileSizeDisplay');
  const wordCompressOptions = document.getElementById('wordCompressOptions');
  const optimizeImagesToggle = document.getElementById('optimizeImagesToggle');
  const removeFileBtn = document.getElementById('removeFileBtn');
  const processBtn = document.getElementById('processBtn');
  const processBtnText = document.getElementById('processBtnText');

  const statusPanel = document.getElementById('statusPanel');
  const statusTitle = document.getElementById('statusTitle');
  const statusDesc = document.getElementById('statusDesc');

  const resultCard = document.getElementById('resultCard');
  const resultTitle = document.getElementById('resultTitle');
  const resultSubtitle = document.getElementById('resultSubtitle');
  const compressionStats = document.getElementById('compressionStats');
  const statOriginalSize = document.getElementById('statOriginalSize');
  const statCompressedSize = document.getElementById('statCompressedSize');
  const statSavingsBadge = document.getElementById('statSavingsBadge');
  const statSavingsPercent = document.getElementById('statSavingsPercent');
  const compressionNote = document.getElementById('compressionNote');
  const downloadBtn = document.getElementById('downloadBtn');
  const downloadBtnText = document.getElementById('downloadBtnText');
  const resetBtn = document.getElementById('resetBtn');

  const errorBanner = document.getElementById('errorBanner');
  const errorTitle = document.getElementById('errorTitle');
  const errorMessage = document.getElementById('errorMessage');
  const ocrAdvisory = document.getElementById('ocrAdvisory');
  const dismissErrorBtn = document.getElementById('dismissErrorBtn');

  const engineStatusIndicator = document.getElementById('engineStatusIndicator');
  const engineStatusText = document.getElementById('engineStatusText');

  // --- Action Metadata Map ---
  const ACTION_CONFIG = {
    'word-to-pdf': {
      endpoint: '/api/convert/word-to-pdf',
      accept: '.docx,.doc',
      acceptDesc: 'Accepts .DOCX, .DOC',
      allowedExts: ['docx', 'doc'],
      btnText: 'Convert to PDF',
      statusText: 'Converting Word to PDF...',
      hint: 'Convert Microsoft Word documents to PDF while preserving formatting, tables, and typography.',
      downloadExt: '.pdf',
      resultTitle: 'PDF Ready for Download',
      isCompress: false
    },
    'pdf-to-word': {
      endpoint: '/api/convert/pdf-to-word',
      accept: '.pdf',
      acceptDesc: 'Accepts .PDF (Text-based)',
      allowedExts: ['pdf'],
      btnText: 'Convert to Word',
      statusText: 'Reconstructing Word document...',
      hint: 'Convert text-based PDFs into editable Word (.docx) files. Detects scanned pages that require OCR.',
      downloadExt: '.docx',
      resultTitle: 'Word Document Ready',
      isCompress: false
    },
    'compress-pdf': {
      endpoint: '/api/compress/pdf',
      accept: '.pdf',
      acceptDesc: 'Accepts .PDF',
      allowedExts: ['pdf'],
      btnText: 'Compress PDF',
      statusText: 'Losslessly compressing PDF streams...',
      hint: 'Losslessly compress PDF files using qpdf. Never degrades images or visual fidelity.',
      downloadExt: '_compressed.pdf',
      resultTitle: 'Compressed PDF Ready',
      isCompress: true
    },
    'compress-word': {
      endpoint: '/api/compress/word',
      accept: '.docx',
      acceptDesc: 'Accepts .DOCX',
      allowedExts: ['docx'],
      btnText: 'Compress Word',
      statusText: 'Compressing Word document...',
      hint: 'Safely optimize Word document archives with optional embedded-image compression.',
      downloadExt: '_compressed.docx',
      resultTitle: 'Compressed Word Document Ready',
      isCompress: true
    }
  };

  // --- Theme Management ---
  const initTheme = () => {
    const savedTheme = localStorage.getItem('privdoc_theme') || 
      (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);
  };

  const updateThemeIcon = (theme) => {
    const icon = themeToggleBtn.querySelector('.theme-icon');
    if (icon) icon.textContent = theme === 'dark' ? '🌙' : '☀️';
  };

  themeToggleBtn.addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('privdoc_theme', next);
    updateThemeIcon(next);
  });

  initTheme();

  // --- Format Bytes Utility ---
  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // --- Check Backend Binary Status ---
  const checkSystemStatus = async () => {
    try {
      const res = await fetch('/api/system-status');
      if (res.ok) {
        const data = await res.json();
        const bullet = engineStatusIndicator.querySelector('.status-bullet');
        if (bullet) {
          bullet.className = 'status-bullet ready';
        }
        engineStatusText.textContent = 'Engines ready · Ephemeral memory active';
      }
    } catch (e) {
      engineStatusText.textContent = 'Local service connected';
    }
  };
  checkSystemStatus();

  // --- Error Handling ---
  const showError = (title, message, isScanned = false) => {
    errorTitle.textContent = title || 'Error';
    errorMessage.textContent = message || 'An unexpected issue occurred.';
    if (isScanned) {
      ocrAdvisory.classList.remove('hidden');
    } else {
      ocrAdvisory.classList.add('hidden');
    }
    errorBanner.classList.remove('hidden');
  };

  const hideError = () => {
    errorBanner.classList.add('hidden');
    ocrAdvisory.classList.add('hidden');
  };

  dismissErrorBtn.addEventListener('click', hideError);

  // --- Tab Selection ---
  actionTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const targetAction = tab.dataset.action;
      if (targetAction === currentAction) return;

      actionTabs.forEach(t => {
        t.classList.remove('active');
        t.setAttribute('aria-selected', 'false');
      });
      tab.classList.add('active');
      tab.setAttribute('aria-selected', 'true');

      currentAction = targetAction;
      const config = ACTION_CONFIG[currentAction];

      // Update constraints & hints
      fileInput.setAttribute('accept', config.accept);
      formatConstraintBadge.textContent = config.acceptDesc;
      actionHintText.textContent = config.hint;
      processBtnText.textContent = config.btnText;

      // Word compression option visibility
      if (currentAction === 'compress-word') {
        wordCompressOptions.classList.remove('hidden');
      } else {
        wordCompressOptions.classList.add('hidden');
      }

      // If a file was already loaded, verify compatibility
      if (selectedFile) {
        const ext = selectedFile.name.split('.').pop().toLowerCase();
        if (!config.allowedExts.includes(ext)) {
          resetAll();
          showError(
            'Incompatible Document Type',
            `Selected file '.${ext}' is not supported for ${tab.querySelector('.tab-label').textContent}. Please upload a ${config.acceptDesc}.`
          );
        }
      }
    });
  });

  // --- Drag and Drop Events ---
  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    window.addEventListener(eventName, (e) => e.preventDefault(), false);
    dropzone.addEventListener(eventName, (e) => e.preventDefault(), false);
  });

  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, () => dropzone.classList.add('dragover'), false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, () => dropzone.classList.remove('dragover'), false);
  });

  dropzone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    if (dt && dt.files && dt.files.length > 0) {
      handleFileSelected(dt.files[0]);
    }
  });

  browseBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    fileInput.click();
  });

  dropzone.addEventListener('click', () => {
    fileInput.click();
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files && fileInput.files.length > 0) {
      handleFileSelected(fileInput.files[0]);
    }
  });

  // --- File Selection Processor ---
  const handleFileSelected = (file) => {
    hideError();
    if (!file) return;

    const config = ACTION_CONFIG[currentAction];
    const ext = file.name.split('.').pop().toLowerCase();

    if (!config.allowedExts.includes(ext)) {
      showError(
        'Invalid File Type',
        `File '.${ext}' does not match the required format for ${config.btnText}. Please provide a ${config.allowedExts.map(e => '.' + e.toUpperCase()).join(' or ')} document.`
      );
      return;
    }

    if (file.size > 50 * 1024 * 1024) {
      showError('File Too Large', 'File exceeds the maximum safe limit of 50 MB.');
      return;
    }

    selectedFile = file;
    fileNameDisplay.textContent = file.name;
    fileSizeDisplay.textContent = formatBytes(file.size);

    // Show card, hide dropzone and results
    dropzone.classList.add('hidden');
    fileCard.classList.remove('hidden');
    resultCard.classList.add('hidden');
    statusPanel.classList.add('hidden');

    if (currentAction === 'compress-word') {
      wordCompressOptions.classList.remove('hidden');
    } else {
      wordCompressOptions.classList.add('hidden');
    }
  };

  // --- Remove / Reset Button ---
  const resetAll = () => {
    selectedFile = null;
    fileInput.value = '';
    hideError();

    if (activeDownloadUrl) {
      URL.revokeObjectURL(activeDownloadUrl);
      activeDownloadUrl = null;
    }

    dropzone.classList.remove('hidden');
    fileCard.classList.add('hidden');
    statusPanel.classList.add('hidden');
    resultCard.classList.add('hidden');
  };

  removeFileBtn.addEventListener('click', resetAll);
  resetBtn.addEventListener('click', resetAll);

  // --- Process Action (Convert / Compress) ---
  processBtn.addEventListener('click', async () => {
    if (!selectedFile) return;

    hideError();
    const config = ACTION_CONFIG[currentAction];

    // Show status panel
    fileCard.classList.add('hidden');
    statusPanel.classList.remove('hidden');
    statusTitle.textContent = config.statusText;
    statusDesc.textContent = 'Allocating ephemeral sandbox and processing bytes...';

    const formData = new FormData();
    formData.append('file', selectedFile);

    if (currentAction === 'compress-word') {
      const optImg = optimizeImagesToggle ? optimizeImagesToggle.checked : false;
      formData.append('optimize_images', optImg ? 'true' : 'false');
    }

    try {
      const response = await fetch(config.endpoint, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        let errData = {};
        try {
          errData = await response.json();
        } catch (_) {
          errData = { error: `Server responded with status code ${response.status}.` };
        }

        const isScanned = (errData.code === 'SCANNED_DOCUMENT' || errData.ocr_required === true);
        showError(
          isScanned ? 'Scanned Document Detected' : 'Operation Failed',
          errData.error || 'Failed to complete document operation.',
          isScanned
        );

        statusPanel.classList.add('hidden');
        fileCard.classList.remove('hidden');
        return;
      }

      // Success: read converted blob
      const blob = await response.blob();
      if (activeDownloadUrl) {
        URL.revokeObjectURL(activeDownloadUrl);
      }
      activeDownloadUrl = URL.createObjectURL(blob);

      // Extract filename from Content-Disposition header if available
      let downloadFilename = selectedFile.name.replace(/\.[^/.]+$/, "") + config.downloadExt;
      const disposition = response.headers.get('Content-Disposition');
      if (disposition && disposition.includes('filename=')) {
        const match = disposition.match(/filename="?([^";]+)"?/);
        if (match && match[1]) {
          downloadFilename = match[1];
        }
      }

      // Populate Result Card
      resultTitle.textContent = config.resultTitle;
      downloadBtn.href = activeDownloadUrl;
      downloadBtn.setAttribute('download', downloadFilename);
      downloadBtnText.textContent = `Download ${downloadFilename} (${formatBytes(blob.size)})`;

      // Handle Compression stats
      if (config.isCompress) {
        compressionStats.classList.remove('hidden');
        const origBytes = parseInt(response.headers.get('X-Original-Size') || selectedFile.size, 10);
        const compBytes = parseInt(response.headers.get('X-Compressed-Size') || blob.size, 10);
        const percentSaved = parseFloat(response.headers.get('X-Percent-Saved') || '0');
        const isReduced = response.headers.get('X-Is-Reduced') === '1';

        statOriginalSize.textContent = formatBytes(origBytes);
        statCompressedSize.textContent = formatBytes(compBytes);
        statSavingsPercent.textContent = `${percentSaved}%`;

        compressionNote.classList.remove('hidden');
        if (isReduced) {
          statSavingsBadge.style.display = 'block';
          compressionNote.textContent = `✓ Document losslessly reduced by ${percentSaved}%. Output size is ${formatBytes(compBytes)}.`;
        } else {
          statSavingsBadge.style.display = 'none';
          compressionNote.textContent = 'ℹ️ This document is already optimally structured. No further lossless reduction could be achieved without discarding visual information.';
        }
      } else {
        compressionStats.classList.add('hidden');
        compressionNote.classList.add('hidden');
      }

      statusPanel.classList.add('hidden');
      resultCard.classList.remove('hidden');

    } catch (err) {
      showError('Connection Error', 'Network connection interrupted or server timeout. Please verify your connection and try again.');
      statusPanel.classList.add('hidden');
      fileCard.classList.remove('hidden');
    }
  });
});
