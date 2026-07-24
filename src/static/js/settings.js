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

    const invitationDays = document.getElementById('invitationDays');
    const invitationCode = document.getElementById('invitationCode');
    const invitationExpiry = document.getElementById('invitationExpiry');
    const invitationResultRow = document.getElementById('invitationResultRow');
    const invitationStatus = document.getElementById('invitationStatus');
    const generateInvitationBtn = document.getElementById('generateInvitationBtn');
    const copyInvitationBtn = document.getElementById('copyInvitationBtn');

    generateInvitationBtn?.addEventListener('click', async () => {
        const days = Number(invitationDays.value);
        if (!Number.isInteger(days) || days < 1 || days > 30) {
            invitationStatus.textContent = '有效天数必须在 1 到 30 天之间';
            invitationStatus.classList.add('error');
            return;
        }
        generateInvitationBtn.disabled = true;
        invitationStatus.textContent = '正在生成...';
        invitationStatus.classList.remove('error');
        try {
            const response = await fetch('/api/admin/invitations', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({days})
            });
            const result = await readJson(response);
            if (!response.ok || !result.success) {
                throw new Error(result.message || '邀请码生成失败');
            }
            invitationCode.value = result.invite_code;
            invitationExpiry.textContent = `有效期至 ${new Date(result.expires_at).toLocaleString()}`;
            invitationResultRow.hidden = false;
            invitationStatus.textContent = '邀请码已生成';
        } catch (error) {
            invitationStatus.textContent = error.message;
            invitationStatus.classList.add('error');
        } finally {
            generateInvitationBtn.disabled = false;
        }
    });

    copyInvitationBtn?.addEventListener('click', async () => {
        if (!invitationCode.value) return;
        try {
            await navigator.clipboard.writeText(invitationCode.value);
            invitationStatus.textContent = '邀请码已复制';
        } catch (_error) {
            invitationCode.select();
            document.execCommand('copy');
            invitationStatus.textContent = '邀请码已复制';
        }
    });

    const userManagementBody = document.getElementById('userManagementBody');
    const userManagementStatus = document.getElementById('userManagementStatus');
    const refreshUsersBtn = document.getElementById('refreshUsersBtn');

    const updateUser = async (userId, payload) => {
        const response = await fetch(`/api/admin/users/${userId}`, {
            method: 'PATCH',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const result = await readJson(response);
        if (!response.ok || !result.success) {
            throw new Error(result.message || '用户更新失败');
        }
    };

    const renderUsers = (users, currentUserId) => {
        userManagementBody.innerHTML = users.map((user) => {
            const isSelf = user.id === currentUserId;
            const roleAction = user.is_admin ? '撤销管理员' : '设为管理员';
            const lockAction = user.is_locked ? '解锁' : '锁定';
            return `
                <tr style="border-top:1px solid var(--border);">
                    <td style="padding:10px;">${user.username}</td>
                    <td style="text-align:center; padding:10px;">${user.is_admin ? '管理员' : '普通用户'}</td>
                    <td style="text-align:center; padding:10px;">${user.is_locked ? '已锁定' : '正常'}</td>
                    <td style="text-align:right; padding:10px;">${user.personal_funds}</td>
                    <td style="text-align:right; padding:10px;">${user.transactions}</td>
                    <td style="padding:10px;">
                        <div style="display:flex; justify-content:flex-end; gap:8px; flex-wrap:wrap;">
                            <button type="button" class="btn btn-secondary user-role-btn"
                                    data-user-id="${user.id}" data-next-admin="${user.is_admin ? '0' : '1'}"
                                    ${isSelf ? 'disabled' : ''}>${roleAction}</button>
                            <button type="button" class="btn btn-secondary user-lock-btn"
                                    data-user-id="${user.id}" data-next-locked="${user.is_locked ? '0' : '1'}"
                                    ${isSelf ? 'disabled' : ''}>${lockAction}</button>
                            <button type="button" class="btn btn-primary user-password-btn"
                                    data-user-id="${user.id}" data-username="${user.username}">重置密码</button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    };

    const loadUsers = async () => {
        userManagementStatus.textContent = '正在加载...';
        try {
            const response = await fetch('/api/admin/users');
            const result = await readJson(response);
            if (!response.ok || !result.success) {
                throw new Error(result.message || '用户列表加载失败');
            }
            renderUsers(result.users, result.current_user_id);
            userManagementStatus.textContent = `共 ${result.users.length} 个用户`;
        } catch (error) {
            userManagementStatus.textContent = error.message;
            userManagementStatus.classList.add('error');
        }
    };

    userManagementBody?.addEventListener('click', async (event) => {
        const roleButton = event.target.closest('.user-role-btn');
        const lockButton = event.target.closest('.user-lock-btn');
        const passwordButton = event.target.closest('.user-password-btn');
        if (!roleButton && !lockButton && !passwordButton) return;

        try {
            if (roleButton) {
                await updateUser(Number(roleButton.dataset.userId), {
                    action: 'set_admin',
                    is_admin: roleButton.dataset.nextAdmin === '1'
                });
            } else if (lockButton) {
                await updateUser(Number(lockButton.dataset.userId), {
                    action: 'set_locked',
                    is_locked: lockButton.dataset.nextLocked === '1'
                });
            } else {
                const username = passwordButton.dataset.username;
                const password = window.prompt(`请输入 ${username} 的新密码（12-20位字母、数字或安全符号）`, '');
                if (password === null) return;
                if (!/^[A-Za-z0-9@#$%^&*_.!+\-]{12,20}$/.test(password)) {
                    throw new Error('密码须为12-20位字母、数字或允许的安全符号');
                }
                await updateUser(Number(passwordButton.dataset.userId), {
                    action: 'reset_password',
                    password
                });
            }
            userManagementStatus.textContent = '用户已更新';
            userManagementStatus.classList.remove('error');
            await loadUsers();
        } catch (error) {
            userManagementStatus.textContent = error.message;
            userManagementStatus.classList.add('error');
        }
    });

    refreshUsersBtn?.addEventListener('click', loadUsers);
    loadUsers();
});
