(() => {
    const config = window.artistDetailConfig;
    const bioContent = document.getElementById('bio-content');
    const bioTextarea = document.getElementById('bio-textarea');
    const bioStatus = document.getElementById('bio-status');

    document.getElementById('save-bio').addEventListener('click', async () => {
        bioStatus.textContent = 'Saving...';
        const formData = new FormData();
        formData.append('bio', bioTextarea.value);
        const response = await fetch(config.bioUrl, { method: 'POST', body: formData });
        const data = await response.json();
        if (!response.ok || !data.success) {
            bioStatus.textContent = data.error || 'Could not save biography.';
            return;
        }
        bioContent.innerHTML = data.bio_html || 'No biography has been added yet.';
        bioContent.classList.toggle('is-empty', !data.bio);
        bioStatus.textContent = 'Biography saved.';
    });

    document.getElementById('cancel-bio').addEventListener('click', () => {
        document.querySelector('.artist-edit-menu').removeAttribute('open');
    });

    const commentForm = document.getElementById('artist-comment-form');
    const commentList = document.getElementById('artist-comment-list');
    const commentCount = document.getElementById('artist-comment-count');
    const commentStatus = document.getElementById('artist-comment-status');

    const buildComment = comment => {
        const article = document.createElement('article');
        article.className = 'artist-comment';
        article.dataset.id = comment.id;
        article.dataset.type = 'artist';

        const avatar = document.createElement('img');
        avatar.alt = '';
        avatar.src = comment.author_avatar ? `/static/${comment.author_avatar}` : config.defaultAvatar;

        const body = document.createElement('div');
        const meta = document.createElement('div');
        meta.className = 'artist-comment-meta';
        const author = document.createElement('a');
        author.href = comment.author_artist_id ? `/artist/${comment.author_artist_id}` : '#';
        author.textContent = comment.author;
        const time = document.createElement('time');
        time.textContent = comment.timestamp;
        meta.append(author, time);

        const text = document.createElement('p');
        text.textContent = comment.content;
        const actions = document.createElement('div');
        actions.className = 'artist-comment-actions';
        const like = document.createElement('button');
        like.className = 'artist-control artist-control-quiet like-comment';
        like.type = 'button';
        like.innerHTML = `♥ <span>${comment.likes || 0}</span>`;
        const menu = document.createElement('details');
        menu.className = 'artist-comment-menu';
        const summary = document.createElement('summary');
        summary.className = 'artist-control artist-control-quiet';
        summary.setAttribute('aria-label', 'Comment options');
        summary.textContent = '•••';
        const panel = document.createElement('div');
        const remove = document.createElement('button');
        remove.className = 'delete-comment';
        remove.type = 'button';
        remove.textContent = 'Delete comment';
        panel.append(remove);
        menu.append(summary, panel);
        actions.append(like, menu);
        body.append(meta, text, actions);
        article.append(avatar, body);
        return article;
    };

    commentForm.addEventListener('submit', async event => {
        event.preventDefault();
        commentStatus.textContent = 'Posting...';
        const response = await fetch(config.addCommentUrl, { method: 'POST', body: new FormData(commentForm) });
        const data = await response.json();
        if (!response.ok || !data.success) {
            commentStatus.textContent = data.error || 'Could not post comment.';
            return;
        }
        commentList.prepend(buildComment(data.comment));
        commentForm.reset();
        commentCount.textContent = Number(commentCount.textContent) + 1;
        commentStatus.textContent = 'Comment posted.';
    });

    document.addEventListener('click', async event => {
        const comment = event.target.closest('.artist-comment');
        if (comment) {
            const id = comment.dataset.id;
            const type = comment.dataset.type;
            if (event.target.closest('.like-comment')) {
                const template = type === 'artist' ? config.likeArtistCommentUrl : config.likeTrackCommentUrl;
                const response = await fetch(template.replace('0', id), { method: 'POST' });
                const data = await response.json();
                if (data.success) comment.querySelector('.like-comment span').textContent = data.new_like_count;
            }
            if (event.target.closest('.delete-comment')) {
                if (!confirm('Delete this comment?')) return;
                const template = type === 'artist' ? config.deleteArtistCommentUrl : config.deleteTrackCommentUrl;
                const response = await fetch(template.replace('0', id), { method: 'POST' });
                const data = await response.json();
                if (data.success) {
                    comment.remove();
                    if (type === 'artist') commentCount.textContent = Math.max(0, Number(commentCount.textContent) - 1);
                }
            }
        }

        document.querySelectorAll('.artist-comment-menu[open]').forEach(menu => {
            if (!menu.contains(event.target)) menu.removeAttribute('open');
        });
    });

    const aiStyle = document.getElementById('artist-ai-style');
    const customPrompt = document.getElementById('artist-custom-prompt');
    const generateButton = document.getElementById('generate-artist-comment');
    const contentInput = commentForm.querySelector('[name="content"]');
    const prompts = {
        general: `Write a natural music fan comment about ${config.artistName}.`,
        positive: `Write an enthusiastic but believable comment about ${config.artistName}.`,
        critical: `Write a thoughtful, constructive critique of ${config.artistName}.`,
        discovery: `Write a comment from someone excited to have just discovered ${config.artistName}.`,
        technical: `Comment on the musical or production qualities of ${config.artistName}.`
    };

    aiStyle.addEventListener('change', () => {
        customPrompt.hidden = aiStyle.value !== 'custom';
    });

    generateButton.addEventListener('click', async () => {
        const prompt = aiStyle.value === 'custom' ? customPrompt.value.trim() : prompts[aiStyle.value];
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

    if (!config.tracks.length) return;

    document.getElementById('play-all').addEventListener('click', () => {
        window.easycorePlayer.playQueue(config.tracks, 0);
    });

    window.addEventListener('easycoreplayerchange', event => {
        document.querySelectorAll('.track-play').forEach(button => {
            button.classList.toggle(
                'is-playing',
                Number(button.dataset.trackId) === Number(event.detail.track?.id) && event.detail.playing
            );
        });
    });
})();
