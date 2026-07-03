(() => {
    if (window.easycorePlayer) return;

    const STORAGE_KEY = 'easycore.globalPlayer.v1';
    const player = document.getElementById('global-player');
    const audio = document.getElementById('global-player-audio');
    const art = document.getElementById('global-player-art');
    const title = document.getElementById('global-player-title');
    const artist = document.getElementById('global-player-artist');
    const toggle = document.getElementById('global-player-toggle');
    const progress = document.getElementById('global-player-progress');
    const currentTime = document.getElementById('global-player-current');
    const duration = document.getElementById('global-player-duration');
    const queuePanel = document.getElementById('global-player-queue');
    const queueList = document.getElementById('global-player-queue-list');
    const queueCount = document.getElementById('global-player-queue-count');
    const repeatButton = document.getElementById('global-player-repeat');

    let state = {
        queue: [],
        index: -1,
        currentTime: 0,
        playing: false,
        repeat: 'off',
        volume: 1
    };
    let restoring = false;
    let saveTimer = null;

    const formatTime = seconds => {
        if (!Number.isFinite(seconds)) return '0:00';
        return `${Math.floor(seconds / 60)}:${Math.floor(seconds % 60).toString().padStart(2, '0')}`;
    };

    const normalizePreview = preview => ({
        start: Number.isFinite(Number(preview?.start)) ? Math.max(0, Number(preview.start)) : 0,
        end: Number.isFinite(Number(preview?.end)) ? Math.max(0, Number(preview.end)) : null,
        fadeIn: Boolean(preview?.fadeIn),
        fadeOut: Boolean(preview?.fadeOut),
        fadeInSeconds: Number.isFinite(Number(preview?.fadeInSeconds)) ? Math.min(30, Math.max(0, Number(preview.fadeInSeconds))) : 2,
        fadeOutSeconds: Number.isFinite(Number(preview?.fadeOutSeconds)) ? Math.min(30, Math.max(0, Number(preview.fadeOutSeconds))) : 2
    });

    const fallbackArtistUrl = artistName => {
        const firstArtist = String(artistName || '').split(',')[0].trim();
        if (!firstArtist || firstArtist.toLowerCase() === 'unknown artist') return '';
        return `/artist/${encodeURIComponent(firstArtist)}`;
    };

    const normalizeTrack = track => {
        const preview = normalizePreview(track.preview);
        const previewOnly = Boolean(track.previewOnly) || Boolean(track.previewDefault);
        const artistName = track.artist || 'Unknown artist';
        if (previewOnly && preview.end === null) preview.end = preview.start + 30;
        return {
            id: Number(track.id),
            key: `${Number(track.id)}:${previewOnly ? 'preview' : 'full'}`,
            title: track.title || `Track ${track.id}`,
            artist: artistName,
            artwork: track.artwork || '',
            artistUrl: track.artistUrl || fallbackArtistUrl(artistName),
            artistArtwork: track.artistArtwork || '',
            url: track.url || `/stream_track/${track.id}`,
            detailUrl: track.detailUrl || `/track/${track.id}`,
            preview,
            previewOnly,
            previewDefault: Boolean(track.previewDefault)
        };
    };

    const save = () => {
        clearTimeout(saveTimer);
        saveTimer = setTimeout(() => {
            state.currentTime = audio.currentTime || 0;
            state.playing = !audio.paused;
            localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
        }, 80);
    };

    const currentTrack = () => state.queue[state.index] || null;
    const previewEndFor = track => {
        if (!track?.previewOnly) return null;
        const end = Number(track.preview?.end);
        return Number.isFinite(end) && end > track.preview.start ? end : null;
    };
    const playbackStartFor = track => track?.previewOnly ? Number(track.preview.start) || 0 : 0;
    const playbackEndFor = track => {
        if (!track) return null;
        const previewEnd = previewEndFor(track);
        if (previewEnd) return Number.isFinite(audio.duration) ? Math.min(previewEnd, audio.duration) : previewEnd;
        return Number.isFinite(audio.duration) ? audio.duration : null;
    };
    const playbackDurationFor = track => {
        const end = playbackEndFor(track);
        if (!Number.isFinite(end)) return 0;
        return Math.max(0, end - playbackStartFor(track));
    };
    const playbackCurrentFor = track => {
        const duration = playbackDurationFor(track);
        if (!duration) return 0;
        return Math.min(duration, Math.max(0, (audio.currentTime || 0) - playbackStartFor(track)));
    };
    const renderTimeline = () => {
        const track = currentTrack();
        const playbackDuration = playbackDurationFor(track);
        const playbackCurrent = playbackCurrentFor(track);
        currentTime.textContent = formatTime(playbackCurrent);
        duration.textContent = formatTime(playbackDuration);
        progress.value = playbackDuration > 0
            ? Math.round((playbackCurrent / playbackDuration) * 1000)
            : 0;
    };
    const updatePreviewVolume = () => {
        const track = currentTrack();
        if (!track?.previewOnly) {
            audio.volume = state.volume;
            return;
        }
        const start = Number(track.preview.start) || 0;
        const end = previewEndFor(track);
        let multiplier = 1;
        if (track.preview.fadeIn && track.preview.fadeInSeconds > 0) {
            multiplier = Math.min(multiplier, Math.max(0, (audio.currentTime - start) / track.preview.fadeInSeconds));
        }
        if (track.preview.fadeOut && end && track.preview.fadeOutSeconds > 0) {
            multiplier = Math.min(multiplier, Math.max(0, (end - audio.currentTime) / track.preview.fadeOutSeconds));
        }
        audio.volume = Math.min(1, Math.max(0, state.volume * multiplier));
    };
    const announce = type => {
        window.dispatchEvent(new CustomEvent('easycoreplayerchange', {
            detail: {
                type,
                track: currentTrack(),
                playing: !audio.paused,
                currentTime: playbackCurrentFor(currentTrack()),
                duration: playbackDurationFor(currentTrack()),
                queue: state.queue,
                index: state.index
            }
        }));
    };

    const renderArtwork = track => {
        art.replaceChildren();
        const artwork = track?.artistArtwork || track?.artwork;
        art.href = track?.artistUrl || track?.detailUrl || '#';
        art.classList.toggle('is-clickable', Boolean(track?.artistUrl));
        art.setAttribute('aria-label', track?.artistUrl ? `Open ${track.artist}` : 'Open track');
        if (artwork) {
            const image = document.createElement('img');
            image.src = artwork;
            image.alt = '';
            art.append(image);
        } else {
            const placeholder = document.createElement('span');
            placeholder.textContent = '♪';
            placeholder.setAttribute('aria-hidden', 'true');
            art.append(placeholder);
        }
    };

    const renderQueue = () => {
        queueList.replaceChildren();
        state.queue.forEach((track, index) => {
            const row = document.createElement('div');
            row.className = `global-queue-item${index === state.index ? ' is-current' : ''}`;
            row.dataset.index = index;

            const itemArt = document.createElement('div');
            itemArt.className = 'global-queue-item-art';
            const artwork = track.artistArtwork || track.artwork;
            if (artwork) {
                const image = document.createElement('img');
                image.src = artwork;
                image.alt = '';
                itemArt.append(image);
            } else {
                itemArt.textContent = '♪';
            }

            const copy = document.createElement('div');
            copy.className = 'global-queue-item-copy';
            const itemTitle = document.createElement('strong');
            itemTitle.textContent = track.title;
            const itemArtist = document.createElement('span');
            itemArtist.textContent = track.previewOnly ? `${track.artist} - Preview` : track.artist;
            copy.append(itemTitle, itemArtist);

            const remove = document.createElement('button');
            remove.className = 'global-queue-remove';
            remove.type = 'button';
            remove.dataset.removeIndex = index;
            remove.setAttribute('aria-label', `Remove ${track.title} from queue`);
            remove.textContent = '×';
            row.append(itemArt, copy, remove);
            queueList.append(row);
        });
        queueCount.textContent = state.queue.length;
    };

    const render = () => {
        const track = currentTrack();
        player.hidden = !track;
        document.body.classList.toggle('global-player-active', Boolean(track));
        if (!track) return;
        title.textContent = track.title;
        title.href = track.detailUrl;
        artist.textContent = track.previewOnly ? `${track.artist} - Preview` : track.artist;
        artist.href = track.artistUrl || track.detailUrl || '#';
        artist.classList.toggle('is-clickable', Boolean(track.artistUrl));
        renderArtwork(track);
        toggle.textContent = '';
        toggle.classList.toggle('is-playing', !audio.paused);
        toggle.setAttribute('aria-label', audio.paused ? 'Play' : 'Pause');
        toggle.title = audio.paused ? 'Play' : 'Pause';
        repeatButton.setAttribute('aria-pressed', state.repeat !== 'off' ? 'true' : 'false');
        repeatButton.title = `Repeat: ${state.repeat}`;
        renderTimeline();
        renderQueue();
        announce('render');
    };

    const load = async (index, { autoplay = true, position = 0, increment = true } = {}) => {
        if (!state.queue.length) return;
        state.index = (index + state.queue.length) % state.queue.length;
        const track = currentTrack();
        restoring = true;
        audio.src = track.url;
        audio.load();
        audio.addEventListener('loadedmetadata', async function onMetadata() {
            audio.removeEventListener('loadedmetadata', onMetadata);
            const previewStart = track.previewOnly ? track.preview.start : 0;
            const previewEnd = previewEndFor(track);
            let requestedPosition = position > 0 ? position : previewStart;
            if (previewEnd && (requestedPosition < previewStart || requestedPosition >= previewEnd)) {
                requestedPosition = previewStart;
            }
            if (Number.isFinite(audio.duration)) {
                audio.currentTime = Math.min(Math.max(0, requestedPosition), Math.max(0, audio.duration - .25));
            }
            restoring = false;
            updatePreviewVolume();
            if (autoplay) {
                try { await audio.play(); } catch (_) { state.playing = false; }
            }
            render();
            announce('track');
            save();
        });
        if (increment) fetch(`/increment_track_view/${track.id}`, { method: 'POST' }).catch(() => {});
        render();
    };

    const playTrack = (track, queue = null) => {
        const normalized = normalizeTrack(track);
        if (queue?.length) {
            state.queue = queue.map(normalizeTrack);
            state.index = Math.max(0, state.queue.findIndex(item => item.key === normalized.key));
        } else {
            const existingIndex = state.queue.findIndex(item =>
                item.id === normalized.id && item.previewOnly === normalized.previewOnly
            );
            if (existingIndex >= 0) {
                state.queue[existingIndex] = normalized;
                state.index = existingIndex;
            } else {
                state.queue.push(normalized);
                state.index = state.queue.length - 1;
            }
        }
        state.currentTime = 0;
        load(state.index, { autoplay: true });
    };

    const playQueue = (tracks, startIndex = 0) => {
        if (!tracks.length) return;
        state.queue = tracks.map(normalizeTrack);
        state.index = Math.min(Math.max(startIndex, 0), state.queue.length - 1);
        load(state.index, { autoplay: true });
    };

    const addToQueue = track => {
        const normalized = normalizeTrack(track);
        if (!state.queue.some(item => item.key === normalized.key)) state.queue.push(normalized);
        if (state.index < 0 && state.queue.length) {
            state.index = 0;
            load(0, { autoplay: false, increment: false });
            return;
        }
        render();
        save();
    };

    const next = () => {
        if (!state.queue.length) return;
        if (state.index >= state.queue.length - 1 && state.repeat === 'off') {
            audio.pause();
            audio.currentTime = 0;
            render();
            return;
        }
        load(state.index + 1, { autoplay: true });
    };

    const previous = () => {
        const track = currentTrack();
        if (playbackCurrentFor(track) > 4) {
            audio.currentTime = playbackStartFor(track);
            renderTimeline();
            return;
        }
        load(state.index - 1, { autoplay: true });
    };

    const completeCurrentPlayback = () => {
        if (state.repeat === 'one') {
            const track = currentTrack();
            audio.currentTime = track?.previewOnly ? track.preview.start : 0;
            audio.play().catch(() => {});
        } else {
            next();
        }
    };

    window.easycorePlayer = {
        playTrack,
        playQueue,
        addToQueue,
        next,
        previous,
        toggle: () => toggle.click(),
        seek: seconds => { audio.currentTime = playbackStartFor(currentTrack()) + seconds; },
        getState: () => ({
            ...state,
            track: currentTrack(),
            playing: !audio.paused,
            duration: playbackDurationFor(currentTrack()),
            currentTime: playbackCurrentFor(currentTrack())
        })
    };

    toggle.addEventListener('click', () => {
        if (!currentTrack()) return;
        audio.paused ? audio.play().catch(() => {}) : audio.pause();
    });
    document.getElementById('global-player-next').addEventListener('click', next);
    document.getElementById('global-player-prev').addEventListener('click', previous);
    document.getElementById('global-player-close').addEventListener('click', () => {
        audio.pause();
        state = { queue: [], index: -1, currentTime: 0, playing: false, repeat: 'off', volume: state.volume };
        localStorage.removeItem(STORAGE_KEY);
        queuePanel.hidden = true;
        render();
    });
    document.getElementById('global-player-queue-toggle').addEventListener('click', () => {
        queuePanel.hidden = !queuePanel.hidden;
    });
    document.getElementById('global-player-clear').addEventListener('click', () => {
        const track = currentTrack();
        state.queue = track ? [track] : [];
        state.index = track ? 0 : -1;
        render();
        save();
    });
    repeatButton.addEventListener('click', () => {
        state.repeat = state.repeat === 'off' ? 'all' : state.repeat === 'all' ? 'one' : 'off';
        render();
        save();
    });
    progress.addEventListener('input', () => {
        const track = currentTrack();
        const playbackDuration = playbackDurationFor(track);
        if (playbackDuration > 0) {
            audio.currentTime = playbackStartFor(track) + (Number(progress.value) / 1000) * playbackDuration;
            renderTimeline();
            updatePreviewVolume();
        }
    });
    queueList.addEventListener('click', event => {
        const remove = event.target.closest('[data-remove-index]');
        if (remove) {
            event.stopPropagation();
            const removeIndex = Number(remove.dataset.removeIndex);
            if (removeIndex === state.index) {
                state.queue.splice(removeIndex, 1);
                if (!state.queue.length) {
                    audio.pause();
                    state.index = -1;
                } else {
                    state.index = Math.min(removeIndex, state.queue.length - 1);
                    load(state.index, { autoplay: true });
                }
            } else {
                state.queue.splice(removeIndex, 1);
                if (removeIndex < state.index) state.index -= 1;
            }
            render();
            save();
            return;
        }
        const row = event.target.closest('[data-index]');
        if (row) load(Number(row.dataset.index), { autoplay: true });
    });

    audio.addEventListener('play', () => { render(); announce('play'); save(); });
    audio.addEventListener('pause', () => { render(); announce('pause'); save(); });
    audio.addEventListener('timeupdate', () => {
        updatePreviewVolume();
        const track = currentTrack();
        const previewEnd = previewEndFor(track);
        if (previewEnd && audio.currentTime >= previewEnd - .05) {
            completeCurrentPlayback();
            return;
        }
        renderTimeline();
        if (!restoring) save();
        announce('time');
    });
    audio.addEventListener('ended', () => {
        completeCurrentPlayback();
    });
    window.addEventListener('pagehide', () => {
        state.currentTime = audio.currentTime || 0;
        state.playing = !audio.paused;
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    });

    document.addEventListener('click', event => {
        const trigger = event.target.closest('[data-global-track]');
        if (!trigger) return;
        event.preventDefault();
        const track = {
            id: trigger.dataset.trackId,
            title: trigger.dataset.trackTitle,
            artist: trigger.dataset.trackArtist,
            artwork: trigger.dataset.trackArtwork,
            artistUrl: trigger.dataset.trackArtistUrl,
            artistArtwork: trigger.dataset.trackArtistArtwork,
            url: trigger.dataset.trackUrl,
            detailUrl: trigger.dataset.trackDetailUrl,
            previewOnly: trigger.dataset.previewOnly === 'true',
            previewDefault: trigger.dataset.previewDefault === 'true',
            preview: {
                start: trigger.dataset.previewStart,
                end: trigger.dataset.previewEnd,
                fadeIn: trigger.dataset.previewFadeIn === 'true',
                fadeOut: trigger.dataset.previewFadeOut === 'true',
                fadeInSeconds: trigger.dataset.previewFadeInSeconds,
                fadeOutSeconds: trigger.dataset.previewFadeOutSeconds
            }
        };
        if (trigger.dataset.queue === 'add') {
            addToQueue(track);
            const originalText = trigger.textContent;
            trigger.textContent = 'Queued';
            setTimeout(() => { trigger.textContent = originalText; }, 900);
        } else {
            playTrack(track);
        }
    });

    try {
        const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
        if (saved?.queue?.length) {
            state = { ...state, ...saved, queue: saved.queue.map(normalizeTrack) };
            audio.volume = state.volume;
            load(state.index >= 0 ? state.index : 0, {
                autoplay: Boolean(state.playing),
                position: Number(state.currentTime) || 0,
                increment: false
            });
        }
    } catch (_) {
        localStorage.removeItem(STORAGE_KEY);
    }
})();
