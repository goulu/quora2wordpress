document.addEventListener('DOMContentLoaded', () => {
    // UI Elements
    const stepUpload = document.getElementById('quora-step-upload');
    const stepOptions = document.getElementById('quora-step-options');
    const stepProgress = document.getElementById('quora-step-progress');
    const stepResults = document.getElementById('quora-step-results');

    const dropzone = document.getElementById('quora-dropzone');
    const browseBtn = document.getElementById('quora-browse-btn');
    const fileInput = document.getElementById('quora-file-input');
    const fileListContainer = document.getElementById('quora-file-list-container');
    const fileList = document.getElementById('quora-file-list');

    const optionsForm = document.getElementById('quora-options-form');
    const backToUploadBtn = document.getElementById('quora-back-to-upload');
    const logConsole = document.getElementById('quora-log-console');
    const progressBar = document.getElementById('quora-progress-bar');
    const resultsList = document.getElementById('quora-results-list');
    const restartBtn = document.getElementById('quora-restart-btn');

    let uploadedFiles = []; // Array of { filename, path, size }

    // Helper: Step Navigation
    function showStep(targetStep) {
        [stepUpload, stepOptions, stepProgress, stepResults].forEach(step => {
            step.classList.remove('active');
        });
        targetStep.classList.add('active');
    }

    // Drag and Drop Events
    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.remove('dragover');
        });
    });

    dropzone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFilesSelected(files);
    });

    browseBtn.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', (e) => {
        handleFilesSelected(e.target.files);
    });

    // Handle Uploading Selected ZIP Files
    async function handleFilesSelected(files) {
        const zipFiles = Array.from(files).filter(f => f.name.toLowerCase().endsWith('.zip'));
        if (zipFiles.length === 0) {
            alert('Veuillez sélectionner au moins un fichier .zip d\'exportation Quora.');
            return;
        }

        const formData = new FormData();
        zipFiles.forEach(file => {
            formData.append('files', file);
        });

        try {
            dropzone.querySelector('h3').textContent = 'Téléversement en cours...';
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();
            dropzone.querySelector('h3').textContent = 'Glissez & déposez vos fichiers d\'exportation ici';

            if (result.success && result.files) {
                result.files.forEach(f => {
                    if (!uploadedFiles.some(existing => existing.filename === f.filename)) {
                        uploadedFiles.push(f);
                    }
                });
                renderFileList();
                // Move to Options screen automatically once files are uploaded
                showStep(stepOptions);
            } else {
                alert('Erreur lors du téléversement: ' + (result.error || 'Erreur inconnue'));
            }
        } catch (err) {
            dropzone.querySelector('h3').textContent = 'Glissez & déposez vos fichiers d\'exportation ici';
            alert('Erreur réseau ou serveur: ' + err.message);
        }
    }

    function renderFileList() {
        if (uploadedFiles.length === 0) {
            fileListContainer.style.display = 'none';
            fileList.innerHTML = '';
            return;
        }

        fileListContainer.style.display = 'block';
        fileList.innerHTML = '';

        uploadedFiles.forEach((file, index) => {
            const li = document.createElement('li');
            li.className = 'quora-file-item';
            li.innerHTML = `
                <div>
                    <span class="file-name">${file.filename}</span>
                    <span class="file-size">(${file.size})</span>
                </div>
                <button type="button" class="remove-file-btn" data-index="${index}">
                    <i class="fa-solid fa-trash-can"></i>
                </button>
            `;
            fileList.appendChild(li);
        });

        document.querySelectorAll('.remove-file-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const idx = parseInt(e.currentTarget.getAttribute('data-index'), 10);
                uploadedFiles.splice(idx, 1);
                renderFileList();
                if (uploadedFiles.length === 0) {
                    showStep(stepUpload);
                }
            });
        });
    }

    backToUploadBtn.addEventListener('click', () => {
        showStep(stepUpload);
    });

    const cancelConvertBtn = document.getElementById('quora-cancel-convert-btn');
    let currentSessionId = null;
    let activeStreamReader = null;

    cancelConvertBtn.addEventListener('click', async () => {
        if (!currentSessionId) return;
        
        cancelConvertBtn.disabled = true;
        cancelConvertBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Arrêt en cours...';
        logConsole.textContent += '\n[Action Utilisateur] Demande d\'arrêt de la conversion...\n';

        try {
            await fetch('/api/cancel', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: currentSessionId })
            });
            if (activeStreamReader) {
                try { await activeStreamReader.cancel(); } catch(e) {}
            }
        } catch (err) {
            console.error('Erreur lors de l\'annulation:', err);
        } finally {
            cancelConvertBtn.disabled = false;
            cancelConvertBtn.innerHTML = '<i class="fa-solid fa-hand"></i> Arrêter la conversion';
        }
    });

    const linkPositionSelect = document.getElementById('quora-link-position');
    const linkTemplateGroup = document.getElementById('quora-link-template-group');

    if (linkPositionSelect && linkTemplateGroup) {
        linkPositionSelect.addEventListener('change', (e) => {
            const val = e.target.value;
            linkTemplateGroup.style.display = (val === 'top' || val === 'bottom') ? 'block' : 'none';
        });
    }

    const usernameInput = document.getElementById('quora-username');
    const startConvertBtn = document.getElementById('quora-start-convert-btn');

    function validateUsernameInput() {
        if (!usernameInput || !startConvertBtn) return;
        const val = usernameInput.value.trim();
        if (!val) {
            startConvertBtn.disabled = true;
            startConvertBtn.style.opacity = '0.5';
            startConvertBtn.style.cursor = 'not-allowed';
            startConvertBtn.title = 'L\'identifiant Quora (slug) est obligatoire pour démarrer la conversion.';
        } else {
            startConvertBtn.disabled = false;
            startConvertBtn.style.opacity = '1';
            startConvertBtn.style.cursor = 'pointer';
            startConvertBtn.title = '';
        }
    }

    if (usernameInput) {
        ['input', 'change', 'keyup'].forEach(evt => {
            usernameInput.addEventListener(evt, validateUsernameInput);
        });
    }

    // Load saved configuration preferences automatically
    async function loadSavedConfig() {
        try {
            const response = await fetch('/api/config');
            if (!response.ok) return;
            const cfg = await response.json();

            if (cfg.author !== undefined) document.getElementById('quora-author').value = cfg.author;
            if (cfg.author_email !== undefined) document.getElementById('quora-author-email').value = cfg.author_email;
            if (cfg.quora_username !== undefined) document.getElementById('quora-username').value = cfg.quora_username;
            if (cfg.image_base_url !== undefined) document.getElementById('quora-image-base-url').value = cfg.image_base_url;

            if (cfg.link_position !== undefined && linkPositionSelect && linkTemplateGroup) {
                linkPositionSelect.value = cfg.link_position;
                linkTemplateGroup.style.display = (cfg.link_position === 'top' || cfg.link_position === 'bottom') ? 'block' : 'none';
            }
            if (cfg.link_template !== undefined) document.getElementById('quora-link-template').value = cfg.link_template;

            if (cfg.include_drafts !== undefined) document.getElementById('quora-include-drafts').checked = cfg.include_drafts;
            if (cfg.include_space_posts !== undefined) document.getElementById('quora-include-space-posts').checked = cfg.include_space_posts;
            if (cfg.use_cdn_images !== undefined) document.getElementById('quora-use-cdn-images').checked = cfg.use_cdn_images;
            if (cfg.scrape_topics !== undefined) document.getElementById('quora-scrape-topics').checked = cfg.scrape_topics;
            if (cfg.scrape_comments !== undefined) document.getElementById('quora-scrape-comments').checked = cfg.scrape_comments;
            if (cfg.check_online !== undefined) document.getElementById('quora-check-online').checked = cfg.check_online;
            if (cfg.test_mode !== undefined) document.getElementById('quora-test-mode').checked = cfg.test_mode;

            validateUsernameInput();
        } catch (err) {
            console.error('Failed to load saved config:', err);
            validateUsernameInput();
        }
    }

    loadSavedConfig();
    validateUsernameInput();

    // Form Submission: Execute Conversion Stream
    optionsForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        if (uploadedFiles.length === 0) {
            alert('Aucun fichier sélectionné.');
            showStep(stepUpload);
            return;
        }

        const usernameVal = (document.getElementById('quora-username').value || '').trim();
        if (!usernameVal) {
            alert('L\'identifiant Quora (slug) est obligatoire.');
            document.getElementById('quora-username').focus();
            return;
        }

        currentSessionId = 'session_' + Date.now();
        const formData = new FormData(optionsForm);
        const requestData = {
            session_id: currentSessionId,
            files: uploadedFiles.map(f => f.filename),
            author: formData.get('author') || '',
            author_email: formData.get('author_email') || '',
            quora_username: formData.get('quora_username') || '',
            image_base_url: formData.get('image_base_url') || '/wp-content/uploads/quora',
            link_position: formData.get('link_position') || 'none',
            link_template: formData.get('link_template') || '<a href="$link$" target="_blank">voir sur Quora</a>',
            include_drafts: formData.get('include_drafts') === 'on',
            include_space_posts: formData.get('include_space_posts') === 'on',
            use_cdn_images: formData.get('use_cdn_images') === 'on',
            scrape_topics: formData.get('scrape_topics') === 'on',
            scrape_comments: formData.get('scrape_comments') === 'on',
            check_online: formData.get('check_online') === 'on',
            test_mode: formData.get('test_mode') === 'on'
        };

        showStep(stepProgress);
        logConsole.textContent = '--- Initialisation de la conversion ---\n';
        progressBar.style.width = '10%';

        try {
            const response = await fetch('/api/convert', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestData)
            });

            const reader = response.body.getReader();
            activeStreamReader = reader;
            const decoder = new TextDecoder('utf-8');
            let buffer = '';

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n\n');
                buffer = lines.pop(); // keep last incomplete chunk

                for (const chunk of lines) {
                    if (chunk.startsWith('data: ')) {
                        try {
                            const jsonStr = chunk.replace(/^data:\s*/, '');
                            const eventData = JSON.parse(jsonStr);

                            if (eventData.type === 'log') {
                                logConsole.textContent += eventData.message + '\n';
                                logConsole.scrollTop = logConsole.scrollHeight;
                                progressBar.style.width = '50%';
                            } else if (eventData.type === 'done') {
                                progressBar.style.width = '100%';
                                renderResults(eventData.results, eventData.cancelled);
                                setTimeout(() => {
                                    showStep(stepResults);
                                }, 1200);
                            }
                        } catch (err) {
                            console.error('Failed to parse SSE payload:', err, chunk);
                        }
                    }
                }
            }
        } catch (err) {
            logConsole.textContent += `\nErreur ou arrêt de la conversion: ${err.message}\n`;
        } finally {
            activeStreamReader = null;
        }
    });

    function renderResults(results, isCancelled) {
        const resultsTitle = stepResults.querySelector('.step-title');
        const resultsIntro = stepResults.querySelector('.step-intro');

        if (isCancelled) {
            resultsTitle.innerHTML = '<i class="fa-solid fa-triangle-exclamation" style="color: #f9e2af;"></i> Conversion interrompue';
            resultsIntro.textContent = 'La conversion a été interrompue. Le fichier WXR partiel contenant tous les articles convertis jusqu\'à l\'arrêt est disponible au téléchargement :';
        } else {
            resultsTitle.innerHTML = '<i class="fa-solid fa-circle-check text-success"></i> Conversion terminée !';
            resultsIntro.textContent = 'Vos fichiers WXR au format WordPress ont été générés avec succès :';
        }

        resultsList.innerHTML = '';
        if (!results || results.length === 0) {
            resultsList.innerHTML = '<p class="text-muted">Aucun fichier WXR n\'a pu être sauvegardé. Veuillez vérifier les logs ci-dessus.</p>';
            return;
        }

        results.forEach(res => {
            const card = document.createElement('div');
            card.className = 'result-card';
            const badge = res.partial ? '<span style="background: rgba(249, 226, 175, 0.2); color: #f9e2af; padding: 2px 8px; border-radius: 4px; font-size: 11px; margin-left: 8px;">Partiel</span>' : '';
            card.innerHTML = `
                <div class="result-info">
                    <i class="fa-solid fa-file-code result-icon"></i>
                    <div class="result-details">
                        <h5>${res.xml_file} ${badge}</h5>
                        <p>Issu de <strong>${res.zip_file}</strong> • Taille: ${res.size}</p>
                    </div>
                </div>
                <a href="${res.download_url}" class="btn-download" download>
                    <i class="fa-solid fa-download"></i> Télécharger le fichier WXR (.xml)
                </a>
            `;
            resultsList.appendChild(card);
        });
    }

    restartBtn.addEventListener('click', () => {
        uploadedFiles = [];
        renderFileList();
        showStep(stepUpload);
    });
});
