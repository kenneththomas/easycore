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

    const normalizeTrack = track => ({
        id: Number(track.id),
        title: track.title || `Track ${track.id}`,
        artist: track.artist || 'Unknown artist',
        artwork: track.artwork || '',
        url: track.url || `/stream_track/${track.id}`,
        detailUrl: track.detailUrl || `/track/${track.id}`
    });

    const save = () => {
        clearTimeout(saveTimer);
        saveTimer = setTimeout(() => {
            state.currentTime = audio.currentTime || 0;
            state.playing = !audio.paused;
            state.volume = audio.volume;
            localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
        }, 80);
    };

    const currentTrack = () => state.queue[state.index] || null;
    const announce = type => {
        window.dispatchEvent(new CustomEvent('easycoreplayerchange', {
            detail: {
                type,
                track: currentTrack(),
                playing: !audio.paused,
                currentTime: audio.currentTime || 0,
                duration: audio.duration || 0,
                queue: state.queue,
                index: state.index
            }
        }));
    };

    const renderArtwork = track => {
        art.replaceChildren();
        if (track?.artwork) {
            const image = document.createElement('img');
            image.src = track.artwork;
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
            if (track.artwork) {
                const image = document.createElement('img');
                image.src = track.artwork;
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
            itemArtist.textContent = track.artist;
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
        artist.textContent = track.artist;
        renderArtwork(track);
        toggle.textContent = audio.paused ? '▶' : 'Ⅱ';
        toggle.setAttribute('aria-label', audio.paused ? 'Play' : 'Pause');
        repeatButton.setAttribute('aria-pressed', state.repeat !== 'off' ? 'true' : 'false');
        repeatButton.title = `Repeat: ${state.repeat}`;
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
            if (position > 0 && Number.isFinite(audio.duration)) {
                audio.currentTime = Math.min(position, Math.max(0, audio.duration - .25));
            }
            restoring = false;
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
            state.index = Math.max(0, state.queue.findIndex(item => item.id === normalized.id));
        } else {
            const existingIndex = state.queue.findIndex(item => item.id === normalized.id);
            if (existingIndex >= 0) {
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
        if (!state.queue.some(item => item.id === normalized.id)) state.queue.push(normalized);
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
        if (audio.currentTime > 4) {
            audio.currentTime = 0;
            return;
        }
        load(state.index - 1, { autoplay: true });
    };

    window.easycorePlayer = {
        playTrack,
        playQueue,
        addToQueue,
        next,
        previous,
        toggle: () => toggle.click(),
        seek: seconds => { audio.currentTime = seconds; },
        getState: () => ({ ...state, track: currentTrack(), playing: !audio.paused, duration: audio.duration || 0 })
    };

    toggle.addEventListener('click', () => {
        if (!currentTrack()) return;
        audio.paused ? audio.play().catch(() => {}) : audio.pause();
    });
    document.getElementById('global-player-next').addEventListener('click', next);
    document.getElementById('global-player-prev').addEventListener('click', previous);
    document.getElementById('global-player-close').addEventListener('click', () => {
        audio.pause();
        state = { queue: [], index: -1, currentTime: 0, playing: false, repeat: 'off', volume: audio.volume };
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
        if (Number.isFinite(audio.duration)) audio.currentTime = (Number(progress.value) / 1000) * audio.duration;
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
        currentTime.textContent = formatTime(audio.currentTime);
        duration.textContent = formatTime(audio.duration);
        progress.value = Number.isFinite(audio.duration) && audio.duration > 0
            ? Math.round((audio.currentTime / audio.duration) * 1000)
            : 0;
        if (!restoring) save();
        announce('time');
    });
    audio.addEventListener('ended', () => {
        if (state.repeat === 'one') {
            audio.currentTime = 0;
            audio.play().catch(() => {});
        } else {
            next();
        }
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
            url: trigger.dataset.trackUrl,
            detailUrl: trigger.dataset.trackDetailUrl
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
