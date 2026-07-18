document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('refreshSettingsForm');
    if (!form) return;

    const enabledInput = document.getElementById('autoRefreshEnabled');
    const intervalInput = document.getElementById('autoRefreshInterval');
    const batchInput = document.getElementById('requestBatchSize');
    const saveButton = document.getElementById('saveSettingsBtn');
    const status = document.getElementById('settingsStatus');

    const showStatus = (message, isError = false) => {
        status.textContent = message;
        status.classList.toggle('error', isError);
    };

    const readJson = async (response) => {
        try {
            return await response.json();
        } catch (_error) {
            throw new Error(response.ok ? '服务器返回了无效数据' : '设置请求失败');
        }
    };

    const loadSettings = async () => {
        try {
            const response = await fetch('/api/config/refresh');
            const settings = await readJson(response);
            if (!response.ok) throw new Error(settings.message || '读取设置失败');
            enabledInput.checked = settings.auto_refresh_enabled !== false;
            intervalInput.value = Math.round(settings.auto_refresh_interval / 1000);
            batchInput.value = settings.request_batch_size;
        } catch (error) {
            showStatus(error.message, true);
        }
    };

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (!form.reportValidity()) return;
        saveButton.disabled = true;
        showStatus('正在保存...');
        try {
            const response = await fetch('/api/config/refresh', {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    auto_refresh_enabled: enabledInput.checked,
                    auto_refresh_interval: Number(intervalInput.value) * 1000,
                    request_batch_size: Number(batchInput.value)
                })
            });
            const result = await readJson(response);
            if (!response.ok || !result.success) {
                throw new Error(result.message || '保存设置失败');
            }
            showStatus('设置已保存，下次刷新时生效');
        } catch (error) {
            showStatus(error.message, true);
        } finally {
            saveButton.disabled = false;
        }
    });

    loadSettings();
});
