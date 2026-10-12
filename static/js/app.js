/**
 * PrivDoc - Privacy-First Document Suite
 * Client-Side Controller
 */

document.addEventListener('DOMContentLoaded', () => {
  // --- State ---
  let selectedFiles = []; // Array of File objects
  let currentAction = 'office-to-pdf';
  let activeDownloadUrl = null;

  // --- DOM Elements ---
  const themeToggleBtn = document.getElementById('themeToggleBtn');
  const actionTabs = document.querySelectorAll('.tab-btn');
  const actionHintText = document.getElementById('actionHintText');
  const formatConstraintBadge = document.getElementById('formatConstraintBadge');

  const dropzone = document.getElementById('dropzone');
  const dropzonePrompt = document.getElementById('dropzonePrompt');
  const fileInput = document.getElementById('fileInput');
  const browseBtn = document.getElementById('browseBtn');

  const fileCard = document.getElementById('fileCard');
  const singleFileInfo = document.getElementById('singleFileInfo');
  const fileNameDisplay = document.getElementById('fileNameDisplay');
  const fileSizeDisplay = document.getElementById('fileSizeDisplay');

  const multiFilesBox = document.getElementById('multiFilesBox');
  const multiFilesCount = document.getElementById('multiFilesCount');
  const fileChipsContainer = document.getElementById('fileChipsContainer');

  const splitPdfOptions = document.getElementById('splitPdfOptions');
  const pageRangeInput = document.getElementById('pageRangeInput');
  const sanitizeOptions = document.getElementById('sanitizeOptions');
  const wordCompressOptions = document.getElementById('wordCompressOptions');
  const optimizeImagesToggle = document.getElementById('optimizeImagesToggle');
  const pdfCompressOptions = document.getElementById('pdfCompressOptions');
  const strongPdfToggle = document.getElementById('strongPdfToggle');

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

  const mergeStatsRow = document.getElementById('mergeStatsRow');
  const statFilesMerged = document.getElementById('statFilesMerged');
  const statTotalPages = document.getElementById('statTotalPages');

  const splitStatsRow = document.getElementById('splitStatsRow');
  const statOriginalPages = document.getElementById('statOriginalPages');
  const statExtractedPages = document.getElementById('statExtractedPages');

  const sanitizeStatsRow = document.getElementById('sanitizeStatsRow');
  const statFieldsScrubbed = document.getElementById('statFieldsScrubbed');
  const statImagesSanitized = document.getElementById('statImagesSanitized');

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
    'office-to-pdf': {
      endpoint: '/api/convert/office-to-pdf',
      accept: '.docx,.doc,.xlsx,.xls,.pptx,.ppt',
      acceptDesc: 'Word, Excel, or PowerPoint (.docx, .xlsx, .pptx)',
      allowedExts: ['docx', 'doc', 'xlsx', 'xls', 'pptx', 'ppt'],
      btnText: 'Convert to PDF',
      statusText: 'Converting Office document to PDF...',
      hint: 'Convert Word (.docx), Excel (.xlsx), or PowerPoint (.pptx) documents directly to PDF with preserved formatting.',
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
    'merge-pdf': {
      endpoint: '/api/pdf/merge',
      accept: '.pdf',
      acceptDesc: 'Accepts 2+ PDF files',
      allowedExts: ['pdf'],
      btnText: 'Merge PDFs',
      statusText: 'Merging PDF documents...',
      hint: 'Combine 2 or more PDF documents into a single ordered document in isolated ephemeral memory.',
      downloadExt: '_merged.pdf',
      resultTitle: 'Merged PDF Ready',
      isMulti: true
    },
    'split-pdf': {
      endpoint: '/api/pdf/split',
      accept: '.pdf',
      acceptDesc: 'Accepts .PDF',
      allowedExts: ['pdf'],
      btnText: 'Extract Pages',
      statusText: 'Extracting selected pages...',
      hint: 'Extract specific pages or page ranges from a PDF (e.g. 1-3, 5).',
      downloadExt: '_extracted.pdf',
      resultTitle: 'Extracted PDF Ready',
      hasPageRange: true
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
    },
    'sanitize-meta': {
      endpoint: '/api/sanitize/metadata',
      accept: '.pdf,.docx,.xlsx,.pptx',
      acceptDesc: 'Accepts PDF, DOCX, XLSX, PPTX',
      allowedExts: ['pdf', 'docx', 'xlsx', 'pptx'],
      btnText: 'Scrub Metadata',
      statusText: 'Purging tracking tags and hidden metadata...',
      hint: 'Strip hidden author names, timestamps, edit revisions, and EXIF camera GPS tags from documents and embedded images.',
      downloadExt: '_sanitized',
      resultTitle: 'Sanitized Document Ready',
      isSanitize: true
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
    if (!bytes || bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // --- Check Backend Status ---
  const checkSystemStatus = async () => {
    try {
      const res = await fetch('/api/system-status');
      if (res.ok) {
        const bullet = engineStatusIndicator.querySelector('.status-bullet');
        if (bullet) bullet.className = 'status-bullet ready';
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

  // --- Update Option Panels Visibility ---
  const updateOptionPanels = () => {
    wordCompressOptions.classList.toggle('hidden', currentAction !== 'compress-word');
    pdfCompressOptions.classList.toggle('hidden', currentAction !== 'compress-pdf');
    splitPdfOptions.classList.toggle('hidden', currentAction !== 'split-pdf');
    sanitizeOptions.classList.toggle('hidden', currentAction !== 'sanitize-meta');
  };

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
      fileInput.multiple = Boolean(config.isMulti);
      formatConstraintBadge.textContent = config.acceptDesc;
      actionHintText.textContent = config.hint;
      processBtnText.textContent = config.btnText;

      dropzonePrompt.textContent = config.isMulti 
        ? 'Drag & drop 2 or more PDF files here' 
        : 'Drag & drop your document here';

      updateOptionPanels();

      // If files were already loaded, verify compatibility
      if (selectedFiles.length > 0) {
        const invalid = selectedFiles.some(f => {
          const ext = f.name.split('.').pop().toLowerCase();
          return !config.allowedExts.includes(ext);
        });

        if (invalid || (config.isMulti && selectedFiles.length < 2)) {
          resetAll();
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
      handleFilesSelected(Array.from(dt.files));
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
      handleFilesSelected(Array.from(fileInput.files));
    }
  });

  // --- Files Selection Handler ---
  const handleFilesSelected = (files) => {
    hideError();
    if (!files || files.length === 0) return;

    const config = ACTION_CONFIG[currentAction];

    // Validate extensions
    for (const file of files) {
      const ext = file.name.split('.').pop().toLowerCase();
      if (!config.allowedExts.includes(ext)) {
        showError(
          'Invalid File Type',
          `File '${file.name}' does not match the required format for ${config.btnText}. Please provide ${config.acceptDesc}.`
        );
        return;
      }
      if (file.size > 50 * 1024 * 1024) {
        showError('File Too Large', `'${file.name}' exceeds the 50 MB limit.`);
        return;
      }
    }

    if (config.isMulti) {
      if (files.length < 2) {
        showError('Multiple Files Required', 'Please select at least 2 PDF files to merge.');
        return;
      }
      selectedFiles = files;
      renderMultiFilesList();
    } else {
      selectedFiles = [files[0]];
      renderSingleFile(files[0]);
    }

    // Toggle view
    dropzone.classList.add('hidden');
    fileCard.classList.remove('hidden');
    resultCard.classList.add('hidden');
    statusPanel.classList.add('hidden');

    updateOptionPanels();
  };

  const renderSingleFile = (file) => {
    singleFileInfo.classList.remove('hidden');
    multiFilesBox.classList.add('hidden');
    fileNameDisplay.textContent = file.name;
    fileSizeDisplay.textContent = formatBytes(file.size);
  };

  const renderMultiFilesList = () => {
    singleFileInfo.classList.add('hidden');
    multiFilesBox.classList.remove('hidden');

    const totalBytes = selectedFiles.reduce((acc, f) => acc + f.size, 0);
    multiFilesCount.textContent = `${selectedFiles.length} files (${formatBytes(totalBytes)})`;

    fileChipsContainer.innerHTML = '';
    selectedFiles.forEach((file, index) => {
      const chip = document.createElement('div');
      chip.className = 'file-chip';
      chip.innerHTML = `
        <span class="chip-name">${index + 1}. ${file.name}</span>
        <span class="chip-size">${formatBytes(file.size)}</span>
      `;
      fileChipsContainer.appendChild(chip);
    });
  };

  // --- Remove / Reset Button ---
  const resetAll = () => {
    selectedFiles = [];
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

  // --- Process Action (Convert / Merge / Split / Scrub / Compress) ---
  processBtn.addEventListener('click', async () => {
    if (!selectedFiles || selectedFiles.length === 0) return;

    hideError();
    const config = ACTION_CONFIG[currentAction];

    // Show status panel
    fileCard.classList.add('hidden');
    statusPanel.classList.remove('hidden');
    statusTitle.textContent = config.statusText;
    statusDesc.textContent = 'Allocating ephemeral sandbox and processing bytes...';

    const formData = new FormData();

    if (config.isMulti) {
      selectedFiles.forEach(f => formData.append('files', f));
    } else {
      formData.append('file', selectedFiles[0]);
    }

    // Additional options
    if (currentAction === 'compress-word') {
      formData.append('optimize_images', optimizeImagesToggle.checked ? 'true' : 'false');
    } else if (currentAction === 'compress-pdf') {
      formData.append('strong_mode', strongPdfToggle.checked ? 'true' : 'false');
    } else if (currentAction === 'split-pdf') {
      formData.append('pages', (pageRangeInput.value || '1').trim());
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
        } catch (_) {}

        statusPanel.classList.add('hidden');
        fileCard.classList.remove('hidden');

        const isScanned = errData.code === 'SCANNED_DOCUMENT';
        const title = isScanned ? 'Scanned Document Detected' : 'Processing Failed';
        const msg = errData.error || `Server responded with status ${response.status}.`;
        showError(title, msg, isScanned);
        return;
      }

      // Hide panels
      statusPanel.classList.add('hidden');
      resultCard.classList.remove('hidden');
      resultTitle.textContent = config.resultTitle;

      // Extract filename from Content-Disposition
      let downloadFilename = 'document' + config.downloadExt;
      const disposition = response.headers.get('Content-Disposition');
      if (disposition && disposition.includes('filename=')) {
        const matches = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(disposition);
        if (matches != null && matches[1]) {
          downloadFilename = matches[1].replace(/['"]/g, '');
        }
      }

      // Display dynamic metric stats
      compressionStats.classList.add('hidden');
      compressionNote.classList.add('hidden');
      mergeStatsRow.classList.add('hidden');
      splitStatsRow.classList.add('hidden');
      sanitizeStatsRow.classList.add('hidden');

      if (config.isCompress) {
        compressionStats.classList.remove('hidden');
        const orig = parseInt(response.headers.get('X-Original-Size') || '0', 10);
        const comp = parseInt(response.headers.get('X-Compressed-Size') || '0', 10);
        const saved = parseFloat(response.headers.get('X-Percent-Saved') || '0');
        const isReduced = response.headers.get('X-Is-Reduced') === '1';

        statOriginalSize.textContent = formatBytes(orig);
        statCompressedSize.textContent = formatBytes(comp);
        statSavingsPercent.textContent = `${saved.toFixed(1)}%`;

        if (isReduced) {
          statSavingsBadge.className = 'stat-badge';
          compressionNote.classList.add('hidden');
        } else {
          statSavingsBadge.className = 'stat-badge unreduced';
          compressionNote.textContent = 'Document is already optimized to maximum lossless density.';
          compressionNote.classList.remove('hidden');
        }
      } else if (currentAction === 'merge-pdf') {
        mergeStatsRow.classList.remove('hidden');
        statFilesMerged.textContent = `${response.headers.get('X-Files-Merged') || selectedFiles.length} Files`;
        statTotalPages.textContent = `${response.headers.get('X-Total-Pages') || '—'} Pages`;
      } else if (currentAction === 'split-pdf') {
        splitStatsRow.classList.remove('hidden');
        statOriginalPages.textContent = `${response.headers.get('X-Original-Pages') || '—'} Pages`;
        statExtractedPages.textContent = `${response.headers.get('X-Extracted-Pages') || '—'} Pages`;
      } else if (currentAction === 'sanitize-meta') {
        sanitizeStatsRow.classList.remove('hidden');
        statFieldsScrubbed.textContent = `${response.headers.get('X-Fields-Scrubbed') || '0'} Fields`;
        statImagesSanitized.textContent = `${response.headers.get('X-Images-Sanitized') || '0'} Images`;
      }

      // Create download blob
      const blob = await response.blob();
      if (activeDownloadUrl) URL.revokeObjectURL(activeDownloadUrl);
      activeDownloadUrl = URL.createObjectURL(blob);

      downloadBtn.href = activeDownloadUrl;
      downloadBtn.download = downloadFilename;
      downloadBtnText.textContent = `Download ${downloadFilename}`;

    } catch (err) {
      statusPanel.classList.add('hidden');
      fileCard.classList.remove('hidden');
      showError('Connection Error', 'Could not communicate with the local conversion engine.');
    }
  });
});
