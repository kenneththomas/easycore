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
    const customPrompt = document.getElementById('custom-prompt');
    const generateButton = document.getElementById('generate-comment');
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

    generateButton.addEventListener('click', async () => {
        const prompt = aiStyle.value === 'custom' ? customPrompt.value.trim() : promptMap[aiStyle.value];
        if (!prompt) {
            commentStatus.textContent = 'Enter a custom prompt first.';
            return;
        }
        generateButton.disabled = true;
        generateButton.textContent = 'Generating...';
        try {
            const response = await fetch(config.generateCommentUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt })
            });
            const data = await response.json();
            if (!response.ok || !data.success) throw new Error(data.error || 'Generation failed');
            contentInput.value = data.comment;
            contentInput.focus();
            commentStatus.textContent = 'Draft generated.';
        } catch (error) {
            commentStatus.textContent = error.message;
        } finally {
            generateButton.disabled = false;
            generateButton.textContent = 'Generate';
        }
    });
})();
