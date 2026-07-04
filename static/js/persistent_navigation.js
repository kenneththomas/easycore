(() => {
    if (window.easycoreNavigation) return;

    const PERSISTENT_SELECTORS = [
        '.navbar',
        '#global-player',
        '#global-player-queue',
        'link[href*="/static/css/global_player.css"]',
        'script[src*="/static/js/global_player.js"]',
        'script[src*="/static/js/persistent_navigation.js"]',
        '#navbar-script'
    ];
    const SKIP_SCRIPT_RE = /\/static\/js\/(?:global_player|persistent_navigation)\.js(?:\?|$)/;

    let navigating = false;

    const isPersistent = node => {
        if (!(node instanceof Element)) return false;
        return PERSISTENT_SELECTORS.some(selector => node.matches(selector));
    };

    const playerIsActive = () => {
        const state = window.easycorePlayer?.getState?.();
        return Boolean(state?.track || document.getElementById('global-player-audio')?.src);
    };

    const shouldHandleUrl = url => {
        if (url.origin !== window.location.origin) return false;
        if (url.pathname.startsWith('/stream') || url.pathname.startsWith('/api/')) return false;
        if (url.pathname.match(/\.[a-z0-9]{2,5}$/i) && !url.pathname.endsWith('.html')) return false;
        return true;
    };

    const shouldHandleLink = (event, link) => {
        if (event.defaultPrevented || event.button !== 0) return false;
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return false;
        if (!link.href || link.target || link.hasAttribute('download')) return false;
        if (link.dataset.normalNavigation === 'true') return false;

        const url = new URL(link.href, window.location.href);
        if (!shouldHandleUrl(url)) return false;
        if (url.pathname === window.location.pathname && url.search === window.location.search) {
            return Boolean(url.hash);
        }
        return true;
    };

    const syncHead = nextDocument => {
        document.title = nextDocument.title || document.title;
        document.head.querySelectorAll('link[rel="stylesheet"], style').forEach(node => node.remove());
        nextDocument.head.querySelectorAll('link[rel="stylesheet"], style').forEach(node => {
            document.head.append(node.cloneNode(true));
        });
    };

    const runReadyHandler = handler => {
        if (typeof handler === 'function') {
            handler.call(document, new Event('DOMContentLoaded'));
        } else if (handler && typeof handler.handleEvent === 'function') {
            handler.handleEvent(new Event('DOMContentLoaded'));
        }
    };

    const activateScripts = async root => {
        const scripts = Array.from(root.querySelectorAll('script'));
        const readyHandlers = [];
        const originalAddEventListener = document.addEventListener;

        document.addEventListener = (type, handler, options) => {
            if (type === 'DOMContentLoaded') {
                readyHandlers.push(handler);
                return;
            }
            originalAddEventListener.call(document, type, handler, options);
        };

        try {
            for (const script of scripts) {
                const src = script.getAttribute('src') || '';
                if (SKIP_SCRIPT_RE.test(src)) {
                    script.remove();
                    continue;
                }

                const activeScript = document.createElement('script');
                Array.from(script.attributes).forEach(attribute => {
                    activeScript.setAttribute(attribute.name, attribute.value);
                });
                activeScript.textContent = script.textContent;
                if (src) activeScript.async = false;

                const loaded = src
                    ? new Promise(resolve => {
                        activeScript.addEventListener('load', resolve, { once: true });
                        activeScript.addEventListener('error', resolve, { once: true });
                    })
                    : Promise.resolve();

                script.replaceWith(activeScript);
                await loaded;
            }
        } finally {
            document.addEventListener = originalAddEventListener;
        }

        readyHandlers.forEach(runReadyHandler);
    };

    const dispatchPageReady = () => {
        window.dispatchEvent(new Event('easycorenavigation'));
    };

    const replaceBody = async nextDocument => {
        const playerWasActive = document.body.classList.contains('global-player-active');
        const nextBodyClass = nextDocument.body.getAttribute('class') || '';
        document.body.setAttribute('class', nextBodyClass);
        document.body.classList.toggle('global-player-active', playerWasActive);

        Array.from(nextDocument.body.children).forEach(node => {
            if (isPersistent(node)) node.remove();
        });

        Array.from(document.body.children).forEach(node => {
            if (!isPersistent(node)) node.remove();
        });

        const fragment = document.createDocumentFragment();
        Array.from(nextDocument.body.children).forEach(node => {
            fragment.append(document.importNode(node, true));
        });
        document.body.append(fragment);
        await activateScripts(document.body);
        dispatchPageReady();
    };

    const visit = async (href, { historyMode = 'push' } = {}) => {
        if (navigating) return;
        const url = new URL(href, window.location.href);
        if (!shouldHandleUrl(url)) {
            window.location.href = url.href;
            return;
        }

        navigating = true;
        document.documentElement.classList.add('is-soft-navigating');

        try {
            const response = await fetch(url.href, {
                headers: { 'X-Easycore-Navigation': 'soft' },
                credentials: 'same-origin'
            });
            const contentType = response.headers.get('content-type') || '';
            if (!response.ok || !contentType.includes('text/html')) {
                window.location.href = url.href;
                return;
            }

            const html = await response.text();
            const nextDocument = new DOMParser().parseFromString(html, 'text/html');
            syncHead(nextDocument);
            await replaceBody(nextDocument);

            if (historyMode === 'replace') {
                window.history.replaceState({ easycore: true }, '', url.href);
            } else {
                window.history.pushState({ easycore: true }, '', url.href);
            }
            window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
        } catch (_) {
            window.location.href = url.href;
        } finally {
            navigating = false;
            document.documentElement.classList.remove('is-soft-navigating');
        }
    };

    document.addEventListener('click', event => {
        const link = event.target.closest('a[href]');
        if (!link || !shouldHandleLink(event, link)) return;
        if (!playerIsActive()) return;

        event.preventDefault();
        visit(link.href);
    });

    document.addEventListener('submit', event => {
        const form = event.target;
        if (!(form instanceof HTMLFormElement)) return;
        if ((form.method || 'get').toLowerCase() !== 'get') return;
        if (form.dataset.normalNavigation === 'true') return;
        if (!playerIsActive()) return;

        const action = form.action || window.location.href;
        const url = new URL(action, window.location.href);
        if (!shouldHandleUrl(url)) return;

        event.preventDefault();
        const formData = new FormData(form);
        url.search = new URLSearchParams(formData).toString();
        visit(url.href);
    });

    window.addEventListener('popstate', () => {
        if (!playerIsActive()) {
            window.location.reload();
            return;
        }
        visit(window.location.href, { historyMode: 'replace' });
    });

    window.easycoreNavigation = { visit };
})();
