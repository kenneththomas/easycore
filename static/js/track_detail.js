(() => {
    const config = window.trackDetailConfig;
    const playButton = document.getElementById('play-pause');
    const playIcon = document.getElementById('play-icon');
    const currentTime = document.getElementById('current-time');
    const duration = document.getElementById('duration');
    const likeCount = document.getElementById('like-count');
    const commentForm = document.getElementById('comment-form');
    const commentList = document.getElementById('comment-list');
    const commentStatus = document.getElementById('comment-status');
    const commentCount = document.getElementById('comment-count');

    const formatTime = seconds => {
        if (!Number.isFinite(seconds)) return '0:00';
        const minutes = Math.floor(seconds / 60);
        const remaining = Math.floor(seconds % 60).toString().padStart(2, '0');
        return `${minutes}:${remaining}`;
    };

    const previewStartInput = document.getElementById('preview-start');
    const previewEndInput = document.getElementById('preview-end');
    const previewRange = document.getElementById('preview-range');
    const previewSelection = document.getElementById('preview-selection');
    const previewDuration = document.getElementById('preview-editor-duration');
    const previewEditorPlay = document.getElementById('preview-editor-play');
    const previewEditorProgress = document.getElementById('preview-editor-progress');
    const previewEditorCurrent = document.getElementById('preview-editor-current');
    const previewEditorEnd = document.getElementById('preview-editor-end');
    const previewEditorAudio = new Audio(config.streamUrl);
    const fadeInInput = document.querySelector('[name="preview_fade_in"]');
    const fadeOutInput = document.querySelector('[name="preview_fade_out"]');
    const fadeInSecondsInput = document.getElementById('preview-fade-in-seconds');
    const fadeOutSecondsInput = document.getElementById('preview-fade-out-seconds');
    const previewDefaultInput = document.querySelector('[name="preview_default"]');
    let audioDuration = 0;
    let previewDrag = null;

    const getPreviewStart = () => Math.max(0, Number(previewStartInput.value) || 0);
    const getPreviewEnd = () => {
        const fallbackEnd = audioDuration ? Math.min(audioDuration, getPreviewStart() + 30) : getPreviewStart() + 30;
        return Math.max(getPreviewStart() + .1, Number(previewEndInput.value) || fallbackEnd);
    };
    const clampPreview = (start, end) => {
        const max = audioDuration || Math.max(end, 30);
        const safeStart = Math.min(Math.max(0, start), Math.max(0, max - .1));
        const safeEnd = Math.min(Math.max(safeStart + .1, end), max);
        return [Number(safeStart.toFixed(1)), Number(safeEnd.toFixed(1))];
    };
    const setPreviewValues = (start, end) => {
        const [safeStart, safeEnd] = clampPreview(start, end);
        previewStartInput.value = safeStart.toFixed(1);
        previewEndInput.value = safeEnd.toFixed(1);
        renderPreviewSelection();
        syncPreviewDataAttributes();
        renderPreviewEditorPlayer();
    };
    const refreshPreviewEditorFromInputs = () => {
        renderPreviewSelection();
        syncPreviewDataAttributes();
        renderPreviewEditorPlayer();
    };
    const syncPreviewDataAttributes = () => {
        const start = previewStartInput.value;
        const end = previewEndInput.value;
        const fadeIn = String(Boolean(fadeInInput?.checked));
        const fadeOut = String(Boolean(fadeOutInput?.checked));
        const previewDefault = String(Boolean(previewDefaultInput?.checked));
        const fadeInSeconds = String(getFadeSeconds('in'));
        const fadeOutSeconds = String(getFadeSeconds('out'));
        document.querySelectorAll('[data-track-id]').forEach(trigger => {
            if (Number(trigger.dataset.trackId) !== Number(config.trackId)) return;
            trigger.dataset.previewStart = start;
            trigger.dataset.previewEnd = end;
            trigger.dataset.previewFadeIn = fadeIn;
            trigger.dataset.previewFadeOut = fadeOut;
            trigger.dataset.previewDefault = previewDefault;
            trigger.dataset.previewFadeInSeconds = fadeInSeconds;
            trigger.dataset.previewFadeOutSeconds = fadeOutSeconds;
        });
    };
    const renderPreviewSelection = () => {
        if (!previewRange || !previewSelection) return;
        const max = audioDuration || Math.max(getPreviewEnd(), 30);
        const startPercent = (getPreviewStart() / max) * 100;
        const endPercent = (getPreviewEnd() / max) * 100;
        previewSelection.style.left = `${Math.min(99, Math.max(0, startPercent))}%`;
        previewSelection.style.width = `${Math.max(1, Math.min(100, endPercent) - startPercent)}%`;
        previewSelection.setAttribute('aria-valuemin', '0');
        previewSelection.setAttribute('aria-valuemax', String(Math.round(max)));
        previewSelection.setAttribute('aria-valuenow', String(getPreviewStart()));
        previewSelection.title = `${formatTime(getPreviewStart())} - ${formatTime(getPreviewEnd())}`;
    };

    function getPreviewLength() {
        return Math.max(.1, getPreviewEnd() - getPreviewStart());
    }

    function getFadeSeconds(kind) {
        const input = kind === 'in' ? fadeInSecondsInput : fadeOutSecondsInput;
        const value = Number(input?.value);
        return Number.isFinite(value) ? Math.min(30, Math.max(0, value)) : 2;
    }

    function applyPreviewEditorFade() {
        const start = getPreviewStart();
        const end = getPreviewEnd();
        let multiplier = 1;
        const fadeInSeconds = getFadeSeconds('in');
        const fadeOutSeconds = getFadeSeconds('out');
        if (fadeInInput?.checked && fadeInSeconds > 0) {
            multiplier = Math.min(multiplier, Math.max(0, (previewEditorAudio.currentTime - start) / fadeInSeconds));
        }
        if (fadeOutInput?.checked && fadeOutSeconds > 0) {
            multiplier = Math.min(multiplier, Math.max(0, (end - previewEditorAudio.currentTime) / fadeOutSeconds));
        }
        previewEditorAudio.volume = Math.min(1, Math.max(0, multiplier));
    }

    function renderPreviewEditorPlayer() {
        const start = getPreviewStart();
        const end = getPreviewEnd();
        const length = getPreviewLength();
        const current = Math.min(Math.max(previewEditorAudio.currentTime || start, start), end);
        const relative = Math.min(length, Math.max(0, current - start));
        previewEditorCurrent.textContent = formatTime(relative);
        previewEditorEnd.textContent = formatTime(length);
        previewEditorProgress.value = Math.round((relative / length) * 1000);
        previewEditorPlay.textContent = previewEditorAudio.paused ? 'Play this preview' : 'Pause preview';
    }

    async function playPreviewEditor() {
        syncPreviewDataAttributes();
        const playerState = window.easycorePlayer?.getState?.();
        if (playerState?.playing) window.easycorePlayer.toggle();

        const start = getPreviewStart();
        const end = getPreviewEnd();
        if (previewEditorAudio.paused || previewEditorAudio.currentTime < start || previewEditorAudio.currentTime >= end) {
            previewEditorAudio.currentTime = start;
            applyPreviewEditorFade();
            try {
                await previewEditorAudio.play();
            } catch (_) {}
        } else {
            previewEditorAudio.pause();
        }
        renderPreviewEditorPlayer();
    }

    const initializePreviewEditor = () => {
        previewEditorAudio.preload = 'metadata';
        previewEditorAudio.addEventListener('loadedmetadata', () => {
            audioDuration = Number.isFinite(previewEditorAudio.duration) ? previewEditorAudio.duration : 0;
            previewDuration.textContent = audioDuration ? `Duration ${formatTime(audioDuration)}` : 'Duration unavailable';
            if (!previewStartInput.value && !previewEndInput.value) {
                setPreviewValues(0, Math.min(audioDuration || 30, 30));
            } else {
                setPreviewValues(getPreviewStart(), getPreviewEnd());
            }
        });
        previewEditorAudio.addEventListener('error', () => {
            previewDuration.textContent = 'Duration unavailable';
            if (!previewEndInput.value) setPreviewValues(0, 30);
        });
        renderPreviewEditorPlayer();
    };

    const positionToSeconds = clientX => {
        const rect = previewRange.getBoundingClientRect();
        const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
        return ratio * (audioDuration || Math.max(getPreviewEnd(), 30));
    };

    previewStartInput.addEventListener('input', refreshPreviewEditorFromInputs);
    previewEndInput.addEventListener('input', refreshPreviewEditorFromInputs);
    previewStartInput.addEventListener('change', () => setPreviewValues(getPreviewStart(), getPreviewEnd()));
    previewEndInput.addEventListener('change', () => setPreviewValues(getPreviewStart(), getPreviewEnd()));
    previewStartInput.addEventListener('blur', () => setPreviewValues(getPreviewStart(), getPreviewEnd()));
    previewEndInput.addEventListener('blur', () => setPreviewValues(getPreviewStart(), getPreviewEnd()));
    document.querySelectorAll('[name="preview_fade_in"], [name="preview_fade_out"], [name="preview_fade_in_seconds"], [name="preview_fade_out_seconds"], [name="preview_default"]').forEach(input => {
        input.addEventListener('change', () => {
            syncPreviewDataAttributes();
            applyPreviewEditorFade();
        });
        input.addEventListener('input', () => {
            syncPreviewDataAttributes();
            applyPreviewEditorFade();
        });
    });
    previewEditorPlay.addEventListener('click', playPreviewEditor);
    previewEditorProgress.addEventListener('input', () => {
        previewEditorAudio.currentTime = getPreviewStart() + (Number(previewEditorProgress.value) / 1000) * getPreviewLength();
        applyPreviewEditorFade();
        renderPreviewEditorPlayer();
    });
    previewEditorAudio.addEventListener('play', renderPreviewEditorPlayer);
    previewEditorAudio.addEventListener('pause', renderPreviewEditorPlayer);
    previewEditorAudio.addEventListener('timeupdate', () => {
        if (previewEditorAudio.currentTime >= getPreviewEnd() - .05) {
            previewEditorAudio.pause();
            previewEditorAudio.currentTime = getPreviewEnd();
        }
        applyPreviewEditorFade();
        renderPreviewEditorPlayer();
    });

    const getPreviewDragMode = event => {
        const handle = event.target.closest('[data-handle]')?.dataset.handle;
        if (handle) return handle;
        if (!event.target.closest('#preview-selection')) return 'create';

        const selectionRect = previewSelection.getBoundingClientRect();
        const edgeWidth = 16;
        if (Math.abs(event.clientX - selectionRect.left) <= edgeWidth) return 'start';
        if (Math.abs(event.clientX - selectionRect.right) <= edgeWidth) return 'end';
        return 'move';
    };

    previewRange.addEventListener('pointerdown', event => {
        event.preventDefault();
        const start = getPreviewStart();
        const end = getPreviewEnd();
        previewDrag = {
            mode: getPreviewDragMode(event),
            start,
            end,
            offset: positionToSeconds(event.clientX)
        };
        previewSelection.classList.add('is-dragging');
        previewRange.setPointerCapture(event.pointerId);
        if (previewDrag.mode === 'create') {
            const point = positionToSeconds(event.clientX);
            setPreviewValues(point, point + Math.min(15, audioDuration || 15));
        }
    });

    previewRange.addEventListener('pointermove', event => {
        if (!previewDrag) return;
        const point = positionToSeconds(event.clientX);
        const length = previewDrag.end - previewDrag.start;
        if (previewDrag.mode === 'start') setPreviewValues(point, getPreviewEnd());
        if (previewDrag.mode === 'end') setPreviewValues(getPreviewStart(), point);
        if (previewDrag.mode === 'move') {
            const delta = point - previewDrag.offset;
            setPreviewValues(previewDrag.start + delta, previewDrag.start + delta + length);
        }
        if (previewDrag.mode === 'create') {
            setPreviewValues(Math.min(previewDrag.offset, point), Math.max(previewDrag.offset, point));
        }
    });

    const endPreviewDrag = event => {
        if (!previewDrag) return;
        previewDrag = null;
        previewSelection.classList.remove('is-dragging');
        if (previewRange.hasPointerCapture(event.pointerId)) previewRange.releasePointerCapture(event.pointerId);
    };
    previewRange.addEventListener('pointerup', endPreviewDrag);
    previewRange.addEventListener('pointercancel', endPreviewDrag);
    initializePreviewEditor();

    const syncPlayButton = playing => {
        playIcon.textContent = playing ? 'Ⅱ' : '▶';
        playButton.setAttribute('aria-label', playing ? 'Pause track' : 'Play track');
    };

    const pageProgress = document.getElementById('track-page-progress');
    pageProgress.addEventListener('input', () => {
        const playerState = window.easycorePlayer.getState();
        if (playerState.track?.id === config.trackId && playerState.duration) {
            window.easycorePlayer.seek((Number(pageProgress.value) / 1000) * playerState.duration);
        }
    });

    window.addEventListener('easycoreplayerchange', event => {
        const isCurrentTrack = Number(event.detail.track?.id) === Number(config.trackId);
        syncPlayButton(isCurrentTrack && event.detail.playing);
        if (!isCurrentTrack) return;
        currentTime.textContent = formatTime(event.detail.currentTime);
        duration.textContent = formatTime(event.detail.duration);
        pageProgress.value = event.detail.duration
            ? Math.round((event.detail.currentTime / event.detail.duration) * 1000)
            : 0;
    });

    document.getElementById('like-track').addEventListener('click', async () => {
        const response = await fetch(config.likeUrl, { method: 'POST' });
        const data = await response.json();
        if (data.success) likeCount.textContent = data.new_like_count;
    });

    const photoInput = document.getElementById('photo-upload');
    const photoPreview = document.getElementById('photo-preview');
    const uploadButton = document.getElementById('upload-photo');
    const editStatus = document.getElementById('edit-status');

    photoInput.addEventListener('change', () => {
        const file = photoInput.files[0];
        if (!file) {
            photoPreview.hidden = true;
            return;
        }
        photoPreview.src = URL.createObjectURL(file);
        photoPreview.hidden = false;
    });

    uploadButton.addEventListener('click', async () => {
        const file = photoInput.files[0];
        if (!file) {
            editStatus.textContent = 'Choose an image first.';
            return;
        }

        uploadButton.disabled = true;
        uploadButton.textContent = 'Uploading...';
        editStatus.textContent = 'Uploading artwork...';
        const formData = new FormData();
        formData.append('photo', file);

        try {
            const response = await fetch(config.photoUrl, { method: 'POST', body: formData });
            const data = await response.json();
            if (!response.ok || !data.success) throw new Error(data.error || 'Upload failed');

            const artwork = document.getElementById('track-artwork');
            artwork.replaceChildren();
            const image = document.createElement('img');
            image.src = data.photo_path;
            image.alt = 'Updated track artwork';
            artwork.append(image);
            document.querySelector('.track-hero-glow').style.backgroundImage = `url("${data.photo_path}")`;
            editStatus.textContent = 'Artwork updated.';
        } catch (error) {
            editStatus.textContent = error.message;
        } finally {
            uploadButton.disabled = false;
            uploadButton.textContent = 'Upload artwork';
        }
    });

    const editForm = document.getElementById('edit-track-form');
    editForm.addEventListener('submit', async event => {
        event.preventDefault();
        editStatus.textContent = 'Saving changes...';
        const response = await fetch(config.updateUrl, {
            method: 'POST',
            body: new FormData(editForm)
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            editStatus.textContent = data.error || 'Could not save changes.';
            return;
        }

        document.getElementById('track-title').textContent = data.track.title;
        document.title = `${data.track.title} - easycore`;
        const trackDate = document.getElementById('track-date');
        if (trackDate) {
            trackDate.dateTime = data.track.date || '';
            trackDate.textContent = data.track.dateDisplay || 'No date set';
        }
        document.getElementById('track-description').textContent =
            data.track.description || 'No description has been added yet.';

        const artists = document.getElementById('track-artists');
        artists.replaceChildren();
        if (data.track.artists.length) {
            data.track.artists.forEach((artist, index) => {
                const link = document.createElement('a');
                link.href = `/artist/${artist.id}`;
                link.textContent = artist.name;
                artists.append(link);
                if (index < data.track.artists.length - 1) artists.append(document.createTextNode(', '));
            });
        } else {
            artists.textContent = 'Unknown artist';
        }

        const tags = document.getElementById('track-tags');
        tags.replaceChildren();
        data.track.tags.forEach(tag => {
            const link = document.createElement('a');
            link.href = `/tag/${encodeURIComponent(tag)}`;
            link.textContent = `#${tag}`;
            tags.append(link);
        });

        editStatus.textContent = 'Changes saved.';
        syncPreviewDataAttributes();
    });

    const buildComment = comment => {
        const article = document.createElement('article');
        article.className = 'track-comment';
        article.dataset.id = comment.id;

        const avatar = document.createElement('img');
        avatar.className = 'comment-avatar';
        avatar.alt = '';
        avatar.src = comment.author_avatar ? `/static/${comment.author_avatar}` : config.defaultAvatar;

        const body = document.createElement('div');
        body.className = 'comment-body';
        const meta = document.createElement('div');
        meta.className = 'comment-meta';
        const author = document.createElement('a');
        author.href = config.artistUrlTemplate.replace('__author__', encodeURIComponent(comment.author));
        author.textContent = comment.author;
        const time = document.createElement('time');
        time.textContent = comment.timestamp;
        meta.append(author, time);

        const text = document.createElement('p');
        text.textContent = comment.content;
        const actions = document.createElement('div');
        actions.className = 'comment-actions';
        const like = document.createElement('button');
        like.type = 'button';
        like.className = 'control-button control-quiet comment-like';
        like.innerHTML = `♥ <span>${comment.likes || 0}</span>`;
        const menu = document.createElement('details');
        menu.className = 'comment-menu';
        const menuTrigger = document.createElement('summary');
        menuTrigger.className = 'control-button control-quiet';
        menuTrigger.setAttribute('aria-label', 'Comment options');
        menuTrigger.title = 'Comment options';
        menuTrigger.textContent = '•••';
        const menuPanel = document.createElement('div');
        menuPanel.className = 'comment-menu-panel';
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'comment-delete';
        remove.textContent = 'Delete comment';
        menuPanel.append(remove);
        menu.append(menuTrigger, menuPanel);
        actions.append(like, menu);
        body.append(meta, text, actions);
        article.append(avatar, body);
        return article;
    };

    commentForm.addEventListener('submit', async event => {
        event.preventDefault();
        commentStatus.textContent = 'Posting...';
        const response = await fetch(config.addCommentUrl, {
            method: 'POST',
            body: new FormData(commentForm)
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            commentStatus.textContent = data.error || 'Could not post comment.';
            return;
        }
        commentList.prepend(buildComment(data.comment));
        commentCount.textContent = Number(commentCount.textContent) + 1;
        document.querySelector('.comment-total').textContent = commentCount.textContent;
        commentForm.reset();
        commentStatus.textContent = 'Comment posted.';
    });

    commentList.addEventListener('click', async event => {
        const comment = event.target.closest('.track-comment');
        if (!comment) return;
        const id = comment.dataset.id;

        if (event.target.closest('.comment-like')) {
            const response = await fetch(config.likeCommentUrl.replace('0', id), { method: 'POST' });
            const data = await response.json();
            if (data.success) comment.querySelector('.comment-like span').textContent = data.new_like_count;
        }

        if (event.target.closest('.comment-delete')) {
            if (!confirm('Delete this comment?')) return;
            const response = await fetch(config.deleteCommentUrl.replace('0', id), { method: 'POST' });
            const data = await response.json();
            if (data.success) {
                comment.remove();
                commentCount.textContent = Math.max(0, Number(commentCount.textContent) - 1);
                document.querySelector('.comment-total').textContent = commentCount.textContent;
            }
        }
    });

    document.addEventListener('click', event => {
        document.querySelectorAll('.comment-menu[open]').forEach(menu => {
            if (!menu.contains(event.target)) menu.removeAttribute('open');
        });
    });

    document.addEventListener('toggle', event => {
        if (!event.target.matches?.('.comment-menu[open]')) return;
        document.querySelectorAll('.comment-menu[open]').forEach(menu => {
            if (menu !== event.target) menu.removeAttribute('open');
        });
    }, true);

    const aiStyle = document.getElementById('ai-style');
    const aiPersona = document.getElementById('ai-persona');
    const customPrompt = document.getElementById('custom-prompt');
    const generateButton = document.getElementById('generate-comment');
    const postAiButton = document.getElementById('post-ai-comment');
    const authorInput = commentForm.querySelector('[name="author"]');
    const contentInput = commentForm.querySelector('[name="content"]');
    const promptMap = {
        general: 'Write a natural music fan comment about this track.',
        positive: 'Write an enthusiastic but believable comment about this track.',
        critical: 'Write a thoughtful, constructive critique of this track.',
        discovery: 'Write a comment from someone excited to have just discovered this track.',
        technical: 'Comment on the production, arrangement, or performance of this track.',
        emotional: 'Write an emotionally sincere response to this track.'
    };

    aiStyle.addEventListener('change', () => {
        customPrompt.hidden = aiStyle.value !== 'custom';
    });

    async function generateAiComment({ post = false } = {}) {
        const prompt = aiStyle.value === 'custom' ? customPrompt.value.trim() : promptMap[aiStyle.value];
        if (!prompt) {
            commentStatus.textContent = 'Enter a custom prompt first.';
            return;
        }
        generateButton.disabled = true;
        postAiButton.disabled = true;
        const activeButton = post ? postAiButton : generateButton;
        const originalLabel = activeButton.textContent;
        activeButton.textContent = post ? 'Posting...' : 'Drafting...';
        try {
            const response = await fetch(config.generateCommentUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    prompt,
                    persona_id: aiPersona.value,
                    post
                })
            });
            const data = await response.json();
            if (!response.ok || !data.success) throw new Error(data.error || 'Generation failed');
            if (post && data.comment_record) {
                commentList.prepend(buildComment(data.comment_record));
                commentCount.textContent = Number(commentCount.textContent) + 1;
                document.querySelector('.comment-total').textContent = commentCount.textContent;
                commentStatus.textContent = `${data.comment_record.author} joined the conversation.`;
            } else {
                if (data.author) authorInput.value = data.author;
                contentInput.value = data.comment;
                contentInput.focus();
                commentStatus.textContent = data.author ? `Draft from ${data.author}.` : 'Draft generated.';
            }
        } catch (error) {
            commentStatus.textContent = error.message;
        } finally {
            generateButton.disabled = false;
            postAiButton.disabled = false;
            activeButton.textContent = originalLabel;
        }
    }

    generateButton.addEventListener('click', () => generateAiComment({ post: false }));
    postAiButton.addEventListener('click', () => generateAiComment({ post: true }));
})();
