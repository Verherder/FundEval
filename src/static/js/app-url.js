(function initializeAppUrls() {
    const configuredBase = document.documentElement.dataset.appBase || '';
    const appBase = configuredBase === '/' ? '' : configuredBase.replace(/\/$/, '');

    window.appBase = appBase;
    window.appUrl = function appUrl(path) {
        if (typeof path !== 'string' || !path.startsWith('/') || path.startsWith('//')) {
            return path;
        }
        if (appBase && (path === appBase || path.startsWith(`${appBase}/`))) {
            return path;
        }
        return `${appBase}${path}`;
    };
    window.appPathname = function appPathname() {
        const pathname = window.location.pathname;
        if (!appBase) return pathname;
        const relativePath = pathname.slice(appBase.length);
        return relativePath || '/';
    };

    const nativeFetch = window.fetch.bind(window);
    window.fetch = function prefixedFetch(resource, options) {
        options = options ? { ...options } : {};
        if (typeof resource === 'string') {
            resource = window.appUrl(resource);
        }
        const method = String(options.method || 'GET').toUpperCase();
        if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
            const token = document.querySelector('meta[name="csrf-token"]')?.content;
            options.headers = new Headers(options.headers || {});
            if (token) options.headers.set('X-CSRF-Token', token);
        }
        return nativeFetch(resource, options);
    };

    const nativeOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function prefixedOpen(method, url, ...args) {
        this.__fundEvalMethod = String(method || 'GET').toUpperCase();
        return nativeOpen.call(this, method, window.appUrl(url), ...args);
    };
    const nativeSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function csrfSend(...args) {
        if (!['GET', 'HEAD', 'OPTIONS'].includes(this.__fundEvalMethod)) {
            const token = document.querySelector('meta[name="csrf-token"]')?.content;
            if (token) this.setRequestHeader('X-CSRF-Token', token);
        }
        return nativeSend.apply(this, args);
    };
})();
