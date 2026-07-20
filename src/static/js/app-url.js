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
        if (typeof resource === 'string') {
            resource = window.appUrl(resource);
        }
        return nativeFetch(resource, options);
    };

    const nativeOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function prefixedOpen(method, url, ...args) {
        return nativeOpen.call(this, method, window.appUrl(url), ...args);
    };
})();
