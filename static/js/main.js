// Polyfill process for React libraries
window.process = {
    env: {
        NODE_ENV: 'production'
    }
};

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Auto Colorize
    if (window.location.pathname !== '/portfolio') {
        autoColorize();
    }

    window.showSimpleMessage = function(message, type = 'info') {
        if (!message) return;

        let container = document.getElementById('simpleMessageContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'simpleMessageContainer';
            container.style.position = 'fixed';
            container.style.top = '20px';
            container.style.right = '20px';
            container.style.zIndex = '99999';
            container.style.display = 'flex';
            container.style.flexDirection = 'column';
            container.style.gap = '8px';
            document.body.appendChild(container);
        }

        const item = document.createElement('div');
        item.textContent = String(message);
        item.style.padding = '10px 12px';
        item.style.borderRadius = '8px';
        item.style.fontSize = '13px';
        item.style.background = 'var(--card-bg)';
        item.style.color = 'var(--text-main)';
        item.style.border = 'none';
        item.style.boxShadow = '0 6px 16px rgba(0,0,0,0.12)';
        item.style.maxWidth = '360px';
        item.style.wordBreak = 'break-word';
        item.style.opacity = '0';
        item.style.transform = 'translateY(-6px)';
        item.style.transition = 'all 0.2s ease';

        if (type === 'success') {
            item.style.background = 'var(--gh-success-bg)';
            item.style.color = 'var(--gh-success-fg)';
        } else if (type === 'backfill-success') {
            item.style.background = 'var(--gh-accent-bg)';
            item.style.color = 'var(--text-main)';
        }

        container.appendChild(item);
        requestAnimationFrame(() => {
            item.style.opacity = '1';
            item.style.transform = 'translateY(0)';
        });

        setTimeout(() => {
            item.style.opacity = '0';
            item.style.transform = 'translateY(-6px)';
            setTimeout(() => {
                if (item.parentNode) {
                    item.parentNode.removeChild(item);
                }
                if (container && !container.hasChildNodes() && container.parentNode) {
                    container.parentNode.removeChild(container);
                }
            }, 220);
        }, 1800);
    };

    window.showTaskProgress = function(title = '处理中', detail = '准备中...', percent = 0, statsText = '') {
        let panel = document.getElementById('taskProgressPanel');
        if (!panel) {
            panel = document.createElement('div');
            panel.id = 'taskProgressPanel';
            panel.style.position = 'fixed';
            panel.style.right = '20px';
            panel.style.bottom = '20px';
            panel.style.zIndex = '100000';
            panel.style.width = '320px';
            panel.style.maxWidth = 'calc(100vw - 32px)';
            panel.style.padding = '14px 16px';
            panel.style.borderRadius = '12px';
            panel.style.background = 'var(--card-bg)';
            panel.style.color = 'var(--text-main)';
            panel.style.boxShadow = '0 12px 30px rgba(0,0,0,0.18)';
            panel.style.border = '1px solid var(--border)';
            panel.innerHTML = `
                <div id="taskProgressTitle" style="font-size:14px;font-weight:600;margin-bottom:8px;"></div>
                <div id="taskProgressDetail" style="font-size:12px;color:var(--text-dim);margin-bottom:10px;"></div>
                <div style="height:8px;border-radius:999px;background:rgba(148,163,184,0.22);overflow:hidden;">
                    <div id="taskProgressBar" style="height:100%;width:0%;background:linear-gradient(90deg,#60a5fa,#3b82f6);transition:width 0.2s ease;"></div>
                </div>
                <div id="taskProgressPercent" style="margin-top:8px;font-size:12px;color:var(--text-dim);text-align:right;"></div>
            `;
            document.body.appendChild(panel);
        }
        panel.style.display = 'block';
        window.updateTaskProgress(title, detail, percent, statsText);
    };

    window.updateTaskProgress = function(title = '处理中', detail = '准备中...', percent = 0, statsText = '') {
        const panel = document.getElementById('taskProgressPanel');
        if (!panel) return;
        const titleEl = document.getElementById('taskProgressTitle');
        const detailEl = document.getElementById('taskProgressDetail');
        const barEl = document.getElementById('taskProgressBar');
        const percentEl = document.getElementById('taskProgressPercent');
        const normalizedPercent = Math.max(0, Math.min(100, Number(percent || 0)));
        if (titleEl) titleEl.textContent = String(title || '处理中');
        if (detailEl) detailEl.textContent = String(detail || '');
        if (barEl) barEl.style.width = `${normalizedPercent}%`;
        if (percentEl) {
            percentEl.textContent = statsText
                ? `${statsText} · ${Math.round(normalizedPercent)}%`
                : `${Math.round(normalizedPercent)}%`;
        }
    };

    window.hideTaskProgress = function() {
        const panel = document.getElementById('taskProgressPanel');
        if (!panel) return;
        panel.style.display = 'none';
    };

    // 基金表格“标记”列：点击五角星切换持有/取消持有（事件委托，动态内容也生效）
    if (!window._fundHoldStarListenerAdded) {
        window._fundHoldStarListenerAdded = true;
        document.body.addEventListener('click', async function(e) {
            const star = e.target.closest('.fund-hold-star');
            const codeCell = !star ? e.target.closest('.fund-code-cell') : null;
            const nameCell = !star ? e.target.closest('.fund-name-cell') : null;
            const estimateCell = !star && !nameCell ? e.target.closest('.fund-estimate-cell') : null;
            const positionAmountCell = !star && !nameCell && !estimateCell ? e.target.closest('.fund-position-amount-cell') : null;
            const positionGainCell = !star && !nameCell && !estimateCell && !positionAmountCell ? e.target.closest('.fund-position-gain-cell') : null;
            if (!star && !codeCell && !nameCell && !estimateCell && !positionAmountCell && !positionGainCell) return;
            e.preventDefault();
            e.stopPropagation();

            // 星标点击：切换持有
            if (star) {
                const code = star.dataset.code;
                const currentlyHeld = star.dataset.hold === '1';
                const newHold = !currentlyHeld;

                // 简单防抖：请求期间禁用点击
                if (star.dataset.loading === '1') return;
                star.dataset.loading = '1';

                try {
                    const response = await fetch('/api/fund/hold', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ codes: code, hold: newHold })
                    });
                    const result = await response.json();
                    if (result.success) {
                        star.textContent = newHold ? '⭐' : '☆';
                        star.dataset.hold = newHold ? '1' : '0';
                    } else {
                        alert(result.message || '操作失败');
                    }
                } catch (err) {
                    alert('操作失败: ' + (err?.message || err));
                } finally {
                    star.dataset.loading = '0';
                }
                return;
            }

            // 基金编码点击：不触发图表展开
            if (codeCell) return;

            // 基金名称点击：展开/收起当前行的基金趋势曲线（业绩）
            if (nameCell && window.toggleFundRowChart) {
                const code = nameCell.dataset.code;
                window.toggleFundRowChart(code, 'performance', 'SINCE_ESTABLISHMENT');
                return;
            }

            // 估值点击：展开/收起当前行的估值曲线
            if (estimateCell && window.toggleFundRowChart) {
                const code = estimateCell.dataset.code;
                window.toggleFundRowChart(code, 'estimate');
                return;
            }

            // 持仓金额点击：打开交易记录弹窗
            if (positionAmountCell && window.openTransactionModal) {
                const code = positionAmountCell.dataset.code;
                window.openTransactionModal(code);
                return;
            }

            // 收益数值点击：展开累计收益曲线
            if (positionGainCell && window.toggleFundRowChart) {
                const code = positionGainCell.dataset.code;
                window.toggleFundRowChart(code, 'profit', 'THREE_MONTH');
            }
        });
    }

    // Legacy Sidebar Toggle (id="sidebar")
    // Used by /market, /market-indices, /precious-metals, /sectors pages
    // Note: /portfolio uses sidebarNav with sidebar-nav.js instead
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');

    if (sidebar && sidebarToggle && sidebar.id === 'sidebar') {
        sidebarToggle.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            sidebar.classList.toggle('collapsed');
            // Update toggle button direction
            const isCollapsed = sidebar.classList.contains('collapsed');
            sidebarToggle.textContent = isCollapsed ? '▶' : '◀';
            sidebarToggle.title = isCollapsed ? '展开' : '折叠';
        });
    }

    // Mobile Hamburger Menu for Legacy Sidebar
    const hamburger = document.getElementById('hamburgerMenu');
    const mobileSidebar = document.getElementById('sidebar');
    let sidebarOverlay = document.getElementById('sidebarOverlay');

    // Only initialize if hamburger menu exists (mobile support)
    if (hamburger && mobileSidebar) {
        // Create overlay if not exists
        if (!sidebarOverlay) {
            sidebarOverlay = document.createElement('div');
            sidebarOverlay.id = 'sidebarOverlay';
            sidebarOverlay.className = 'sidebar-overlay';
            document.body.appendChild(sidebarOverlay);
        }

        // Toggle sidebar
        hamburger.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            const isActive = mobileSidebar.classList.contains('mobile-active');

            if (isActive) {
                closeMobileSidebar();
            } else {
                openMobileSidebar();
            }
        });

        // Close sidebar when clicking overlay
        sidebarOverlay.addEventListener('click', closeMobileSidebar);

        // Close sidebar when window is resized to desktop
        window.addEventListener('resize', function() {
            if (window.innerWidth > 768) {
                closeMobileSidebar();
            }
        });

        // Close sidebar when clicking navigation links
        const sidebarLinks = mobileSidebar.querySelectorAll('.sidebar-item');
        sidebarLinks.forEach(link => {
            link.addEventListener('click', closeMobileSidebar);
        });

        function openMobileSidebar() {
            mobileSidebar.classList.add('mobile-active');
            hamburger.classList.add('active');
            sidebarOverlay.classList.add('active');
            document.body.style.overflow = 'hidden'; // Prevent background scrolling
        }

        function closeMobileSidebar() {
            mobileSidebar.classList.remove('mobile-active');
            hamburger.classList.remove('active');
            sidebarOverlay.classList.remove('active');
            document.body.style.overflow = ''; // Restore scrolling
        }
    }
});

function autoColorize() {
    // Use requestAnimationFrame to ensure DOM is updated
    requestAnimationFrame(() => {
        const cells = document.querySelectorAll('.style-table td');

        const extractSignedNumber = (text) => {
            // 优先提取百分号前的最后一个数字（适配“3/20 -1.23%”）
            const pctMatches = [...text.matchAll(/([+-]?\d+(?:\.\d+)?)\s*%/g)];
            if (pctMatches.length > 0) {
                return parseFloat(pctMatches[pctMatches.length - 1][1]);
            }

            // 再提取文本中的最后一个带符号数字
            const signedMatches = text.match(/[+-]?\d+(?:\.\d+)?/g);
            if (signedMatches && signedMatches.length > 0) {
                return parseFloat(signedMatches[signedMatches.length - 1]);
            }

            return NaN;
        };

        cells.forEach(cell => {
            // Clear existing color classes first
            cell.classList.remove('positive', 'negative');

            // 跳过基金名称列（如 A100 等名称中的数字不应触发着色）
            if (cell.querySelector('.fund-name-cell')) {
                return;
            }

            // 跳过“持仓/收益”单元格，避免持仓金额被红绿着色
            if (cell.querySelector('.fund-position-amount-cell, .fund-position-gain-cell')) {
                return;
            }

            const text = cell.textContent.trim();

            // Skip empty cells or non-data cells
            if (!text || text === '-' || text === 'N/A' || text === '---') {
                return;
            }

            // Handle "利好" (bullish/positive) and "利空" (bearish/negative) for news
            if (text === '利好') {
                cell.classList.add('positive');
                return;
            } else if (text === '利空') {
                cell.classList.add('negative');
                return;
            }

            // 仅对“像涨跌值”的文本进行着色，避免普通名称中的数字被误判
            const hasFinancialHint = text.includes('%') || /^[+-]/.test(text) || /[+-]\d/.test(text);
            if (!hasFinancialHint) {
                return;
            }

            const val = extractSignedNumber(text);
            if (!isNaN(val)) {
                if (val < 0) {
                    cell.classList.add('negative');  // Green for negative
                } else if (val > 0) {
                    cell.classList.add('positive');   // Red for positive
                }
            }
        });
    });
}

function sortTable(table, columnIndex) {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const currentSortCol = table.dataset.sortCol;
    const currentSortDir = table.dataset.sortDir || 'asc';
    let direction = 'asc';

    if (currentSortCol == columnIndex) {
        direction = currentSortDir === 'asc' ? 'desc' : 'asc';
    }
    table.dataset.sortCol = columnIndex;
    table.dataset.sortDir = direction;

    rows.sort((a, b) => {
        const aText = a.cells[columnIndex].textContent.trim();
        const bText = b.cells[columnIndex].textContent.trim();
        const valA = parseValue(aText);
        const valB = parseValue(bText);
        let comparison = 0;
        if (valA > valB) {
            comparison = 1;
        } else if (valA < valB) {
            comparison = -1;
        }
        return direction === 'asc' ? comparison : -comparison;
    });

    tbody.innerHTML = '';
    rows.forEach(row => tbody.appendChild(row));

    table.querySelectorAll('th').forEach(th => {
        th.classList.remove('sorted-asc', 'sorted-desc');
    });
    const headerToUpdate = table.querySelectorAll('th')[columnIndex];
    if (headerToUpdate) {
        headerToUpdate.classList.add(direction === 'asc' ? 'sorted-asc' : 'sorted-desc');
    }
}

function parseValue(val) {
    if (val === 'N/A' || val === '--' || val === '---' || val === '') {
        return -Infinity;
    }
    const cleanedVal = val.replace(/[%亿万元\/克手]/g, '').replace(/[¥,]/g, '');
    const num = parseFloat(cleanedVal);
    return isNaN(num) ? val.toLowerCase() : num;
}

// 页面加载时加载份额数据并计算持仓统计
// This function is called only in portfolio.html, not globally
async function loadSharesData() {
    try {
        // 从后端API获取用户的基金数据（包含份额）
        const response = await fetch('/api/fund/data');
        if (response.ok) {
            const fundData = await response.json();

            // 初始化全局份额数据存储
            window.fundSharesData = {};
            window.fundSectorsData = {};  // 存储板块数据

            // 填充份额数据到全局存储
            for (const [code, data] of Object.entries(fundData)) {
                if (data.shares !== undefined && data.shares !== null) {
                    window.fundSharesData[code] = parseFloat(data.shares) || 0;
                }
                // 存储板块数据
                if (data.sectors && data.sectors.length > 0) {
                    window.fundSectorsData[code] = data.sectors;
                }

                // 如果有份额输入框，也填充（旧版页面兼容）
                const sharesInput = document.getElementById('shares_' + code);
                if (sharesInput && data.shares) {
                    sharesInput.value = data.shares;
                }
            }

            console.log('已加载份额数据:', window.fundSharesData);

            // 计算持仓统计
            if (typeof calculatePositionSummary === 'function') {
                calculatePositionSummary();
            }
        }
    } catch (e) {
        console.error('加载份额数据失败:', e);
        // 即使加载失败，也尝试计算持仓统计
        if (typeof calculatePositionSummary === 'function') {
            calculatePositionSummary();
        }
    }
}

function openTab(evt, tabId) {
    // Hide all tab contents
    const allContents = document.querySelectorAll('.tab-content');
    allContents.forEach(content => {
        content.classList.remove('active');
    });

    // Remove active class from all tab buttons
    const allButtons = document.querySelectorAll('.tab-button');
    allButtons.forEach(button => {
        button.classList.remove('active');
    });

    // Show the clicked tab's content and add active class to the button
    document.getElementById(tabId).classList.add('active');
    evt.currentTarget.classList.add('active');
}

// Fund Operations Functions
// 板块分类数据
const SECTOR_CATEGORIES = {
    "科技": ["人工智能", "半导体", "云计算", "5G", "光模块", "CPO", "F5G", "通信设备", "PCB", "消费电子",
            "计算机", "软件开发", "信创", "网络安全", "IT服务", "国产软件", "计算机设备", "光通信",
            "算力", "脑机接口", "通信", "电子", "光学光电子", "元件", "存储芯片", "第三代半导体",
            "光刻胶", "电子化学品", "LED", "毫米波", "智能穿戴", "东数西算", "数据要素", "国资云",
            "Web3.0", "AIGC", "AI应用", "AI手机", "AI眼镜", "DeepSeek", "TMT", "科技"],
    "医药健康": ["医药生物", "医疗器械", "生物疫苗", "CRO", "创新药", "精准医疗", "医疗服务", "中药",
                "化学制药", "生物制品", "基因测序", "超级真菌"],
    "消费": ["食品饮料", "白酒", "家用电器", "纺织服饰", "商贸零售", "新零售", "家居用品", "文娱用品",
            "婴童", "养老产业", "体育", "教育", "在线教育", "社会服务", "轻工制造", "新消费",
            "可选消费", "消费", "家电零部件", "智能家居"],
    "金融": ["银行", "证券", "保险", "非银金融", "国有大型银行", "股份制银行", "城商行", "金融"],
    "能源": ["新能源", "煤炭", "石油石化", "电力", "绿色电力", "氢能源", "储能", "锂电池", "电池",
            "光伏设备", "风电设备", "充电桩", "固态电池", "能源", "煤炭开采", "公用事业", "锂矿"],
    "工业制造": ["机械设备", "汽车", "新能源车", "工程机械", "高端装备", "电力设备", "专用设备",
                "通用设备", "自动化设备", "机器人", "人形机器人", "汽车零部件", "汽车服务",
                "汽车热管理", "尾气治理", "特斯拉", "无人驾驶", "智能驾驶", "电网设备", "电机",
                "高端制造", "工业4.0", "工业互联", "低空经济", "通用航空"],
    "材料": ["有色金属", "黄金股", "贵金属", "基础化工", "钢铁", "建筑材料", "稀土永磁", "小金属",
            "工业金属", "材料", "大宗商品", "资源"],
    "军工": ["国防军工", "航天装备", "航空装备", "航海装备", "军工电子", "军民融合", "商业航天",
            "卫星互联网", "航母", "航空机场"],
    "基建地产": ["建筑装饰", "房地产", "房地产开发", "房地产服务", "交通运输", "物流"],
    "环保": ["环保", "环保设备", "环境治理", "垃圾分类", "碳中和", "可控核聚变", "液冷"],
    "传媒": ["传媒", "游戏", "影视", "元宇宙", "超清视频", "数字孪生"],
    "主题": ["国企改革", "一带一路", "中特估", "中字头", "并购重组", "华为", "新兴产业",
            "国家安防", "安全主题", "农牧主题", "农林牧渔", "养殖业", "猪肉", "高端装备"]
};

// 基金选择模态框相关变量
let currentOperation = null;
let selectedFundsForOperation = [];
let allFunds = [];
let currentFilteredFunds = []; // 当前过滤后的基金列表

// 打开基金选择模态框
async function openFundSelectionModal(operation) {
    currentOperation = operation;
    selectedFundsForOperation = [];

    // 设置标题
    const titles = {
        'hold': '选择要标记持有的基金',
        'unhold': '选择要取消持有的基金',
        'sector': '选择要标注板块的基金',
        'unsector': '选择要删除板块的基金',
        'delete': '选择要删除的基金'
    };
    document.getElementById('fundSelectionTitle').textContent = titles[operation] || '选择基金';

    // 获取所有基金列表
    try {
        const response = await fetch('/api/fund/data');
        const fundMap = await response.json();
        allFunds = Object.entries(fundMap).map(([code, data]) => ({
            code,
            name: data.fund_name,
            is_hold: data.is_hold,
            sectors: data.sectors || []
        }));

        // 根据操作类型过滤基金列表
        let filteredFunds = allFunds;
        switch (operation) {
            case 'hold':
                // 标记持有：只显示未持有的基金
                filteredFunds = allFunds.filter(fund => !fund.is_hold);
                break;
            case 'unhold':
                // 取消持有：只显示已持有的基金
                filteredFunds = allFunds.filter(fund => fund.is_hold);
                break;
            case 'unsector':
                // 删除板块：只显示有板块标记的基金
                filteredFunds = allFunds.filter(fund => fund.sectors && fund.sectors.length > 0);
                break;
            case 'sector':
            case 'delete':
            default:
                // 标注板块、删除基金：显示所有基金
                filteredFunds = allFunds;
                break;
        }

        // 保存当前过滤后的列表，供搜索使用
        currentFilteredFunds = filteredFunds;

        // 渲染基金列表
        renderFundSelectionList(filteredFunds);

        // 显示模态框
        document.getElementById('fundSelectionModal').classList.add('active');
    } catch (e) {
        alert('获取基金列表失败: ' + e.message);
    }
}

// 渲染基金选择列表
function renderFundSelectionList(funds) {
    const listContainer = document.getElementById('fundSelectionList');
    listContainer.innerHTML = funds.map(fund => `
        <div class="sector-item" style="text-align: left; padding: 12px; margin-bottom: 8px; cursor: pointer; display: flex; align-items: center; gap: 10px;"
             onclick="toggleFundSelection('${fund.code}', this)">
            <input type="checkbox" class="fund-selection-checkbox" data-code="${fund.code}"
                   style="width: 18px; height: 18px; cursor: pointer;" onclick="event.stopPropagation();">
            <div style="flex: 1;">
                <div style="font-weight: 600;">${fund.code} - ${fund.name}</div>
                ${fund.is_hold ? '<span style="color: #667eea; font-size: 12px;">⭐ 持有</span>' : ''}
                ${fund.sectors && fund.sectors.length > 0 ? `<span style="color: #8b949e; font-size: 12px;"> 🏷️ ${fund.sectors.join(', ')}</span>` : ''}
            </div>
        </div>
    `).join('');
}

// 切换基金选择状态
function toggleFundSelection(code, element) {
    const checkbox = element.querySelector('.fund-selection-checkbox');
    checkbox.checked = !checkbox.checked;

    if (checkbox.checked) {
        if (!selectedFundsForOperation.includes(code)) {
            selectedFundsForOperation.push(code);
        }
        element.style.backgroundColor = 'rgba(102, 126, 234, 0.2)';
    } else {
        selectedFundsForOperation = selectedFundsForOperation.filter(c => c !== code);
        element.style.backgroundColor = '';
    }
}

// 关闭基金选择模态框
function closeFundSelectionModal() {
    document.getElementById('fundSelectionModal').classList.remove('active');
    currentOperation = null;
    selectedFundsForOperation = [];
}

// 确认基金选择
async function confirmFundSelection() {
    if (selectedFundsForOperation.length === 0) {
        alert('请至少选择一个基金');
        return;
    }

    // 根据操作类型执行相应的操作
    switch (currentOperation) {
        case 'hold':
            await markHold(selectedFundsForOperation);
            break;
        case 'unhold':
            await unmarkHold(selectedFundsForOperation);
            break;
        case 'sector':
            const selectedCodes = selectedFundsForOperation; // 先保存选中的基金代码
            closeFundSelectionModal();
            openSectorModal(selectedCodes);
            return; // 不关闭，等待板块选择
        case 'unsector':
            await removeSector(selectedFundsForOperation);
            break;
        case 'delete':
            await deleteFunds(selectedFundsForOperation);
            break;
    }

    closeFundSelectionModal();
}

// 基金选择搜索
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('fundSelectionSearch');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            const keyword = this.value.toLowerCase();
            // 在当前过滤后的列表中搜索，而不是在所有基金中搜索
            const filtered = currentFilteredFunds.filter(fund =>
                fund.code.includes(keyword) || fund.name.toLowerCase().includes(keyword)
            );
            renderFundSelectionList(filtered);
        });
    }
});

// 确认对话框相关函数
let confirmCallback = null;

function showConfirmDialog(title, message, onConfirm) {
    document.getElementById('confirmTitle').textContent = title;
    document.getElementById('confirmMessage').textContent = message;
    document.getElementById('confirmDialog').classList.add('active');
    confirmCallback = onConfirm;
}

function closeConfirmDialog() {
    document.getElementById('confirmDialog').classList.remove('active');
    confirmCallback = null;
}

// 确认对话框按钮事件 - confirmBtn 只在 portfolio 页面存在
const confirmBtn = document.getElementById('confirmBtn');
if (confirmBtn) {
    confirmBtn.addEventListener('click', function() {
        if (confirmCallback) {
            confirmCallback();
        }
        closeConfirmDialog();
    });
}

// 添加基金
async function addFunds() {
    const input = document.getElementById('fundCodesInput');
    const codes = input.value.trim();
    if (!codes) {
        alert('请输入基金代码');
        return;
    }

    try {
        const response = await fetch('/api/fund/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ codes })
        });
        const result = await response.json();
        if (result.success) {
            alert(result.message);
            location.reload();
        } else {
            alert(result.message);
        }
    } catch (e) {
        alert('操作失败: ' + e.message);
    }
}

// 批量回填成立日期
async function backfillEstablishmentDates() {
    const confirmed = window.confirm('将为当前账户所有“成立日期缺失”的基金尝试自动补齐，是否继续？');
    if (!confirmed) return;

    try {
        const response = await fetch('/api/fund/backfill-establishment-dates', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const result = await response.json();

        if (!result || !result.success) {
            const message = (result && result.message) ? result.message : '回填失败';
            if (typeof window.showSimpleMessage === 'function') {
                window.showSimpleMessage(message, 'error');
            } else {
                alert(message);
            }
            return;
        }

        const summary = `回填完成：缺失${result.missing || 0}，补齐${result.updated || 0}，失败${result.failed || 0}`;
        if (typeof window.showSimpleMessage === 'function') {
            window.showSimpleMessage(summary, 'success');
        } else {
            alert(summary);
        }

        // 回填仅更新元数据，无需整页重载，直接刷新基金表格即可
        if (typeof fetchPortfolioData === 'function') {
            fetchPortfolioData().catch(() => {});
        }
    } catch (e) {
        const message = '回填失败: ' + (e?.message || e);
        if (typeof window.showSimpleMessage === 'function') {
            window.showSimpleMessage(message, 'error');
        } else {
            alert(message);
        }
    }
}

// 删除基金
async function deleteFunds(codes) {
    showConfirmDialog(
        '删除基金',
        `确定要删除 ${codes.length} 只基金吗？`,
        async () => {
            try {
                const response = await fetch('/api/fund/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ codes: codes.join(',') })
                });
                const result = await response.json();
                if (result.success) {
                    alert(result.message);
                    location.reload();
                } else {
                    alert(result.message);
                }
            } catch (e) {
                alert('操作失败: ' + e.message);
            }
        }
    );
}

// 标记持有
async function markHold(codes) {
    showConfirmDialog(
        '标记持有',
        `确定要标记 ${codes.length} 只基金为持有吗？`,
        async () => {
            try {
                const response = await fetch('/api/fund/hold', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ codes: codes.join(','), hold: true })
                });
                const result = await response.json();
                if (result.success) {
                    alert(result.message);
                    location.reload();
                } else {
                    alert(result.message);
                }
            } catch (e) {
                alert('操作失败: ' + e.message);
            }
        }
    );
}

// 取消持有
async function unmarkHold(codes) {
    showConfirmDialog(
        '取消持有',
        `确定要取消 ${codes.length} 只基金的持有标记吗？`,
        async () => {
            try {
                const response = await fetch('/api/fund/hold', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ codes: codes.join(','), hold: false })
                });
                const result = await response.json();
                if (result.success) {
                    alert(result.message);
                    location.reload();
                } else {
                    alert(result.message);
                }
            } catch (e) {
                alert('操作失败: ' + e.message);
            }
        }
    );
}

// 打开板块选择模态框（用于标注板块）
let selectedCodesForSector = [];

function openSectorModal(codes) {
    selectedCodesForSector = codes;
    document.getElementById('sectorModal').classList.add('active');
    renderSectorCategories();
}

// 删除板块标记
async function removeSector(codes) {
    showConfirmDialog(
        '删除板块标记',
        `确定要删除 ${codes.length} 只基金的板块标记吗？`,
        async () => {
            try {
                const response = await fetch('/api/fund/sector/remove', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ codes: codes.join(',') })
                });
                const result = await response.json();
                if (result.success) {
                    alert(result.message);
                    location.reload();
                } else {
                    alert(result.message);
                }
            } catch (e) {
                alert('操作失败: ' + e.message);
            }
        }
    );
}

// 取消持有
async function unmarkHold() {
    const codes = selectedFundsForOperation;
    if (codes.length === 0) {
        alert('请先选择要取消持有的基金');
        return;
    }

    showConfirmDialog(
        '取消持有',
        `确定要取消 ${codes.length} 只基金的持有标记吗？`,
        async () => {
            try {
                const response = await fetch('/api/fund/hold', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ codes: codes.join(','), hold: false })
                });
                const result = await response.json();
                if (result.success) {
                    alert(result.message);
                    location.reload();
                } else {
                    alert(result.message);
                }
            } catch (e) {
                alert('操作失败: ' + e.message);
            }
        }
    );
}

// 板块选择相关
let selectedSectors = [];

function renderSectorCategories() {
    // 生成板块分类HTML
    const container = document.getElementById('sectorCategories');
    container.innerHTML = '';

    for (const [category, sectors] of Object.entries(SECTOR_CATEGORIES)) {
        const categoryDiv = document.createElement('div');
        categoryDiv.className = 'sector-category';

        const header = document.createElement('div');
        header.className = 'sector-category-header';
        header.innerHTML = `<span>${category}</span><span>▼</span>`;
        header.onclick = () => {
            const items = categoryDiv.querySelector('.sector-items');
            items.style.display = items.style.display === 'none' ? 'grid' : 'none';
        };

        const itemsDiv = document.createElement('div');
        itemsDiv.className = 'sector-items';

        sectors.forEach(sector => {
            const item = document.createElement('div');
            item.className = 'sector-item';
            item.textContent = sector;
            item.onclick = () => {
                item.classList.toggle('selected');
                if (item.classList.contains('selected')) {
                    if (!selectedSectors.includes(sector)) {
                        selectedSectors.push(sector);
                    }
                } else {
                    selectedSectors = selectedSectors.filter(s => s !== sector);
                }
            };
            itemsDiv.appendChild(item);
        });

        categoryDiv.appendChild(header);
        categoryDiv.appendChild(itemsDiv);
        container.appendChild(categoryDiv);
    }

    selectedSectors = [];
    document.getElementById('sectorModal').classList.add('active');
}

function closeSectorModal() {
    document.getElementById('sectorModal').classList.remove('active');
    selectedSectors = [];
}

async function confirmSector() {
    if (selectedCodesForSector.length === 0) {
        alert('请先选择基金');
        closeSectorModal();
        return;
    }
    if (selectedSectors.length === 0) {
        alert('请至少选择一个板块');
        return;
    }

    try {
        const response = await fetch('/api/fund/sector', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ codes: selectedCodesForSector.join(','), sectors: selectedSectors })
        });
        const result = await response.json();
        closeSectorModal();
        if (result.success) {
            alert(result.message);
            location.reload();
        } else {
            alert(result.message);
        }
    } catch (e) {
        closeSectorModal();
        alert('操作失败: ' + e.message);
    }
}

// 板块搜索功能
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('sectorSearch');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            const keyword = this.value.toLowerCase();
            const categories = document.querySelectorAll('.sector-category');

            categories.forEach(category => {
                const items = category.querySelectorAll('.sector-item');
                let hasVisible = false;

                items.forEach(item => {
                    const text = item.textContent.toLowerCase();
                    if (text.includes(keyword)) {
                        item.style.display = 'block';
                        hasVisible = true;
                    } else {
                        item.style.display = 'none';
                    }
                });

                category.style.display = hasVisible || keyword === '' ? 'block' : 'none';
            });
        });
    }

    // ==================== 新增功能：份额管理和文件操作 ====================

    // 更新基金份额
    window.updateShares = async function(fundCode, shares) {
        if (!fundCode) {
            alert('基金代码无效');
            return;
        }

        try {
            const sharesValue = parseFloat(shares) || 0;
            const response = await fetch('/api/fund/shares', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code: fundCode, shares: sharesValue })
            });
            const result = await response.json();
            if (result.success) {
                // 更新成功后重新计算持仓统计
                calculatePositionSummary();
                // 可选：显示成功提示
                const input = document.getElementById('shares_' + fundCode);
                if (input) {
                    input.style.borderColor = '#4CAF50';
                    setTimeout(() => {
                        input.style.borderColor = '#ddd';
                    }, 1000);
                }
            } else {
                alert(result.message);
            }
        } catch (e) {
            alert('更新份额失败: ' + e.message);
        }
    };

    // 下载fund_map.json
    window.downloadFundMap = function() {
        window.location.href = '/api/fund/download';
    };

    window.clearAllFundTransactions = async function() {
        try {
            window.location.href = '/api/fund/transactions/download-all';

            const confirmText = '清空全部交易';
            const inputText = window.prompt(
                '危险操作：将清空全部基金交易记录，并将所有基金持仓重置为0。\n已开始下载全量交易备份。\n\n请输入“清空全部交易”以确认：',
                ''
            );
            if (inputText === null) {
                return;
            }

            const response = await fetch('/api/fund/transactions/clear-all', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ confirm_text: inputText })
            });
            const result = await response.json();
            if (!result.success) {
                window.showSimpleMessage(result.message || '清空失败', 'error');
                return;
            }

            window.fundSharesData = {};
            document.querySelectorAll('.fund-hold-star').forEach((star) => {
                star.textContent = '☆';
                star.dataset.hold = '0';
            });

            window.showSimpleMessage(result.message || '清空成功', 'success');

            if (currentTransactionFundCode && typeof window.loadFundTransactions === 'function') {
                await window.loadFundTransactions();
            }
            if (typeof fetchPortfolioData === 'function') {
                await fetchPortfolioData();
            } else {
                location.reload();
            }
        } catch (e) {
            window.showSimpleMessage('清空失败: ' + (e?.message || e), 'error');
        }
    };

    window.clearFundTransactionsDanger = async function() {
        const defaultValue = currentTransactionFundCode || '';
        const inputText = window.prompt(
            '危险操作：请输入 6 位基金代码以清空该基金交易记录，或输入“全部”清空全部交易记录。\n\n可输入示例：000001 / 全部',
            defaultValue
        );
        if (inputText === null) {
            return;
        }
        const normalized = String(inputText || '').trim();
        if (normalized === '全部') {
            await window.clearAllFundTransactions();
            return;
        }
        if (!/^\d{6}$/.test(normalized)) {
            window.showSimpleMessage('请输入 6 位基金代码，或输入“全部”', 'info');
            return;
        }
        await window.clearFundTransactionsByCode(normalized);
    };

    // 上传fund_map.json
    window.uploadFundMap = async function(file) {
        if (!file) {
            alert('请选择文件');
            return;
        }

        if (!file.name.endsWith('.json')) {
            alert('只支持JSON文件');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/api/fund/upload', {
                method: 'POST',
                body: formData
            });
            const result = await response.json();
            if (result.success) {
                alert(result.message);
                location.reload();
            } else {
                alert(result.message);
            }
        } catch (e) {
            alert('上传失败: ' + e.message);
        }
    };

    // 上传交易记录Excel
    window.uploadTransactionRecords = async function(file) {
        if (!file) {
            alert('请选择文件');
            return;
        }

        if (!file.name.toLowerCase().endsWith('.xlsx')) {
            alert('仅支持 .xlsx 格式Excel文件');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);
        if (typeof window.showTaskProgress === 'function') {
            window.showTaskProgress('交易记录导入中', '准备上传文件...', 0, '已处理 0/0');
        }

        try {
            const uploadResult = await new Promise((resolve, reject) => {
                const xhr = new XMLHttpRequest();
                xhr.open('POST', '/api/fund/transactions/import', true);
                xhr.responseType = 'json';

                xhr.upload.onloadstart = function() {
                    if (typeof window.updateTaskProgress === 'function') {
                        window.updateTaskProgress('交易记录导入中', '开始上传文件...', 5, '已处理 0/0');
                    }
                };

                xhr.upload.onprogress = function(event) {
                    if (typeof window.updateTaskProgress !== 'function') return;
                    if (event.lengthComputable && event.total > 0) {
                        const uploadPercent = Math.min(75, Math.round((event.loaded / event.total) * 75));
                        window.updateTaskProgress('交易记录导入中', '正在上传文件...', uploadPercent, '已处理 0/0');
                    } else {
                        window.updateTaskProgress('交易记录导入中', '正在上传文件...', 40, '已处理 0/0');
                    }
                };

                xhr.upload.onload = function() {
                    if (typeof window.updateTaskProgress === 'function') {
                        window.updateTaskProgress('交易记录导入中', '文件上传完成，服务器处理中...', 80, '已处理 0/0');
                    }
                };

                xhr.onerror = function() {
                    reject(new Error('网络异常，上传失败'));
                };

                xhr.onload = function() {
                    if (xhr.status < 200 || xhr.status >= 300) {
                        reject(new Error(`导入请求失败: ${xhr.status}`));
                        return;
                    }
                    const responseData = xhr.response || JSON.parse(xhr.responseText || '{}');
                    resolve(responseData);
                };

                xhr.send(formData);
            });

            if (!uploadResult || !uploadResult.success || !uploadResult.job_id) {
                throw new Error(uploadResult?.message || '导入任务创建失败');
            }

            const result = await new Promise((resolve, reject) => {
                let stopped = false;
                const poll = async () => {
                    if (stopped) return;
                    try {
                        const response = await fetch(`/api/fund/transactions/import-progress?job_id=${encodeURIComponent(uploadResult.job_id)}`, {
                            cache: 'no-store'
                        });
                        const progressResult = await response.json();
                        if (!progressResult.success || !progressResult.job) {
                            throw new Error(progressResult.message || '导入进度获取失败');
                        }

                        const job = progressResult.job || {};
                        const processedCount = Number(job.processed_count || 0);
                        const totalCount = Number(job.total_count || 0);
                        const statsText = `已处理 ${processedCount}/${totalCount || 0}`;

                        if (typeof window.updateTaskProgress === 'function') {
                            window.updateTaskProgress(
                                job.title || '交易记录导入中',
                                job.detail || '服务器处理中...',
                                Number(job.percent || 0),
                                statsText
                            );
                        }

                        if (job.done) {
                            stopped = true;
                            resolve(job);
                            return;
                        }

                        setTimeout(poll, 800);
                    } catch (error) {
                        stopped = true;
                        reject(error);
                    }
                };
                poll();
            });

            const duplicateCount = Number(result.duplicate_count || 0);
            const warningMessages = Array.isArray(result.warning_messages) ? result.warning_messages : [];
            if (!result.success) {
                if (typeof window.hideTaskProgress === 'function') {
                    window.hideTaskProgress();
                }
                const failedRows = Array.isArray(result.failed_rows) ? result.failed_rows : [];
                const warningText = warningMessages.length > 0
                    ? '\n告警信息:\n' + warningMessages.slice(0, 10).join('\n')
                    : '';
                const detailText = failedRows.length > 0
                    ? '\n失败明细:\n' + failedRows.slice(0, 10).map(item => `第${item.row}行: ${item.reason}`).join('\n')
                    : '';
                const duplicateText = duplicateCount > 0 ? `\n重复订单：${duplicateCount}条` : '';
                alert((result.message || '导入失败') + duplicateText + warningText + detailText);
                return;
            }

            if (typeof window.updateTaskProgress === 'function') {
                window.updateTaskProgress(
                    '交易记录导入中',
                    '导入完成，正在刷新页面数据...',
                    100,
                    `已处理 ${Number(result.processed_count || 0)}/${Number(result.total_count || 0)}`
                );
            }

            const failedRows = Array.isArray(result.failed_rows) ? result.failed_rows : [];
            const warningText = warningMessages.length > 0
                ? '\n告警信息:\n' + warningMessages.slice(0, 10).join('\n')
                : '';
            const detailText = failedRows.length > 0
                ? '\n失败明细:\n' + failedRows.slice(0, 10).map(item => `第${item.row}行: ${item.reason}`).join('\n')
                : '';
            const duplicateText = duplicateCount > 0 ? `\n重复订单：${duplicateCount}条` : '';
            alert((result.message || '导入成功') + duplicateText + warningText + detailText);

            if (typeof fetchPortfolioData === 'function') {
                await fetchPortfolioData();
            } else {
                location.reload();
            }

            if (currentTransactionFundCode && typeof window.loadFundTransactions === 'function') {
                await window.loadFundTransactions();
            }
            if (typeof window.hideTaskProgress === 'function') {
                setTimeout(() => window.hideTaskProgress(), 400);
            }
        } catch (e) {
            if (typeof window.hideTaskProgress === 'function') {
                window.hideTaskProgress();
            }
            alert('导入交易记录失败: ' + (e?.message || e));
        } finally {
            const tradeFileInput = document.getElementById('uploadTradeFile');
            if (tradeFileInput) {
                tradeFileInput.value = '';
            }
        }
    };

    window.summaryPanelsExpanded = false;
    window.summaryPanelsHasData = false;
    window.summaryPanelsHasDetails = false;

    function formatDateKey(date) {
        const y = date.getFullYear();
        const m = String(date.getMonth() + 1).padStart(2, '0');
        const d = String(date.getDate()).padStart(2, '0');
        return `${y}-${m}-${d}`;
    }

    function applyDailyGainLabels(estimatedDayLabel, actualDayLabel) {
        const estimatedGainLabel = document.getElementById('estimatedGainLabel');
        const actualGainLabel = document.getElementById('actualGainLabel');
        const toolbarEstimatedGainLabel = document.getElementById('toolbarEstimatedGainLabel');

        if (estimatedGainLabel) {
            estimatedGainLabel.textContent = `${estimatedDayLabel}预估收益`;
        }
        if (actualGainLabel) {
            actualGainLabel.textContent = `${actualDayLabel}实际收益`;
        }
        if (toolbarEstimatedGainLabel) {
            toolbarEstimatedGainLabel.textContent = `${estimatedDayLabel}收益估计`;
        }
    }

    function updateActualGainNote(noteText = '') {
        const actualGainNote = document.getElementById('actualGainNote');
        if (!actualGainNote) return;
        if (noteText) {
            actualGainNote.textContent = noteText;
            actualGainNote.style.display = 'block';
        } else {
            actualGainNote.textContent = '';
            actualGainNote.style.display = 'none';
        }
    }

    function updateEstimatedGainNote(noteText = '') {
        const estimatedGainNote = document.getElementById('estimatedGainNote');
        if (!estimatedGainNote) return;
        if (noteText) {
            estimatedGainNote.textContent = noteText;
            estimatedGainNote.style.display = 'block';
        } else {
            estimatedGainNote.textContent = '';
            estimatedGainNote.style.display = 'none';
        }
    }

    function getDayLabelFromDateKey(dateKey) {
        if (!dateKey || !/^\d{4}-\d{2}-\d{2}$/.test(dateKey)) return '--';
        const month = Number(dateKey.slice(5, 7));
        const day = Number(dateKey.slice(8, 10));
        if (!Number.isFinite(month) || !Number.isFinite(day)) return '--';
        return `${month}月${day}日`;
    }

    function getEstimateSnapshot() {
        try {
            const raw = localStorage.getItem('portfolioEstimateSnapshot');
            if (!raw) return null;
            const parsed = JSON.parse(raw);
            if (!parsed || typeof parsed !== 'object') return null;
            return parsed;
        } catch (_) {
            return null;
        }
    }

    function saveEstimateSnapshot(snapshot) {
        try {
            localStorage.setItem('portfolioEstimateSnapshot', JSON.stringify(snapshot));
        } catch (_) {
            // ignore quota/private mode errors
        }
    }

    function applySummaryPanelsVisibility() {
        const summaryDiv = document.getElementById('positionSummary');
        const fundDetailsDiv = document.getElementById('fundDetailsSummary');
        const shouldShowSummary = window.summaryPanelsExpanded && window.summaryPanelsHasData;
        const shouldShowDetails = window.summaryPanelsExpanded && window.summaryPanelsHasDetails;

        if (summaryDiv) {
            summaryDiv.style.display = shouldShowSummary ? 'block' : 'none';
        }
        if (fundDetailsDiv) {
            fundDetailsDiv.style.display = shouldShowDetails ? 'block' : 'none';
        }
    }

    function updateToolbarEstimateTitle(estimatedDayLabel, actualDayLabel) {
        const toolbarEstimatedGainWrap = document.getElementById('toolbarEstimatedGainWrap');
        if (!toolbarEstimatedGainWrap) return;
        toolbarEstimatedGainWrap.title = `预估绑定：${estimatedDayLabel}；实际绑定：${actualDayLabel}。点击收益估计值展开/折叠明细`;
    }

    function initSummaryPanelsToggleByToolbarEstimate() {
        const toolbarEstimatedGainEl = document.getElementById('toolbarEstimatedGain');
        const toolbarEstimatedGainPctEl = document.getElementById('toolbarEstimatedGainPct');
        const toolbarEstimatedGainWrap = document.getElementById('toolbarEstimatedGainWrap');
        if (!toolbarEstimatedGainEl || !toolbarEstimatedGainPctEl) return;
        if (toolbarEstimatedGainEl.dataset.summaryToggleBound === '1') return;

        const toggle = () => {
            if (!window.summaryPanelsHasData) {
                return;
            }
            window.summaryPanelsExpanded = !window.summaryPanelsExpanded;
            applySummaryPanelsVisibility();
        };

        [toolbarEstimatedGainEl, toolbarEstimatedGainPctEl].forEach((node) => {
            node.style.cursor = 'pointer';
            node.style.textDecoration = 'underline';
            node.style.textDecorationStyle = 'dotted';
            node.title = '点击展开/折叠持仓统计与涨跌明细';
            node.addEventListener('click', toggle);
        });

        if (toolbarEstimatedGainWrap) {
            toolbarEstimatedGainWrap.title = '点击收益估计值展开/折叠明细';
        }

        toolbarEstimatedGainEl.dataset.summaryToggleBound = '1';
    }

    // 计算并显示持仓统计
    function calculatePositionSummary() {
        let totalValue = 0;
        let estimatedGain = 0;
        let actualGain = 0;
        let settledValue = 0;
        let freshEstimateFundCount = 0;

        const parseFirstNumber = (text, opts = {}) => {
            const { isPercent = false } = opts;
            const raw = String(text || '').replace(/,/g, '');
            const pattern = isPercent
                ? /[-+]?\d+(?:\.\d+)?(?=%)/
                : /[-+]?\d+(?:\.\d+)?/;
            const match = raw.match(pattern);
            if (!match) return null;
            const value = Number(match[0]);
            return Number.isFinite(value) ? value : null;
        };

        const countHeldFunds = () => {
            let heldCount = 0;
            if (!window.fundSharesData) return heldCount;
            for (const code in window.fundSharesData) {
                if (window.fundSharesData[code] > 0) {
                    heldCount++;
                }
            }
            return heldCount;
        };

        const todayDateKey = formatDateKey(new Date());

        const heldFundRowsData = [];
        // 存储每个基金的详细涨跌信息
        const fundDetailsData = [];

        // 遍历所有基金行
        const fundRows = document.querySelectorAll('.style-table tbody tr');
        fundRows.forEach(row => {
            const cells = row.querySelectorAll('td');
            if (cells.length < 9) return;

            // 兼容当前表格结构：优先使用 data-code，再回退到第二列纯代码
            const nameNode = row.querySelector('.fund-name-cell[data-code]');
            const fundCode = String(nameNode?.dataset?.code || cells[1]?.textContent || '').trim();
            if (!fundCode) return;

            // 从全局数据获取份额
            const shares = (window.fundSharesData && window.fundSharesData[fundCode]) || 0;
            if (shares <= 0) return;

            try {
                // 获取基金名称（第三列，索引2），优先保留 fund-name-cell 的 innerHTML
                const fundName = nameNode ? nameNode.innerHTML.trim() : cells[2].innerHTML.trim();

                const positionNode = row.querySelector(`.fund-position-amount-cell[data-code="${fundCode}"]`);
                const estimateNode = row.querySelector(`.fund-estimate-cell[data-code="${fundCode}"]`);
                if (!positionNode) return;

                const positionValue = parseFirstNumber(positionNode.textContent);
                const estimatedGrowth = parseFirstNumber(estimateNode.textContent, { isPercent: true });
                const estimateDate = String(estimateNode?.dataset?.estimateDate || '').trim();
                if (positionValue == null || positionValue <= 0) return;

                // 日涨幅节点仅包含涨幅值，净值日期在同一td副文本中；
                // 因此日期需从整格文本提取，避免实际收益无法按当日净值更新。
                const dayGrowthNode = row.querySelector(`.fund-daygrowth-cell[data-code="${fundCode}"]`);
                const dayGrowthCell = dayGrowthNode?.closest('td') || cells[5];
                const dayGrowthFullText = String(dayGrowthCell?.textContent || dayGrowthNode?.textContent || '').trim();
                const fullDateMatch = dayGrowthFullText.match(/(\d{4}-\d{2}-\d{2})/);
                const shortDateMatch = dayGrowthFullText.match(/(\d{2}-\d{2})/);
                let netValueDate = fullDateMatch ? fullDateMatch[1] : (shortDateMatch ? shortDateMatch[1] : '');

                // 处理净值日期格式：API可能返回"MM-DD"或"YYYY-MM-DD"
                // 如果是"MM-DD"格式，添加当前年份
                if (netValueDate.length === 5) {  // 格式为"MM-DD"
                    const currentYear = new Date().getFullYear();
                    netValueDate = `${currentYear}-${netValueDate}`;
                }

                // 解析日涨幅 (第五列，索引4)
                const dayGrowthText = String(dayGrowthNode?.textContent || dayGrowthCell?.textContent || '').trim();
                const dayGrowth = parseFirstNumber(dayGrowthText, { isPercent: true });

                totalValue += positionValue;
                const fundEstimatedGain = estimatedGrowth == null ? 0 : (positionValue * estimatedGrowth / 100);
                if (estimatedGrowth != null && /^\d{4}-\d{2}-\d{2}$/.test(estimateDate) && estimateDate === todayDateKey) {
                    freshEstimateFundCount += 1;
                }
                heldFundRowsData.push({
                    fundCode,
                    positionValue,
                    estimatedGrowth,
                    estimateDate,
                    dayGrowth,
                    netValueDate,
                    fundEstimatedGain,
                });

                // 获取板块数据
                const sectors = window.fundSectorsData && window.fundSectorsData[fundCode] ? window.fundSectorsData[fundCode] : [];

                // 收集每个基金的详细涨跌信息
                fundDetailsData.push({
                    code: fundCode,
                    name: fundName,
                    shares: shares,
                    positionValue: positionValue,
                    estimatedGain: fundEstimatedGain,
                    estimatedGainPct: estimatedGrowth,
                    actualGain: 0,
                    actualGainPct: 0,
                    sectors: sectors
                });
            } catch (e) {
                console.warn('解析基金数据失败:', fundCode, e);
            }
        });

        const totalHeldFundCount = heldFundRowsData.length;
        const actualTargetDateKey = heldFundRowsData
            .filter(item => Number.isFinite(item.dayGrowth) && /^\d{4}-\d{2}-\d{2}$/.test(item.netValueDate))
            .map(item => item.netValueDate)
            .sort()
            .slice(-1)[0] || '';
        let actualUpdatedFundCount = 0;

        for (const rowItem of heldFundRowsData) {
            estimatedGain += rowItem.fundEstimatedGain;
            const isActualTargetDate = actualTargetDateKey && rowItem.netValueDate === actualTargetDateKey;
            if (isActualTargetDate && Number.isFinite(rowItem.dayGrowth)) {
                const rowActualGain = rowItem.positionValue * rowItem.dayGrowth / 100;
                actualGain += rowActualGain;
                settledValue += rowItem.positionValue;
                actualUpdatedFundCount += 1;
            }
        }

        for (const fund of fundDetailsData) {
            const rowData = heldFundRowsData.find(item => item.fundCode === fund.code);
            const isActualTargetDate = !!rowData && !!actualTargetDateKey && rowData.netValueDate === actualTargetDateKey;
            if (isActualTargetDate && Number.isFinite(rowData.dayGrowth)) {
                fund.actualGain = fund.positionValue * rowData.dayGrowth / 100;
                fund.actualGainPct = rowData.dayGrowth;
            } else {
                fund.actualGain = 0;
                fund.actualGainPct = 0;
            }
        }

        const latestEstimatedDateKeyFromRows = heldFundRowsData
            .filter(item => item.estimatedGrowth != null && /^\d{4}-\d{2}-\d{2}$/.test(item.estimateDate))
            .map(item => item.estimateDate)
            .sort()
            .slice(-1)[0] || '';
        const previousSnapshot = getEstimateSnapshot();

        const now = new Date();
        const isBefore0930 = now.getHours() < 9 || (now.getHours() === 9 && now.getMinutes() < 30);
        const isBefore15 = now.getHours() < 15;
        const hasFreshEstimateData = latestEstimatedDateKeyFromRows === todayDateKey && freshEstimateFundCount > 0;
        const shouldFreezeGainRefresh = isBefore15 && totalHeldFundCount > 0 && !hasFreshEstimateData;
        const previousAvailableDateKey =
            (previousSnapshot && /^\d{4}-\d{2}-\d{2}$/.test(previousSnapshot.dateKey || '') ? previousSnapshot.dateKey : '')
            || latestEstimatedDateKeyFromRows
            || '';

        const shouldKeepPreviousEstimateDate = isBefore0930 || latestEstimatedDateKeyFromRows !== todayDateKey;
        const displayDateKey = shouldKeepPreviousEstimateDate
            ? (previousAvailableDateKey || todayDateKey)
            : todayDateKey;
        const displayDayLabel = getDayLabelFromDateKey(displayDateKey);
        const actualDisplayDateKey = actualTargetDateKey || displayDateKey;
        const actualDisplayDayLabel = getDayLabelFromDateKey(actualDisplayDateKey);
        applyDailyGainLabels(displayDayLabel, actualDisplayDayLabel);
        updateToolbarEstimateTitle(displayDayLabel, actualDisplayDayLabel);

        if (totalHeldFundCount <= 0) {
            updateEstimatedGainNote('');
            updateActualGainNote('');
        } else {
            if (displayDateKey !== todayDateKey) {
                updateEstimatedGainNote(`预估按${displayDayLabel}估值日期展示`);
            } else {
                updateEstimatedGainNote('');
            }
        }

        if (totalHeldFundCount <= 0) {
            updateActualGainNote('');
        } else if (!actualTargetDateKey) {
            updateActualGainNote(`实际收益待更新（0/${totalHeldFundCount}）`);
        } else if (actualDisplayDateKey !== todayDateKey) {
            updateActualGainNote(`实际按${actualDisplayDayLabel}交易日期展示（${actualUpdatedFundCount}/${totalHeldFundCount}）`);
        } else if (actualUpdatedFundCount < totalHeldFundCount) {
            updateActualGainNote(`实际收益部分更新（${actualUpdatedFundCount}/${totalHeldFundCount}），按已更新基金统计`);
        } else {
            updateActualGainNote('');
        }

        // 保存基金明细数据到全局变量，供炫耀卡片使用
        window.fundDetailsData = fundDetailsData;
        window.summaryPanelsHasData = totalValue > 0;
        window.summaryPanelsHasDetails = fundDetailsData.length > 0;
        applySummaryPanelsVisibility();
        initSummaryPanelsToggleByToolbarEstimate();
        const estimatedGainPct = totalValue > 0 ? (estimatedGain / totalValue * 100) : 0;
        const actualGainPct = settledValue > 0 ? (actualGain / settledValue * 100) : 0;

        if (!shouldFreezeGainRefresh && totalValue > 0 && freshEstimateFundCount > 0) {
            saveEstimateSnapshot({
                dateKey: displayDateKey,
                totalValue,
                estimatedGain,
                estimatedGainPct,
                actualGain,
                actualGainPct,
                settledValue,
                savedAt: Date.now()
            });
        }

        const displayData = {
            totalValue: shouldFreezeGainRefresh && previousSnapshot
                ? Number(previousSnapshot.totalValue || totalValue)
                : totalValue,
            estimatedGain: shouldFreezeGainRefresh && previousSnapshot
                ? Number(previousSnapshot.estimatedGain || 0)
                : estimatedGain,
            estimatedGainPct: shouldFreezeGainRefresh && previousSnapshot
                ? Number(previousSnapshot.estimatedGainPct || 0)
                : estimatedGainPct,
            actualGain,
            actualGainPct,
            settledValue,
        };

        // 更新持仓基金页面的汇总数据 (始终执行)
        // 更新总持仓金额
        const totalValueEl = document.getElementById('totalValue');
        if (totalValueEl) {
            totalValueEl.className = 'sensitive-value';
            const realValueSpan = totalValueEl.querySelector('.real-value');
            if (realValueSpan) {
                realValueSpan.textContent = '¥' + displayData.totalValue.toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
            }
        }

        // 更新今日预估
        const estimatedGainEl = document.getElementById('estimatedGain');
        const estimatedGainPctEl = document.getElementById('estimatedGainPct');
        if (estimatedGainEl && estimatedGainPctEl) {
            const estGainPct = displayData.estimatedGainPct;
            const estSign = displayData.estimatedGain >= 0 ? '+' : '';
            const estMoneySign = displayData.estimatedGain < 0 ? '-' : '+';
            const sensitiveSpan = estimatedGainEl.querySelector('.sensitive-value');
            if (sensitiveSpan) {
                sensitiveSpan.className = displayData.estimatedGain >= 0 ? 'sensitive-value positive' : 'sensitive-value negative';
            }
            const realValueSpan = estimatedGainEl.querySelector('.real-value');
            if (realValueSpan) {
                realValueSpan.textContent = `${estMoneySign}¥${Math.abs(displayData.estimatedGain).toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            }
            estimatedGainPctEl.textContent = ` (${estSign}${estGainPct.toFixed(2)}%)`;
            estimatedGainPctEl.style.color = displayData.estimatedGain >= 0 ? 'var(--up-color)' : 'var(--down-color)';
        }

        const toolbarEstimatedGainEl = document.getElementById('toolbarEstimatedGain');
        const toolbarEstimatedGainPctEl = document.getElementById('toolbarEstimatedGainPct');
        if (toolbarEstimatedGainEl && toolbarEstimatedGainPctEl) {
            if (displayData.totalValue > 0) {
                const estGainPct = displayData.estimatedGainPct;
                const estSign = displayData.estimatedGain >= 0 ? '+' : '';
                const estMoneySign = displayData.estimatedGain < 0 ? '-' : '+';
                toolbarEstimatedGainEl.textContent = `${estMoneySign}¥${Math.abs(displayData.estimatedGain).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                toolbarEstimatedGainEl.style.color = displayData.estimatedGain >= 0 ? 'var(--up-color)' : 'var(--down-color)';
                toolbarEstimatedGainPctEl.textContent = `${estSign}${estGainPct.toFixed(2)}%`;
                toolbarEstimatedGainPctEl.style.color = displayData.estimatedGain >= 0 ? 'var(--up-color)' : 'var(--down-color)';
            } else {
                toolbarEstimatedGainEl.textContent = '--';
                toolbarEstimatedGainEl.style.color = 'var(--text-main)';
                toolbarEstimatedGainPctEl.textContent = '--';
                toolbarEstimatedGainPctEl.style.color = 'var(--text-dim)';
            }
        }

        // 更新今日实际（统一按今日更新的数据计算）
        const actualGainEl = document.getElementById('actualGain');
        const actualGainPctEl = document.getElementById('actualGainPct');
        if (actualGainEl && actualGainPctEl) {
            if (displayData.settledValue > 0) {
                const actGainPct = displayData.actualGainPct;
                const actSign = displayData.actualGain >= 0 ? '+' : '';
                const actMoneySign = displayData.actualGain < 0 ? '-' : '+';
                const sensitiveSpan = actualGainEl.querySelector('.sensitive-value');
                if (sensitiveSpan) {
                    sensitiveSpan.className = displayData.actualGain >= 0 ? 'sensitive-value positive' : 'sensitive-value negative';
                }
                const realValueSpan = actualGainEl.querySelector('.real-value');
                if (realValueSpan) {
                    realValueSpan.textContent = `${actMoneySign}¥${Math.abs(displayData.actualGain).toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
                }
                actualGainPctEl.textContent = ` (${actSign}${actGainPct.toFixed(2)}%)`;
                actualGainPctEl.style.color = displayData.actualGain >= 0 ? 'var(--up-color)' : 'var(--down-color)';
            } else {
                const sensitiveSpan = actualGainEl.querySelector('.sensitive-value');
                if (sensitiveSpan) {
                    sensitiveSpan.className = 'sensitive-value';
                }
                const realValueSpan = actualGainEl.querySelector('.real-value');
                if (realValueSpan) {
                    realValueSpan.textContent = '¥0.00';
                }
                actualGainPctEl.textContent = ' (+0.00%)';
                actualGainPctEl.style.color = 'var(--text-dim)';
            }
        }

        // 更新持仓数量
        const holdCountEl = document.getElementById('holdCount');
        if (holdCountEl) {
            holdCountEl.textContent = countHeldFunds() + ' 只';
        }

        // 填充分基金明细表格
        const fundDetailsDiv = document.getElementById('fundDetailsSummary');
        if (fundDetailsDiv && fundDetailsData.length > 0) {
            const tableBody = document.getElementById('fundDetailsTableBody');
            if (tableBody) {
                tableBody.innerHTML = fundDetailsData.map(fund => {
                    const hasEstimate = Number.isFinite(fund.estimatedGainPct);
                    const estColor = fund.estimatedGain >= 0 ? 'var(--up-color)' : 'var(--down-color)';
                    const actColor = fund.actualGain >= 0 ? 'var(--up-color)' : 'var(--down-color)';
                    const estSign = fund.estimatedGain >= 0 ? '+' : '';
                    const actSign = fund.actualGain >= 0 ? '+' : '';
                    const estMoneySign = fund.estimatedGain < 0 ? '-' : '+';
                    const actMoneySign = fund.actualGain < 0 ? '-' : '+';
                    // 基金名称中已包含板块标签，不再重复添加
                    return `
                        <tr style="border-bottom: 1px solid var(--border);">
                            <td style="padding: 10px; text-align: center; vertical-align: middle; color: var(--accent); font-weight: 500;">${fund.code}</td>
                            <td style="padding: 10px; text-align: center; vertical-align: middle; color: var(--text-main); white-space: nowrap; min-width: 120px;">${fund.name}</td>
                            <td class="sensitive-value" style="padding: 10px; text-align: center; vertical-align: middle; font-family: var(--font-mono); color: var(--text-main);"><span class="real-value">${fund.shares.toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span><span class="hidden-value">****</span></td>
                            <td class="sensitive-value" style="padding: 10px; text-align: center; vertical-align: middle; font-family: var(--font-mono); font-weight: 600; color: var(--text-main);"><span class="real-value">¥${fund.positionValue.toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span><span class="hidden-value">****</span></td>
                            <td class="sensitive-value" style="padding: 10px; text-align: center; vertical-align: middle; font-family: var(--font-mono); color: ${hasEstimate ? estColor : 'var(--text-dim)'}; font-weight: 500;"><span class="real-value">${hasEstimate ? `${estMoneySign}¥${Math.abs(fund.estimatedGain).toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}` : '--'}</span><span class="hidden-value">****</span></td>
                            <td style="padding: 10px; text-align: center; vertical-align: middle; font-family: var(--font-mono); color: ${hasEstimate ? estColor : 'var(--text-dim)'}; font-weight: 500;">${hasEstimate ? `${estSign}${fund.estimatedGainPct.toFixed(2)}%` : '--'}</td>
                            <td class="sensitive-value" style="padding: 10px; text-align: center; vertical-align: middle; font-family: var(--font-mono); color: ${actColor}; font-weight: 500;"><span class="real-value">${actMoneySign}¥${Math.abs(fund.actualGain).toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span><span class="hidden-value">****</span></td>
                            <td style="padding: 10px; text-align: center; vertical-align: middle; font-family: var(--font-mono); color: ${actColor}; font-weight: 500;">${actSign}${fund.actualGainPct.toFixed(2)}%</td>
                        </tr>
                    `;
                }).join('');
            }
        }

        // Update new summary bar if it exists (sidebar layout)
        const summaryBar = document.getElementById('summaryBar');
        if (summaryBar) {
            const heldCount = countHeldFunds();

            // Update total value
            const summaryTotalValue = document.getElementById('summaryTotalValue');
            if (summaryTotalValue) {
                summaryTotalValue.textContent = '¥' + totalValue.toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
            }

            // Update total change
            const summaryTotalChange = document.getElementById('summaryTotalChange');
            if (summaryTotalChange) {
                const totalPct = displayData.totalValue > 0 ? ((displayData.estimatedGain + displayData.actualGain) / displayData.totalValue * 100) : 0;
                const totalSign = (displayData.estimatedGain + displayData.actualGain) >= 0 ? '+' : '';
                summaryTotalChange.textContent = `${totalSign}${totalPct.toFixed(2)}%`;
                summaryTotalChange.className = 'summary-change ' + ((displayData.estimatedGain + displayData.actualGain) >= 0 ? 'positive' : 'negative');
            }

            // Update estimated gain
            const summaryEstGain = document.getElementById('summaryEstGain');
            if (summaryEstGain) {
                const estMoneySign = displayData.estimatedGain < 0 ? '-' : '+';
                summaryEstGain.textContent = `${estMoneySign}¥${Math.abs(displayData.estimatedGain).toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            }

            // Update estimated change
            const summaryEstChange = document.getElementById('summaryEstChange');
            if (summaryEstChange) {
                const estGainPct = displayData.estimatedGainPct;
                const estSign = displayData.estimatedGain >= 0 ? '+' : '';
                summaryEstChange.textContent = `${estSign}${estGainPct.toFixed(2)}%`;
                summaryEstChange.className = 'summary-change ' + (displayData.estimatedGain >= 0 ? 'positive' : 'negative');
            }

            // Update actual gain
            const summaryActualGain = document.getElementById('summaryActualGain');
            if (summaryActualGain) {
                const actMoneySign = displayData.actualGain < 0 ? '-' : '+';
                summaryActualGain.textContent = `${actMoneySign}¥${Math.abs(displayData.actualGain).toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            }

            // Update actual change
            const summaryActualChange = document.getElementById('summaryActualChange');
            if (summaryActualChange) {
                if (displayData.settledValue > 0) {
                    const actGainPct = displayData.actualGainPct;
                    const actSign = displayData.actualGain >= 0 ? '+' : '';
                    summaryActualChange.textContent = `${actSign}${actGainPct.toFixed(2)}%`;
                    summaryActualChange.className = 'summary-change ' + (displayData.actualGain >= 0 ? 'positive' : 'negative');
                } else {
                    summaryActualChange.textContent = '0.00%';
                    summaryActualChange.className = 'summary-change neutral';
                }
            }

            // Update hold count
            const summaryHoldCount = document.getElementById('summaryHoldCount');
            if (summaryHoldCount) {
                summaryHoldCount.textContent = `${heldCount} 只`;
            }
        }
    }

    // Note: loadSharesData() is called only in portfolio.html, not globally
    // This prevents unnecessary requests to /api/fund/data on other pages

    // 展开/收起基金行详情
    window.toggleFundExpand = function(fundCode) {
        const fundRow = document.querySelector(`.fund-row[data-code="${fundCode}"]`);
        if (fundRow) {
            fundRow.classList.toggle('expanded');
        }
    };

    // 全局暴露其他必要的函数
    window.openFundSelectionModal = openFundSelectionModal;
    window.closeFundSelectionModal = closeFundSelectionModal;
    window.confirmFundSelection = confirmFundSelection;
    window.addFunds = addFunds;
    window.backfillEstablishmentDates = backfillEstablishmentDates;
    window.markHold = markHold;
    window.unmarkHold = unmarkHold;
    window.deleteFunds = deleteFunds;
    window.openSectorModal = openSectorModal;
    window.closeSectorModal = closeSectorModal;
    window.confirmSector = confirmSector;
    window.removeSector = removeSector;

    // ==================== Buy/Sell Actions ====================
    let currentTradeFundCode = null;
    let currentTradeAction = null;
    let currentBackfillFundCode = null;
    let currentBackfillFetchToken = 0;
    let currentBackfillNetValueLoading = false;
    let currentBackfillView = 'trade';
    let currentTransactionFundCode = null;

    function getBackfillActionButtons() {
        return {
            buyBtn: document.getElementById('backfillModalBuyBtn'),
            sellBtn: document.getElementById('backfillModalSellBtn'),
            dividendBtn: document.getElementById('backfillModalDividendBtn'),
        };
    }

    function updateBackfillSubmitButtonsState() {
        const { buyBtn, sellBtn, dividendBtn } = getBackfillActionButtons();
        const netValueInput = document.getElementById('backfillNetValue');
        if (!netValueInput) return;

        const netValue = parseFloat(String(netValueInput.value || '').trim());
        const hasValidNetValue = Number.isFinite(netValue) && netValue > 0;
        const isDividendView = currentBackfillView === 'dividend';
        const shouldDisableBuySell = currentBackfillNetValueLoading || !hasValidNetValue;
        if (buyBtn) buyBtn.disabled = isDividendView || shouldDisableBuySell;
        if (sellBtn) sellBtn.disabled = isDividendView || shouldDisableBuySell;
        if (dividendBtn) dividendBtn.disabled = !isDividendView;
    }

    function setBackfillView(view = 'trade') {
        const isDividendView = view === 'dividend';
        currentBackfillView = isDividendView ? 'dividend' : 'trade';

        if (isDividendView) {
            currentBackfillNetValueLoading = false;
            currentBackfillFetchToken += 1;
        }

        const topGrid = document.getElementById('backfillTopGrid');
        const amountSharesGrid = document.getElementById('backfillAmountSharesGrid');
        const titleEl = document.getElementById('backfillModalTitle');
        const amountLabel = document.getElementById('backfillAmountLabel');
        const amountQuickButtons = document.getElementById('backfillAmountQuickButtons');
        const sharesGroup = document.getElementById('backfillSharesGroup');
        const netValueGroup = document.getElementById('backfillNetValueGroup');
        const feeGroup = document.getElementById('backfillFeeGroup');
        const tradeActions = document.getElementById('backfillTradeActions');
        const tradeViewBtn = document.getElementById('backfillViewTradeBtn');
        const dividendViewBtn = document.getElementById('backfillViewDividendBtn');
        const hint = document.getElementById('backfillNetValueHint');
        const { dividendBtn } = getBackfillActionButtons();

        if (topGrid) {
            topGrid.style.gridTemplateColumns = isDividendView ? '1fr' : 'repeat(2, minmax(0, 1fr))';
        }
        if (amountSharesGrid) {
            amountSharesGrid.style.gridTemplateColumns = isDividendView ? '1fr' : 'repeat(2, minmax(0, 1fr))';
        }

        if (titleEl) {
            titleEl.textContent = isDividendView ? '补录分红' : '补录交易';
        }
        if (amountLabel) {
            amountLabel.textContent = isDividendView ? '分红金额（元）' : '金额（买入，元）';
        }
        if (amountQuickButtons) {
            amountQuickButtons.style.display = isDividendView ? 'none' : 'flex';
        }
        if (sharesGroup) {
            sharesGroup.style.display = isDividendView ? 'none' : '';
        }
        if (netValueGroup) {
            netValueGroup.style.display = isDividendView ? 'none' : '';
        }
        if (feeGroup) {
            feeGroup.style.display = isDividendView ? 'none' : '';
        }
        if (tradeActions) {
            tradeActions.style.display = isDividendView ? 'none' : 'flex';
        }
        if (dividendBtn) {
            dividendBtn.style.display = isDividendView ? '' : 'none';
            dividendBtn.textContent = '补录分红';
        }
        if (tradeViewBtn) {
            tradeViewBtn.className = isDividendView ? 'btn btn-secondary' : 'btn btn-primary';
        }
        if (dividendViewBtn) {
            dividendViewBtn.className = isDividendView ? 'btn btn-primary' : 'btn btn-secondary';
        }
        if (hint) {
            hint.textContent = isDividendView
                ? '分红模式：无需净值和手续费'
                : '选择日期后将尝试自动填充净值（若趋势数据可用）';
            hint.style.color = 'var(--text-dim)';
        }

        updateBackfillSubmitButtonsState();
        updateBackfillSharesPreview();
    }

    window.setBackfillView = setBackfillView;

    function updateBackfillSharesPreview() {
        const amountInput = document.getElementById('backfillAmount');
        const feeInput = document.getElementById('backfillFee');
        const netValueInput = document.getElementById('backfillNetValue');
        const sharesInput = document.getElementById('backfillShares');
        const sharesLabel = document.getElementById('backfillSharesLabel');
        if (!amountInput || !feeInput || !netValueInput || !sharesInput || !sharesLabel) return;

        sharesLabel.textContent = '份额（卖出填写 / 买入参考）';

        const amountText = String(amountInput.value || '').trim();
        const feeText = String(feeInput.value || '').trim();
        const netValue = parseFloat(String(netValueInput.value || '').trim());
        const amount = amountText === '' ? NaN : parseFloat(amountText);
        const fee = feeText === '' ? 0 : parseFloat(feeText);

        // 合并模式：输入金额时自动折算买入参考份额；未输入金额时允许手工输入卖出份额。
        if (amountText !== '') {
            sharesInput.placeholder = '买入金额自动折算，仅供查验';
            if (!Number.isFinite(amount) || amount <= 0 || !Number.isFinite(fee) || fee < 0 || !Number.isFinite(netValue) || netValue <= 0) {
                sharesInput.value = '';
                return;
            }
            const buyBaseAmount = amount - fee;
            if (buyBaseAmount <= 0) {
                sharesInput.value = '0.00';
                return;
            }
            sharesInput.value = (buyBaseAmount / netValue).toFixed(2);
            return;
        }

        sharesInput.placeholder = '卖出时填写，例如 123.45';
    }

    window.setBackfillMode = function(_mode = 'buy') {
        setBackfillView(_mode === 'dividend' ? 'dividend' : 'trade');
    };

    function getBackfillTradeDateValue() {
        const dateInput = document.getElementById('backfillTradeDate');
        return String(dateInput?.value || '').trim();
    }

    function setBackfillTradeDateValue(dateText) {
        const dateInput = document.getElementById('backfillTradeDate');
        const match = String(dateText || '').match(/^(\d{4})-(\d{2})-(\d{2})$/);
        if (!dateInput) return;
        if (!match) {
            dateInput.value = '';
            return;
        }
        dateInput.value = `${match[1]}-${match[2]}-${match[3]}`;
    }

    window.openTradeModal = function(action, fundCode) {
        currentTradeFundCode = fundCode;
        currentTradeAction = action;

        const modal = document.getElementById('tradeModal');
        const title = document.getElementById('tradeModalTitle');
        const codeDisplay = document.getElementById('tradeModalFundCode');
        const inputLabel = document.getElementById('tradeModalInputLabel');
        const input = document.getElementById('tradeModalInput');
        const hint = document.getElementById('tradeModalHint');
        const confirmBtn = document.getElementById('tradeModalConfirmBtn');

        if (!modal || !title || !codeDisplay || !inputLabel || !input || !hint || !confirmBtn) return;

        const currentShares = parseFloat((window.fundSharesData && window.fundSharesData[fundCode]) || 0);
        codeDisplay.textContent = fundCode;
        input.value = '';

        if (action === 'buy') {
            title.textContent = '买入基金';
            inputLabel.textContent = '买入金额（元）';
            input.placeholder = '请输入买入金额';
            hint.textContent = '15:00前买入按当日净值确认；15:00后按下个交易日净值确认';
            confirmBtn.textContent = '确认买入';
        } else {
            title.textContent = '卖出基金';
            inputLabel.textContent = '卖出份额';
            input.placeholder = '请输入卖出份额';
            hint.textContent = `当前持仓：${currentShares.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}份`;
            confirmBtn.textContent = '确认卖出';
        }

        modal.classList.add('active');
        setTimeout(() => input.focus(), 100);
    };

    window.closeTradeModal = function() {
        const modal = document.getElementById('tradeModal');
        const input = document.getElementById('tradeModalInput');
        const confirmBtn = document.getElementById('tradeModalConfirmBtn');
        if (modal) {
            modal.classList.remove('active');
        }
        if (input) {
            input.value = '';
        }
        if (confirmBtn) {
            confirmBtn.disabled = false;
        }
        currentTradeFundCode = null;
        currentTradeAction = null;
    };

    window.confirmTrade = async function() {
        if (!currentTradeFundCode || !currentTradeAction) return;

        const input = document.getElementById('tradeModalInput');
        const confirmBtn = document.getElementById('tradeModalConfirmBtn');
        if (!input || !confirmBtn) return;

        const value = parseFloat(input.value);
        if (!isFinite(value) || value <= 0) {
            alert(currentTradeAction === 'buy' ? '请输入大于0的买入金额' : '请输入大于0的卖出份额');
            input.focus();
            return;
        }

        confirmBtn.disabled = true;
        confirmBtn.textContent = currentTradeAction === 'buy' ? '买入中...' : '卖出中...';

        try {
            const isBuy = currentTradeAction === 'buy';
            const response = await fetch(isBuy ? '/api/fund/buy' : '/api/fund/sell', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(isBuy
                    ? { code: currentTradeFundCode, amount: value }
                    : { code: currentTradeFundCode, shares: value })
            });

            const result = await response.json();
            if (!result.success) {
                alert(result.message || (isBuy ? '买入失败' : '卖出失败'));
                confirmBtn.disabled = false;
                confirmBtn.textContent = isBuy ? '确认买入' : '确认卖出';
                return;
            }

            const updatedShares = parseFloat(result.current_shares || 0);

            const star = document.querySelector(`.fund-hold-star[data-code="${currentTradeFundCode}"]`);
            if (star) {
                const isHeld = updatedShares > 0;
                star.textContent = isHeld ? '⭐' : '☆';
                star.dataset.hold = isHeld ? '1' : '0';
            }

            window.closeTradeModal();

            if (typeof fetchPortfolioData === 'function') {
                await fetchPortfolioData();
            } else if (typeof calculatePositionSummary === 'function') {
                calculatePositionSummary();
            }
        } catch (e) {
            alert((currentTradeAction === 'buy' ? '买入失败: ' : '卖出失败: ') + (e?.message || e));
            confirmBtn.disabled = false;
            confirmBtn.textContent = currentTradeAction === 'buy' ? '确认买入' : '确认卖出';
        }
    };

    window.buyFund = function(fundCode) {
        window.openTradeModal('buy', fundCode);
    };

    window.sellFund = function(fundCode) {
        window.openTradeModal('sell', fundCode);
    };

    window.openTransactionModal = function(fundCode) {
        currentTransactionFundCode = fundCode;

        const modal = document.getElementById('transactionModal');
        const codeEl = document.getElementById('transactionModalFundCode');
        const nameEl = document.getElementById('transactionModalFundName');
        const hintEl = document.getElementById('transactionModalHint');
        const tbody = document.getElementById('transactionModalTbody');
        const holdingGainEl = document.getElementById('transactionHoldingGain');
        const holdingReturnEl = document.getElementById('transactionHoldingReturn');
        const holdingDaysEl = document.getElementById('transactionHoldingDays');
        const totalFeeEl = document.getElementById('transactionTotalFee');
        const totalGainEl = document.getElementById('transactionTotalGain');
        const totalReturnEl = document.getElementById('transactionTotalReturn');
        if (!modal || !codeEl || !hintEl || !tbody) {
            alert('交易记录弹窗未初始化，请刷新页面后重试');
            return;
        }

        const nameNode = document.querySelector(`.fund-name-cell[data-code="${fundCode}"]`);
        const fundName = nameNode ? nameNode.textContent.replace(/🏷️.*/g, '').trim() : '';
        codeEl.textContent = fundCode;
        if (nameEl) {
            nameEl.textContent = fundName;
        }
        hintEl.textContent = '正在加载交易记录...';
        hintEl.style.color = 'var(--text-dim)';
        if (holdingGainEl) {
            holdingGainEl.textContent = '--';
            holdingGainEl.style.color = 'var(--text-main)';
        }
        if (holdingReturnEl) {
            holdingReturnEl.textContent = '--';
            holdingReturnEl.style.color = 'var(--text-main)';
        }
        if (holdingDaysEl) {
            holdingDaysEl.textContent = '--';
        }
        if (totalFeeEl) {
            totalFeeEl.textContent = '--';
        }
        if (totalGainEl) {
            totalGainEl.textContent = '--';
            totalGainEl.style.color = 'var(--text-main)';
        }
        if (totalReturnEl) {
            totalReturnEl.textContent = '--';
            totalReturnEl.style.color = 'var(--text-main)';
        }
        tbody.innerHTML = '<tr><td colspan="8" style="padding:12px;text-align:center;color:var(--text-dim);">加载中...</td></tr>';

        modal.classList.add('active');
        window.loadFundTransactions();
    };

    window.closeTransactionModal = function() {
        const modal = document.getElementById('transactionModal');
        const modalBody = document.getElementById('transactionModalBody');
        const tableWrap = document.getElementById('transactionModalTableWrap');
        const tbody = document.getElementById('transactionModalTbody');
        const hintEl = document.getElementById('transactionModalHint');
        if (modal) {
            modal.classList.remove('active');
        }
        if (modalBody) {
            modalBody.scrollTop = 0;
        }
        if (tableWrap) {
            tableWrap.scrollTop = 0;
        }
        if (tbody) {
            tbody.innerHTML = '';
        }
        if (hintEl) {
            hintEl.textContent = '';
        }
        currentTransactionFundCode = null;
    };

    window.loadFundTransactions = async function() {
        if (!currentTransactionFundCode) return;

        const fundCode = currentTransactionFundCode;
        const hintEl = document.getElementById('transactionModalHint');
        const tbody = document.getElementById('transactionModalTbody');
        const holdingGainEl = document.getElementById('transactionHoldingGain');
        const holdingReturnEl = document.getElementById('transactionHoldingReturn');
        const holdingDaysEl = document.getElementById('transactionHoldingDays');
        const totalFeeEl = document.getElementById('transactionTotalFee');
        const totalGainEl = document.getElementById('transactionTotalGain');
        const totalReturnEl = document.getElementById('transactionTotalReturn');
        if (!hintEl || !tbody) return;

        const parseNumberFromText = (text) => {
            const raw = String(text || '').replace(/,/g, '').trim();
            const match = raw.match(/[-+]?\d+(?:\.\d+)?/);
            return match ? Number(match[0]) : null;
        };

        const updateTransactionSummary = (rows) => {
            const safeRows = Array.isArray(rows) ? rows : [];

            // 总手续费：当前基金全部交易记录手续费之和
            const totalFee = safeRows.reduce((sum, item) => sum + (Number(item?.fee || 0) || 0), 0);
            if (totalFeeEl) {
                totalFeeEl.textContent = `¥${totalFee.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            }

            // 现金流口径：买入为资金流出，卖出/分红为资金流入
            const totalBuy = safeRows.reduce((sum, item) => {
                if (String(item?.tx_type || '').toLowerCase() !== 'buy') return sum;
                return sum + (Number(item?.amount || 0) || 0);
            }, 0);
            const totalSell = safeRows.reduce((sum, item) => {
                if (String(item?.tx_type || '').toLowerCase() !== 'sell') return sum;
                return sum + (Number(item?.amount || 0) || 0);
            }, 0);
            const totalDividend = safeRows.reduce((sum, item) => {
                if (String(item?.tx_type || '').toLowerCase() !== 'dividend') return sum;
                return sum + (Number(item?.amount || 0) || 0);
            }, 0);

            const positionNode = document.querySelector(`.fund-position-amount-cell[data-code="${fundCode}"]`);
            const positionText = positionNode ? positionNode.textContent.trim() : '';
            const positionValue = parseNumberFromText(positionText) || 0;

            // 总收益 = 累计卖出 + 累计分红 + 当前持仓市值 - 累计买入
            const totalGain = totalSell + totalDividend + positionValue - totalBuy;
            // 总收益率 = 总收益 / 累计买入
            const totalReturn = totalBuy > 0 ? (totalGain / totalBuy * 100) : null;

            if (totalGainEl) {
                totalGainEl.textContent = `${totalGain >= 0 ? '+' : '-'}¥${Math.abs(totalGain).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                totalGainEl.style.color = totalGain >= 0 ? 'var(--up-color)' : 'var(--down-color)';
            }
            if (totalReturnEl) {
                totalReturnEl.textContent = totalReturn == null ? '--' : `${totalReturn >= 0 ? '+' : ''}${totalReturn.toFixed(2)}%`;
                totalReturnEl.style.color = totalReturn == null ? 'var(--text-main)' : (totalReturn >= 0 ? 'var(--up-color)' : 'var(--down-color)');
            }

            const ascRows = [...safeRows].reverse();
            if (holdingDaysEl) {
                const cycles = [];
                let prevShares = 0;
                let openStartDate = null;

                ascRows.forEach((item) => {
                    const sharesAfter = Number(item?.holding_shares_after || 0);
                    const txTime = String(item?.tx_time || '');
                    const txDate = /^\d{4}-\d{2}-\d{2}/.test(txTime) ? txTime.slice(0, 10) : '';

                    if (prevShares <= 1e-6 && sharesAfter > 1e-6 && txDate) {
                        openStartDate = txDate;
                    }

                    if (prevShares > 1e-6 && sharesAfter <= 1e-6 && openStartDate && txDate) {
                        cycles.push({ start: openStartDate, end: txDate });
                        openStartDate = null;
                    }

                    prevShares = sharesAfter;
                });

                if (openStartDate) {
                    holdingDaysEl.textContent = `${openStartDate} - 当前`;
                } else if (cycles.length > 0) {
                    const lastCycle = cycles[cycles.length - 1];
                    holdingDaysEl.textContent = `${lastCycle.start} - ${lastCycle.end}`;
                } else {
                    holdingDaysEl.textContent = '--';
                }
            }

            const gainNode = document.querySelector(`.fund-position-gain-cell[data-code="${fundCode}"]`);
            const gainText = gainNode ? gainNode.textContent.trim() : '';
            const gainValue = parseNumberFromText(gainText);
            if (holdingGainEl) {
                holdingGainEl.textContent = gainValue == null
                    ? '--'
                    : `${gainValue >= 0 ? '+' : '-'}¥${Math.abs(gainValue).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                holdingGainEl.style.color = gainValue == null ? 'var(--text-main)' : (gainValue >= 0 ? 'var(--up-color)' : 'var(--down-color)');
            }

            const rowNode = document.querySelector(`.fund-name-cell[data-code="${fundCode}"]`)?.closest('tr');
            const holdingRateCellText = rowNode?.cells?.[8]?.textContent || '';
            const holdingRateLine = String(holdingRateCellText).split('\n').map(s => s.trim()).find(s => s.includes('%')) || '';
            const holdingRateValue = parseNumberFromText(holdingRateLine);
            if (holdingReturnEl) {
                holdingReturnEl.textContent = holdingRateValue == null
                    ? '--'
                    : `${holdingRateValue >= 0 ? '+' : ''}${holdingRateValue.toFixed(2)}%`;
                holdingReturnEl.style.color = holdingRateValue == null ? 'var(--text-main)' : (holdingRateValue >= 0 ? 'var(--up-color)' : 'var(--down-color)');
            }
        };

        try {
            const response = await fetch(`/api/fund/transactions?code=${encodeURIComponent(fundCode)}`);
            const result = await response.json();

            if (fundCode !== currentTransactionFundCode) return;

            if (!result.success) {
                hintEl.textContent = result.message || '加载交易记录失败';
                hintEl.style.color = 'var(--down-color)';
                tbody.innerHTML = '<tr><td colspan="8" style="padding:12px;text-align:center;color:var(--text-dim);">暂无数据</td></tr>';
                updateTransactionSummary([]);
                return;
            }

            const rows = Array.isArray(result.transactions) ? result.transactions : [];
            if (rows.length === 0) {
                hintEl.textContent = '暂无交易记录';
                hintEl.style.color = 'var(--text-dim)';
                tbody.innerHTML = '<tr><td colspan="8" style="padding:12px;text-align:center;color:var(--text-dim);">暂无交易记录</td></tr>';
                updateTransactionSummary([]);
                return;
            }

            hintEl.textContent = `共 ${rows.length} 条记录（按时间从新到旧）`;
            hintEl.style.color = 'var(--text-dim)';
            updateTransactionSummary(rows);
            tbody.innerHTML = rows.map((item) => {
                const txId = Number(item.id || 0);
                const txType = String(item.tx_type || '').toLowerCase();
                const txTypeColor = txType === 'buy'
                    ? 'var(--up-color)'
                    : (txType === 'sell' ? 'var(--down-color)' : 'var(--text-main)');
                const txTypeText = txType === 'buy' ? '买入' : (txType === 'sell' ? '卖出' : '分红');
                const amount = Number(item.amount || 0);
                const shares = Number(item.shares || 0);
                const netValue = item.net_value == null ? '-' : Number(item.net_value).toFixed(4);
                const fee = Number(item.fee || 0);
                const avgCostAfter = item.avg_cost_after == null ? '-' : Number(item.avg_cost_after).toFixed(4);
                const txTime = String(item.tx_time || '');
                const txDate = /^\d{4}-\d{2}-\d{2}/.test(txTime) ? txTime.slice(0, 10) : txTime;
                const isDividend = txType === 'dividend';
                const referenceAmount = !isDividend && netValue !== '-'
                    ? ((txType === 'sell' ? (shares * Number(netValue) - fee) : (shares * Number(netValue) + fee)))
                    : null;
                const referenceText = referenceAmount == null
                    ? ''
                    : `${txType === 'sell' ? '到账参考' : '确认金额参考'}：¥${referenceAmount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                const escapedTxTime = txTime
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;')
                    .replace(/"/g, '&quot;')
                    .replace(/'/g, '&#39;');
                return `
                    <tr id="tx_row_${txId}" data-tx-time="${escapedTxTime}" data-tx-type="${txType}" data-net-value="${netValue === '-' ? '' : netValue}">
                        <td style="padding: 8px; border-top: 1px solid var(--border);">
                            <span style="color: var(--text-main);">${txDate || '-'}</span>
                        </td>
                        <td style="padding: 8px; border-top: 1px solid var(--border); color: ${txTypeColor}; font-weight: 600; font-size: 12px; white-space: nowrap;">
                            <span style="font-size: 12px; white-space: nowrap;">${txTypeText}</span>
                        </td>
                        <td style="padding: 8px; border-top: 1px solid var(--border); text-align: right;">
                            <input id="tx_amount_${txId}" type="number" step="0.01" min="0" value="${amount.toFixed(2)}" style="width: 110px; text-align: right; padding: 6px; border: 1px solid var(--border); border-radius: 4px; background: var(--card-bg); color: var(--text-main);">
                            ${referenceText ? `<div id="tx_amount_ref_${txId}" style="margin-top:4px; font-size:11px; color:var(--text-dim); white-space:nowrap;">${referenceText}</div>` : ''}
                        </td>
                        <td style="padding: 8px; border-top: 1px solid var(--border); text-align: right;">
                            ${isDividend
                                ? '<span style="font-family: var(--font-mono); color: var(--text-dim);">-</span>'
                                : `<input id="tx_shares_${txId}" type="number" step="0.01" min="0" value="${shares.toFixed(2)}" oninput="updateTransactionReferenceAmount(${txId})" style="width: 90px; text-align: right; padding: 6px; border: 1px solid var(--border); border-radius: 4px; background: var(--card-bg); color: var(--text-main);">`}
                        </td>
                        <td style="padding: 8px; border-top: 1px solid var(--border); text-align: right;">
                            <span id="tx_net_${txId}" style="font-family: var(--font-mono); color: ${isDividend ? 'var(--text-dim)' : 'var(--text-main)'};">${netValue === '-' ? '-' : netValue}</span>
                        </td>
                        <td style="padding: 8px; border-top: 1px solid var(--border); text-align: right;">
                            <input id="tx_fee_${txId}" type="number" step="0.01" min="0" value="${fee.toFixed(2)}" ${isDividend ? 'disabled' : ''} oninput="updateTransactionReferenceAmount(${txId})" style="width: 90px; text-align: right; padding: 6px; border: 1px solid var(--border); border-radius: 4px; background: var(--card-bg); color: var(--text-main);">
                        </td>
                        <td style="padding: 10px; border-top: 1px solid var(--border); text-align: right;">${avgCostAfter}</td>
                        <td style="padding: 10px; border-top: 1px solid var(--border); text-align: center;">
                            <div style="display:flex;justify-content:center;align-items:center;gap:14px;">
                                <button class="btn btn-primary" style="padding:4px 10px;font-size:12px;min-width:56px;display:inline-flex;align-items:center;justify-content:center;text-align:center;" onclick="updateFundTransaction(${txId})">更新</button>
                                <button class="btn btn-danger" style="padding:4px 10px;font-size:12px;min-width:56px;display:inline-flex;align-items:center;justify-content:center;text-align:center;" onclick="deleteFundTransaction(${txId})">删除</button>
                            </div>
                        </td>
                    </tr>
                `;
            }).join('');
        } catch (e) {
            hintEl.textContent = '加载交易记录失败';
            hintEl.style.color = 'var(--down-color)';
            tbody.innerHTML = '<tr><td colspan="8" style="padding:12px;text-align:center;color:var(--text-dim);">加载失败</td></tr>';
        }
    };

    window.updateTransactionReferenceAmount = function(transactionId) {
        const txId = Number(transactionId || 0);
        if (!Number.isFinite(txId) || txId <= 0) return;

        const row = document.getElementById(`tx_row_${txId}`);
        const sharesInput = document.getElementById(`tx_shares_${txId}`);
        const feeInput = document.getElementById(`tx_fee_${txId}`);
        const refEl = document.getElementById(`tx_amount_ref_${txId}`);
        if (!row || !refEl || !sharesInput || !feeInput) return;

        const txType = String(row.dataset.txType || '').toLowerCase();
        if (txType === 'dividend') return;

        const shares = parseFloat(sharesInput.value || '0');
        const fee = parseFloat(feeInput.value || '0');
        const netValue = parseFloat(row.dataset.netValue || '0');
        if (!Number.isFinite(shares) || shares < 0 || !Number.isFinite(fee) || fee < 0 || !Number.isFinite(netValue) || netValue <= 0) {
            refEl.textContent = txType === 'sell' ? '到账参考：--' : '确认金额参考：--';
            return;
        }

        const referenceAmount = txType === 'sell'
            ? (shares * netValue - fee)
            : (shares * netValue + fee);
        refEl.textContent = `${txType === 'sell' ? '到账参考' : '确认金额参考'}：¥${Math.max(referenceAmount, 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    };

    window.updateFundTransaction = async function(transactionId) {
        if (!currentTransactionFundCode) return;

        const txId = Number(transactionId || 0);
        if (!Number.isFinite(txId) || txId <= 0) {
            window.showSimpleMessage('交易ID无效', 'error');
            return;
        }

        const txRow = document.getElementById(`tx_row_${txId}`);
        const txTime = String(txRow?.dataset.txTime || '').trim();
        const txType = String(txRow?.dataset.txType || '').trim();
        const amount = parseFloat(document.getElementById(`tx_amount_${txId}`)?.value || '0');
        const shares = txType === 'dividend' ? 0 : parseFloat(document.getElementById(`tx_shares_${txId}`)?.value || '0');
        const netValue = parseFloat(txRow?.dataset.netValue || '0');
        const fee = txType === 'dividend' ? 0 : parseFloat(document.getElementById(`tx_fee_${txId}`)?.value || '0');

        if (!txTime) {
            window.showSimpleMessage('交易时间不能为空', 'error');
            return;
        }
        if (!['buy', 'sell', 'dividend'].includes(txType)) {
            window.showSimpleMessage('交易类型无效', 'error');
            return;
        }
        if (!Number.isFinite(amount) || amount <= 0) {
            window.showSimpleMessage('金额必须大于0', 'error');
            return;
        }
        if (txType !== 'dividend' && (!Number.isFinite(netValue) || netValue <= 0)) {
            window.showSimpleMessage('净值必须大于0', 'error');
            return;
        }
        if (!Number.isFinite(fee) || fee < 0) {
            window.showSimpleMessage('手续费必须大于等于0', 'error');
            return;
        }
        if (txType !== 'dividend' && (!Number.isFinite(shares) || shares <= 0)) {
            window.showSimpleMessage('份额必须大于0', 'error');
            return;
        }

        try {
            const response = await fetch('/api/fund/transaction/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    code: currentTransactionFundCode,
                    transaction_id: txId,
                    tx_time: txTime,
                    tx_type: txType,
                    amount,
                    shares: txType === 'dividend' ? 0 : shares,
                    net_value: txType === 'dividend' ? null : netValue,
                    fee,
                })
            });
            const result = await response.json();
            if (!result.success) {
                window.showSimpleMessage(result.message || '更新失败', 'error');
                return;
            }

            const updatedShares = parseFloat(result.current_shares || 0);
            if (!window.fundSharesData) {
                window.fundSharesData = {};
            }
            window.fundSharesData[currentTransactionFundCode] = updatedShares;

            const star = document.querySelector(`.fund-hold-star[data-code="${currentTransactionFundCode}"]`);
            if (star) {
                const isHeld = updatedShares > 0;
                star.textContent = isHeld ? '⭐' : '☆';
                star.dataset.hold = isHeld ? '1' : '0';
            }

            window.showSimpleMessage(result.message || '更新成功', 'success');
            window.loadFundTransactions();
            if (typeof fetchPortfolioData === 'function') {
                fetchPortfolioData().catch(() => {});
            }
        } catch (e) {
            window.showSimpleMessage('更新失败: ' + (e?.message || e), 'error');
        }
    };

    window.deleteFundTransaction = async function(transactionId) {
        if (!currentTransactionFundCode) return;

        const txId = Number(transactionId || 0);
        if (!Number.isFinite(txId) || txId <= 0) {
            window.showSimpleMessage('交易ID无效', 'error');
            return;
        }

        try {
            const response = await fetch('/api/fund/transaction/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    code: currentTransactionFundCode,
                    transaction_id: txId,
                })
            });
            const result = await response.json();
            if (!result.success) {
                window.showSimpleMessage(result.message || '删除失败', 'error');
                return;
            }

            const updatedShares = parseFloat(result.current_shares || 0);
            if (!window.fundSharesData) {
                window.fundSharesData = {};
            }
            window.fundSharesData[currentTransactionFundCode] = updatedShares;

            const star = document.querySelector(`.fund-hold-star[data-code="${currentTransactionFundCode}"]`);
            if (star) {
                const isHeld = updatedShares > 0;
                star.textContent = isHeld ? '⭐' : '☆';
                star.dataset.hold = isHeld ? '1' : '0';
            }

            window.showSimpleMessage(result.message || '删除成功', 'success');

            window.loadFundTransactions();

            if (typeof fetchPortfolioData === 'function') {
                fetchPortfolioData().catch(() => {});
            }
        } catch (e) {
            window.showSimpleMessage('删除失败: ' + (e?.message || e), 'error');
        }
    };

    window.clearFundTransactionsByCode = async function(fundCode, fundName = '') {
        const normalizedCode = String(fundCode || '').trim();
        if (!/^\d{6}$/.test(normalizedCode)) {
            window.showSimpleMessage('基金代码格式错误，应为6位数字', 'error');
            return;
        }

        try {
            const txResponse = await fetch(`/api/fund/transactions?code=${encodeURIComponent(normalizedCode)}`);
            const txResult = await txResponse.json();
            if (!txResult.success) {
                window.showSimpleMessage(txResult.message || '读取交易记录失败', 'error');
                return;
            }

            const rows = Array.isArray(txResult.transactions) ? txResult.transactions : [];
            if (rows.length === 0) {
                window.showSimpleMessage('当前基金没有可清空的交易记录', 'info');
                return;
            }

            const backupData = {
                exported_at: new Date().toISOString(),
                fund_code: normalizedCode,
                fund_name: fundName,
                transaction_count: rows.length,
                transactions: rows,
            };
            const blob = new Blob([JSON.stringify(backupData, null, 2)], { type: 'application/json;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const anchor = document.createElement('a');
            anchor.href = url;
            anchor.download = `${normalizedCode}_transactions_backup_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.json`;
            document.body.appendChild(anchor);
            anchor.click();
            anchor.remove();
            URL.revokeObjectURL(url);

            const confirmText = `清空 ${normalizedCode}`;
            const inputText = window.prompt(
                `危险操作：将清空 ${normalizedCode}${fundName ? ' ' + fundName : ''} 的全部交易记录。\n已自动下载备份文件。\n\n请输入“${confirmText}”以确认：`,
                ''
            );
            if (inputText === null) {
                return;
            }

            const response = await fetch('/api/fund/transactions/clear', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    code: normalizedCode,
                    confirm_text: inputText,
                })
            });
            const result = await response.json();
            if (!result.success) {
                window.showSimpleMessage(result.message || '清空失败', 'error');
                return;
            }

            const updatedShares = parseFloat(result.current_shares || 0);
            if (!window.fundSharesData) {
                window.fundSharesData = {};
            }
            window.fundSharesData[normalizedCode] = updatedShares;

            const star = document.querySelector(`.fund-hold-star[data-code="${normalizedCode}"]`);
            if (star) {
                const isHeld = updatedShares > 0;
                star.textContent = isHeld ? '⭐' : '☆';
                star.dataset.hold = isHeld ? '1' : '0';
            }

            window.showSimpleMessage(result.message || '清空成功', 'success');

            if (currentTransactionFundCode === normalizedCode && typeof window.loadFundTransactions === 'function') {
                await window.loadFundTransactions();
            }
            if (typeof fetchPortfolioData === 'function') {
                fetchPortfolioData().catch(() => {});
            }
        } catch (e) {
            window.showSimpleMessage('清空失败: ' + (e?.message || e), 'error');
        }
    };

    window.clearCurrentFundTransactions = async function() {
        if (!currentTransactionFundCode) {
            window.showSimpleMessage('未选择基金', 'error');
            return;
        }
        const fundCode = currentTransactionFundCode;
        const fundName = document.getElementById('transactionModalFundName')?.textContent?.trim() || '';
        await window.clearFundTransactionsByCode(fundCode, fundName);
    };

    window.openBackfillModal = function(fundCode) {
        currentBackfillFundCode = fundCode;
        currentBackfillFetchToken += 1;

        const modal = document.getElementById('backfillModal');
        const titleEl = document.getElementById('backfillModalTitle');
        const codeDisplay = document.getElementById('backfillModalFundCode');
        const tradeDateInput = document.getElementById('backfillTradeDate');
        const netValueInput = document.getElementById('backfillNetValue');
        const amountInput = document.getElementById('backfillAmount');
        const sharesInput = document.getElementById('backfillShares');
        const feeInput = document.getElementById('backfillFee');
        const hint = document.getElementById('backfillNetValueHint');

        if (!modal || !codeDisplay || !tradeDateInput || !netValueInput || !amountInput || !sharesInput || !feeInput) {
            alert('补录弹窗未初始化，请刷新页面后重试');
            return;
        }

        const today = new Date();
        const yyyy = today.getFullYear();
        const mm = String(today.getMonth() + 1).padStart(2, '0');
        const dd = String(today.getDate()).padStart(2, '0');

        codeDisplay.textContent = fundCode;
        setBackfillTradeDateValue(`${yyyy}-${mm}-${dd}`);
        netValueInput.value = '';
        amountInput.value = '';
        sharesInput.value = '';
        feeInput.value = '';
        if (hint) {
            hint.textContent = '正在尝试自动填充净值...';
            hint.style.color = 'var(--text-dim)';
        }
        setBackfillView('trade');
        currentBackfillNetValueLoading = true;
        updateBackfillSubmitButtonsState();
        updateBackfillSharesPreview();

        modal.classList.add('active');
        setTimeout(() => tradeDateInput.focus(), 100);

        window.tryAutoFillBackfillNetValue();
    };

    window.closeBackfillModal = function() {
        const modal = document.getElementById('backfillModal');
        const { buyBtn, sellBtn, dividendBtn } = getBackfillActionButtons();
        if (modal) {
            modal.classList.remove('active');
        }
        if (buyBtn) {
            buyBtn.disabled = false;
            buyBtn.textContent = '补录买入';
        }
        if (sellBtn) {
            sellBtn.disabled = false;
            sellBtn.textContent = '补录卖出';
        }
        if (dividendBtn) {
            dividendBtn.disabled = false;
            dividendBtn.textContent = '补录分红';
        }
        setBackfillView('trade');
        currentBackfillNetValueLoading = false;
        currentBackfillFundCode = null;
    };

    window.tryAutoFillBackfillNetValue = async function() {
        if (!currentBackfillFundCode) return;
        if (currentBackfillView === 'dividend') {
            currentBackfillNetValueLoading = false;
            updateBackfillSubmitButtonsState();
            return;
        }

        const tradeDate = getBackfillTradeDateValue();
        const netValueInput = document.getElementById('backfillNetValue');
        const hint = document.getElementById('backfillNetValueHint');
        if (!netValueInput || !hint) return;

        if (!tradeDate) {
            hint.textContent = '请选择日期后自动填充净值';
            hint.style.color = 'var(--text-dim)';
            return;
        }

        const fetchToken = ++currentBackfillFetchToken;
        currentBackfillNetValueLoading = true;
        updateBackfillSubmitButtonsState();
        hint.textContent = '正在查询该日期净值...';
        hint.style.color = 'var(--text-dim)';

        try {
            const response = await fetch(`/api/fund/net-value-by-date?code=${encodeURIComponent(currentBackfillFundCode)}&date=${encodeURIComponent(tradeDate)}`);
            const result = await response.json();

            if (fetchToken !== currentBackfillFetchToken) return;

            if (!result.success) {
                hint.textContent = result.message || '自动查询净值失败，请手动输入';
                hint.style.color = 'var(--down-color)';
                currentBackfillNetValueLoading = false;
                updateBackfillSubmitButtonsState();
                return;
            }

            if (result.found && isFinite(parseFloat(result.net_value))) {
                netValueInput.value = parseFloat(result.net_value).toFixed(4);
                hint.textContent = `已自动填充 ${result.trade_date} 净值：${parseFloat(result.net_value).toFixed(4)}`;
                hint.style.color = 'var(--up-color)';
                currentBackfillNetValueLoading = false;
                updateBackfillSubmitButtonsState();
                updateBackfillSharesPreview();
                return;
            }

            hint.textContent = result.message || '趋势数据中无该日期净值，请手动输入';
            hint.style.color = 'var(--text-dim)';
            currentBackfillNetValueLoading = false;
            updateBackfillSubmitButtonsState();
            updateBackfillSharesPreview();
        } catch (e) {
            if (fetchToken !== currentBackfillFetchToken) return;
            hint.textContent = '自动查询净值失败，请手动输入';
            hint.style.color = 'var(--down-color)';
            currentBackfillNetValueLoading = false;
            updateBackfillSubmitButtonsState();
            updateBackfillSharesPreview();
        }
    };

    window.setBackfillAmountQuick = function(amount) {
        const amountInput = document.getElementById('backfillAmount');
        if (!amountInput) return;
        const value = Number(amount || 0);
        if (!Number.isFinite(value) || value <= 0) return;
        amountInput.value = String(value);
        updateBackfillSharesPreview();
        amountInput.focus();
    };

    window.confirmBackfillTrade = async function(action = 'buy') {
        if (!currentBackfillFundCode) {
            window.showSimpleMessage('未选择基金', 'error');
            return;
        }

        const tradeDateInput = document.getElementById('backfillTradeDate');
        const netValueInput = document.getElementById('backfillNetValue');
        const amountInput = document.getElementById('backfillAmount');
        const sharesInput = document.getElementById('backfillShares');
        const feeInput = document.getElementById('backfillFee');
        const { buyBtn, sellBtn, dividendBtn } = getBackfillActionButtons();
        const actionBtn = action === 'sell' ? sellBtn : (action === 'dividend' ? dividendBtn : buyBtn);
        if (!tradeDateInput || !netValueInput || !amountInput || !sharesInput || !feeInput || !actionBtn) return;

        const tradeDate = getBackfillTradeDateValue();
        const netValueRaw = String(netValueInput.value || '').trim();
        const netValue = netValueRaw === '' ? NaN : parseFloat(netValueRaw);
        const amountValue = parseFloat(amountInput.value);
        const sharesValue = parseFloat(sharesInput.value);
        const feeValue = String(feeInput.value || '').trim() === '' ? 0 : parseFloat(feeInput.value);
        const isSellBackfill = action === 'sell';
        const isDividendBackfill = action === 'dividend';

        if (isDividendBackfill && currentBackfillView !== 'dividend') {
            setBackfillView('dividend');
        }
        if (!isDividendBackfill && currentBackfillView !== 'trade') {
            setBackfillView('trade');
        }

        if (!tradeDate) {
            window.showSimpleMessage('请选择交易日期', 'error');
            tradeDateInput.focus();
            return;
        }

        if (!isDividendBackfill && (!isFinite(netValue) || netValue <= 0)) {
            window.showSimpleMessage('请输入大于0的当日净值', 'error');
            netValueInput.focus();
            return;
        }

        if (isSellBackfill) {
            if (!isFinite(sharesValue) || sharesValue <= 0) {
                window.showSimpleMessage('请输入大于0的卖出份额', 'error');
                sharesInput.focus();
                return;
            }
        } else {
            if (!isFinite(amountValue) || amountValue <= 0) {
                window.showSimpleMessage(isDividendBackfill ? '请输入大于0的分红金额' : '请输入大于0的买入金额', 'error');
                amountInput.focus();
                return;
            }
        }

        if (!isDividendBackfill && (!isFinite(feeValue) || feeValue < 0)) {
            window.showSimpleMessage('请输入大于等于0的手续费', 'error');
            feeInput.focus();
            return;
        }

        if (!isSellBackfill && !isDividendBackfill && amountValue <= feeValue) {
            window.showSimpleMessage('买入金额需大于手续费', 'error');
            amountInput.focus();
            return;
        }

        if (isSellBackfill) {
            const grossSell = sharesValue * netValue;
            if (feeValue >= grossSell) {
                window.showSimpleMessage('手续费不能大于等于卖出总额（份额×净值）', 'error');
                feeInput.focus();
                return;
            }
        }

        if (buyBtn) buyBtn.disabled = true;
        if (sellBtn) sellBtn.disabled = true;
        if (dividendBtn) dividendBtn.disabled = true;
        if (isSellBackfill) {
            actionBtn.textContent = '补录卖出中...';
        } else if (isDividendBackfill) {
            actionBtn.textContent = '补录分红中...';
        } else {
            actionBtn.textContent = '补录买入中...';
        }

        try {
            const requestUrl = isDividendBackfill
                ? '/api/fund/dividend-backfill'
                : (isSellBackfill ? '/api/fund/sell-backfill' : '/api/fund/buy-backfill');
            const response = await fetch(requestUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    code: currentBackfillFundCode,
                    trade_date: tradeDate,
                    net_value: isDividendBackfill ? undefined : netValue,
                    fee: isDividendBackfill ? 0 : feeValue,
                    amount: isSellBackfill ? undefined : amountValue,
                    shares: isSellBackfill ? sharesValue : undefined,
                })
            });

            const result = await response.json();
            if (!result.success) {
                window.showSimpleMessage(result.message || '补录失败', 'error');
                if (buyBtn) buyBtn.disabled = false;
                if (sellBtn) sellBtn.disabled = false;
                if (dividendBtn) dividendBtn.disabled = false;
                if (buyBtn) buyBtn.textContent = '补录买入';
                if (sellBtn) sellBtn.textContent = '补录卖出';
                if (dividendBtn) dividendBtn.textContent = '补录分红';
                updateBackfillSubmitButtonsState();
                return;
            }

            const updatedShares = parseFloat(result.current_shares || 0);
            if (!window.fundSharesData) {
                window.fundSharesData = {};
            }
            window.fundSharesData[currentBackfillFundCode] = updatedShares;

            const star = document.querySelector(`.fund-hold-star[data-code="${currentBackfillFundCode}"]`);
            if (star) {
                const isHeld = updatedShares > 0;
                star.textContent = isHeld ? '⭐' : '☆';
                star.dataset.hold = isHeld ? '1' : '0';
            }

            amountInput.value = '';
            sharesInput.value = '';
            if (isSellBackfill) {
                sharesInput.focus();
            } else if (isDividendBackfill) {
                amountInput.focus();
            } else {
                amountInput.focus();
            }
            if (buyBtn) buyBtn.disabled = false;
            if (sellBtn) sellBtn.disabled = false;
            if (dividendBtn) dividendBtn.disabled = false;
            if (buyBtn) buyBtn.textContent = '补录买入';
            if (sellBtn) sellBtn.textContent = '补录卖出';
            if (dividendBtn) dividendBtn.textContent = '补录分红';
            updateBackfillSubmitButtonsState();

            if (typeof calculatePositionSummary === 'function') {
                calculatePositionSummary();
            }

            window.showSimpleMessage(result.message || '补录成功', 'backfill-success');
        } catch (e) {
            window.showSimpleMessage('补录失败: ' + (e?.message || e), 'error');
            if (buyBtn) buyBtn.disabled = false;
            if (sellBtn) sellBtn.disabled = false;
            if (dividendBtn) dividendBtn.disabled = false;
            if (buyBtn) buyBtn.textContent = '补录买入';
            if (sellBtn) sellBtn.textContent = '补录卖出';
            if (dividendBtn) dividendBtn.textContent = '补录分红';
            updateBackfillSubmitButtonsState();
        }
    };

    // ==================== Shares Modal Functions ====================

    // 当前正在编辑份额的基金代码
    let currentSharesFundCode = null;

    // 获取基金份额（从内存或DOM）
    window.getFundShares = function(fundCode) {
        // 先从全局存储获取
        if (window.fundSharesData && window.fundSharesData[fundCode]) {
            return window.fundSharesData[fundCode];
        }
        return 0;
    };

    // 更新份额按钮状态
    function updateSharesButton(fundCode, shares) {
        const button = document.getElementById('sharesBtn_' + fundCode);
        if (button) {
            if (shares > 0) {
                button.textContent = '修改';
                button.style.background = '#10b981';
            } else {
                button.textContent = '设置';
                button.style.background = '#3b82f6';
            }
        }
    }

    // 打开份额设置弹窗
    window.openSharesModal = function(fundCode) {
        currentSharesFundCode = fundCode;
        const modal = document.getElementById('sharesModal');
        const fundCodeDisplay = document.getElementById('sharesModalFundCode');
        const sharesInput = document.getElementById('sharesModalInput');

        // 获取当前份额
        const sharesValue = window.getFundShares(fundCode) || 0;
        sharesInput.value = sharesValue > 0 ? sharesValue : '';
        fundCodeDisplay.textContent = fundCode;

        // 更新弹窗标题
        const header = modal.querySelector('.sector-modal-header');
        if (header) {
            header.textContent = sharesValue > 0 ? '修改持仓份额' : '设置持仓份额';
        }

        modal.classList.add('active');
        setTimeout(() => sharesInput.focus(), 100);
    };

    // 关闭份额设置弹窗
    window.closeSharesModal = function() {
        const modal = document.getElementById('sharesModal');
        if (modal) {
            modal.classList.remove('active');
        }
        currentSharesFundCode = null;
    };

    // 确认设置份额
    window.confirmShares = async function() {
        if (!currentSharesFundCode) {
            alert('未选择基金');
            return;
        }

        const sharesInput = document.getElementById('sharesModalInput');
        const shares = parseFloat(sharesInput.value) || 0;

        if (shares < 0) {
            alert('份额不能为负数');
            return;
        }

        try {
            const response = await fetch('/api/fund/shares', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code: currentSharesFundCode, shares: shares })
            });
            const result = await response.json();

            if (result.success) {
                const latestShares = parseFloat(result.current_shares ?? shares) || 0;
                const latestIsHold = result.current_is_hold !== undefined ? !!result.current_is_hold : (latestShares > 0);

                // 更新全局存储
                if (!window.fundSharesData) {
                    window.fundSharesData = {};
                }
                window.fundSharesData[currentSharesFundCode] = latestShares;

                const star = document.querySelector(`.fund-hold-star[data-code="${currentSharesFundCode}"]`);
                if (star) {
                    star.textContent = latestIsHold ? '⭐' : '☆';
                    star.dataset.hold = latestIsHold ? '1' : '0';
                }

                // 更新按钮状态
                updateSharesButton(currentSharesFundCode, latestShares);

                // 关闭弹窗
                window.closeSharesModal();

                if (typeof fetchPortfolioData === 'function') {
                    await fetchPortfolioData();
                } else {
                    calculatePositionSummary();
                }

                alert(result.message);
            } else {
                alert(result.message);
            }
        } catch (e) {
            alert('设置份额失败: ' + e.message);
        }
    };

    const tradeModal = document.getElementById('tradeModal');
    if (tradeModal) {
        tradeModal.addEventListener('click', function(e) {
            if (e.target === tradeModal) {
                closeTradeModal();
            }
        });
    }

    const backfillModal = document.getElementById('backfillModal');
    if (backfillModal) {
        backfillModal.addEventListener('click', function(e) {
            if (e.target === backfillModal) {
                closeBackfillModal();
            }
        });
    }

    const tradeInput = document.getElementById('tradeModalInput');
    if (tradeInput) {
        tradeInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                confirmTrade();
            }
        });
    }

    const backfillAmountInput = document.getElementById('backfillAmount');
    if (backfillAmountInput) {
        backfillAmountInput.addEventListener('input', function() {
            updateBackfillSharesPreview();
        });
        backfillAmountInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                confirmBackfillTrade(currentBackfillView === 'dividend' ? 'dividend' : 'buy');
            }
        });
    }

    const backfillSharesInput = document.getElementById('backfillShares');
    if (backfillSharesInput) {
        backfillSharesInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                confirmBackfillTrade('sell');
            }
        });
    }

    const backfillTradeDateInput = document.getElementById('backfillTradeDate');
    if (backfillTradeDateInput) {
        backfillTradeDateInput.addEventListener('input', function() {
            if (typeof window.tryAutoFillBackfillNetValue === 'function') {
                window.tryAutoFillBackfillNetValue();
            }
        });
        backfillTradeDateInput.addEventListener('change', function() {
            if (typeof window.tryAutoFillBackfillNetValue === 'function') {
                window.tryAutoFillBackfillNetValue();
            }
        });
    }

    const backfillNetValueInput = document.getElementById('backfillNetValue');
    if (backfillNetValueInput) {
        backfillNetValueInput.addEventListener('input', function() {
            updateBackfillSharesPreview();
            if (!currentBackfillNetValueLoading) {
                updateBackfillSubmitButtonsState();
            }
        });
    }

    const backfillFeeInput = document.getElementById('backfillFee');
    if (backfillFeeInput) {
        backfillFeeInput.addEventListener('input', function() {
            updateBackfillSharesPreview();
        });
        backfillFeeInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                confirmBackfillTrade('buy');
            }
        });
    }

    // ==================== Auto-Refresh System ====================
    let refreshInterval;
    let REFRESH_INTERVAL = 60000; // 默认 60 秒（毫秒）
    let lastRefreshTime = null; // 记录最后刷新时间

    // 初始化刷新配置（从后端API读取）
    async function initRefreshConfig() {
        try {
            const response = await fetch('/api/config/refresh');
            if (response.ok) {
                const config = await response.json();
                REFRESH_INTERVAL = config.auto_refresh_interval || 60000;
                console.log(`✅ Refresh config loaded: interval=${REFRESH_INTERVAL}ms`);
                // 暴露配置到 window，用于调试
                window._refreshConfig = { REFRESH_INTERVAL };
            } else {
                console.warn(`❌ Failed to fetch refresh config: HTTP ${response.status}`);
                window._refreshConfig = { error: `HTTP ${response.status}` };
            }
        } catch (e) {
            console.error('❌ Failed to load refresh config:', e);
            window._refreshConfig = { error: e.message };
        }
    }

    // 更新刷新时间显示
    function updateRefreshTimeDisplay(pageType = null) {
        let timeDisplay;
        if (pageType) {
            timeDisplay = document.getElementById(`lastRefreshTime-${pageType}`);
        } else {
            // 更新所有可见的时间显示
            ['portfolio', 'metals', 'sectors'].forEach(type => {
                const display = document.getElementById(`lastRefreshTime-${type}`);
                if (display && getComputedStyle(display).display !== 'none') {
                    updateRefreshTimeForType(type, display);
                }
            });
            return;
        }
        if (!timeDisplay) return;
        updateRefreshTimeForType(pageType, timeDisplay);
    }

    function updateRefreshTimeForType(pageType, timeDisplay) {

        if (!lastRefreshTime) {
            timeDisplay.textContent = '';
            return;
        }

        // 显示具体的时分秒
        const hours = String(lastRefreshTime.getHours()).padStart(2, '0');
        const minutes = String(lastRefreshTime.getMinutes()).padStart(2, '0');
        const seconds = String(lastRefreshTime.getSeconds()).padStart(2, '0');
        
        timeDisplay.textContent = `${hours}:${minutes}:${seconds}`;
    }

    // 定时更新刷新时间显示
    setInterval(updateRefreshTimeDisplay, 1000);

    // Start auto-refresh
    function startAutoRefresh() {
        if (refreshInterval) {
            clearInterval(refreshInterval);
        }
        refreshInterval = setInterval(() => {
            refreshCurrentPage();
        }, REFRESH_INTERVAL);
        console.log(`Auto-refresh started (${REFRESH_INTERVAL}ms interval)`);
    }

    // Stop auto-refresh
    function stopAutoRefresh() {
        if (refreshInterval) {
            clearInterval(refreshInterval);
            refreshInterval = null;
            console.log('Auto-refresh stopped');
        }
    }

    // Refresh current page data based on route (只更新数据，不重新加载页面)
    async function refreshCurrentPage() {
        const path = window.location.pathname;

        // 快速检查：避免重复点击刷新按钮
        // 通过检查对应页面的刷新按钮是否已禁用
        let refreshBtn = null;
        switch (path) {
            case '/portfolio':
                refreshBtn = document.getElementById('refreshBtn-portfolio');
                break;
            case '/precious-metals':
                refreshBtn = document.getElementById('refreshBtn-metals');
                break;
            case '/sectors':
                // sectors 可能有两个按钮
                refreshBtn = document.getElementById('refreshBtn-sectors') || document.getElementById('refreshBtn-sectors-query');
                break;
        }
        
        // 如果按钮已禁用，说明已经在刷新中，拒絕重複點擊
        if (refreshBtn && refreshBtn.disabled) {
            console.log('Refresh already in progress, ignoring click');
            return;
        }

        // 注意：按钮状态的管理由各个 fetch 函数来处理
        // 这里只负责调用对应的数据更新函数
        try {
            console.log(`Refreshing ${path}`);
            switch (path) {
                case '/portfolio':
                    await fetchPortfolioData();
                    break;
                case '/precious-metals':
                    // 只更新数据，不重新加载页面
                    await fetchPreciousMetalsData();
                    break;
                case '/sectors':
                    // 只更新数据，不重新加载页面
                    await fetchSectorsData();
                    break;
                case '/market-indices':
                    await fetchMarketIndicesData();
                    break;
                case '/market':
                    await fetchNewsData();
                    break;
                default:
                    console.log('No refresh handler for path:', path);
            }
        } catch (e) {
            console.error('Refresh failed:', e);
        }
    }

    // Portfolio page data fetch (更新基金表格和持仓统计)
    async function fetchPortfolioData() {
        const refreshBtn = document.getElementById('refreshBtn-portfolio');
        try {
            // 显示加载状态
            if (refreshBtn) {
                refreshBtn.disabled = true;
                refreshBtn.innerHTML = '⏳ 更新中...';
            }

            // 1. 获取最新的基金表格
            const tableResponse = await fetch('/api/portfolio/fund-table');
            if (!tableResponse.ok) {
                throw new Error(`Failed to fetch fund table: ${tableResponse.status}`);
            }
            const tableData = await tableResponse.json();
            
            if (!tableData.success) {
                throw new Error(tableData.message || '获取基金表格失败');
            }

            // 2. 替换基金表格内容（整表 thead+tbody，保证持仓份额列与表头一致）
            const newTableHTML = tableData.html;
            if (!newTableHTML || !newTableHTML.trim()) {
                throw new Error('获取到空的基金表格数据，已保留当前页面数据');
            }

            const parser = new DOMParser();
            const newTableDoc = parser.parseFromString(newTableHTML, 'text/html');
            const newTables = Array.from(newTableDoc.querySelectorAll('.style-table'));
            const currentTables = Array.from(document.querySelectorAll('.style-table'));
            const newTable = newTables.find(table => table.querySelector('.fund-name-cell')) || newTables[0] || null;
            const currentTable = currentTables.find(table => table.querySelector('.fund-name-cell')) || currentTables[0] || null;

            if (!newTable || !currentTable) {
                throw new Error('新基金表格结构无效，已保留当前页面数据');
            }

            const newRowCount = newTable.querySelectorAll('tbody tr').length;
            const currentRowCount = currentTable.querySelectorAll('tbody tr').length;
            const newFundItemCount = newTable.querySelectorAll('.fund-name-cell').length;

            // 保护逻辑：若当前有数据而新表为空（常见于网络异常），则不替换，避免页面空白
            if (currentRowCount > 0 && newRowCount === 0) {
                throw new Error('未获取到有效新数据，已保留当前页面数据');
            }

            // 保护逻辑：基金表必须包含基金条目，否则判定为无效刷新（避免空白）
            if (newFundItemCount === 0) {
                throw new Error('新数据缺少基金条目，已保留当前页面数据');
            }

            // 3. 获取最新的份额数据
            const fundDataResponse = await fetch('/api/fund/data');
            if (!fundDataResponse.ok) {
                throw new Error(`Failed to fetch fund data: ${fundDataResponse.status}`);
            }

            const fundData = await fundDataResponse.json();

            // 构建最新份额快照
            const latestSharesData = {};
            for (const [code, data] of Object.entries(fundData)) {
                latestSharesData[code] = parseFloat(data.shares) || 0;
            }

            const currentTableHTML = currentTable.innerHTML;
            const newTableInnerHTML = newTable.innerHTML;
            const hasTableChanges = newTableInnerHTML !== currentTableHTML;

            const currentSharesData = window.fundSharesData || {};
            const allShareKeys = new Set([...Object.keys(currentSharesData), ...Object.keys(latestSharesData)]);
            const hasSharesChanges = Array.from(allShareKeys).some(code => {
                const oldVal = parseFloat(currentSharesData[code] || 0);
                const newVal = parseFloat(latestSharesData[code] || 0);
                return oldVal !== newVal;
            });

            // 无新数据：仍需刷新份额缓存并重算汇总，确保首屏和日期标签可用
            if (!hasTableChanges && !hasSharesChanges) {
                window.fundSharesData = latestSharesData;
                if (typeof calculatePositionSummary === 'function') {
                    await calculatePositionSummary();
                }
                if (typeof autoColorize === 'function') {
                    autoColorize();
                }
                if (refreshBtn) {
                    refreshBtn.innerHTML = 'ℹ️ 无新数据';
                    setTimeout(() => {
                        refreshBtn.innerHTML = '🔄 刷新';
                        refreshBtn.disabled = false;
                        refreshBtn.style.background = '';
                    }, 1500);
                }
                return;
            }

            // 有变更才更新份额缓存和表格
            window.fundSharesData = latestSharesData;
            if (hasTableChanges) {
                currentTable.innerHTML = newTableInnerHTML;
            }

            // 刷新后默认折叠已展开的业绩/估值曲线
            const expandedChartRow = document.querySelector('tr.fund-chart-row');
            if (expandedChartRow) {
                expandedChartRow.remove();
            }
            if (window.fundRowChartInstance) {
                window.fundRowChartInstance.destroy();
                window.fundRowChartInstance = null;
            }
            window.currentFundChartState = null;

            // 4. 重新计算持仓统计（会自动使用新的表格数据 + 最新份额）
            if (typeof calculatePositionSummary === 'function') {
                await calculatePositionSummary();
                
                // 5. 重新着色
                if (typeof autoColorize === 'function') {
                    autoColorize();
                }
                
                // 记录刷新时间并更新显示
                lastRefreshTime = new Date();
                updateRefreshTimeDisplay('portfolio');
                
                // 显示成功提示（2秒后恢复）
                if (refreshBtn) {
                    refreshBtn.innerHTML = '✅ 更新完成';
                    
                    setTimeout(() => {
                        refreshBtn.innerHTML = '🔄 刷新';
                        refreshBtn.disabled = false;
                        refreshBtn.style.background = ''; // 恢复CSS样式
                    }, 2000);
                }
            } else {
                throw new Error('calculatePositionSummary function not found');
            }
        } catch (e) {
            console.error('Failed to refresh portfolio data:', e);
            if (refreshBtn) {
                refreshBtn.innerHTML = '❌ 更新失败';

                setTimeout(() => {
                    refreshBtn.innerHTML = '🔄 刷新';
                    refreshBtn.disabled = false;
                    refreshBtn.style.background = ''; // 恢复CSS样式
                }, 2000);
            }
        } finally {
            if (refreshBtn && refreshBtn.disabled) {
                setTimeout(() => {
                    if (!refreshBtn.disabled) return;
                    refreshBtn.disabled = false;
                    if (refreshBtn.innerHTML === '⏳ 更新中...') {
                        refreshBtn.innerHTML = '🔄 刷新';
                    }
                    refreshBtn.style.background = '';
                }, 3500);
            }
        }
    }

    // Market indices page data fetch
    async function fetchMarketIndicesData() {
        try {
            // Fetch global indices
            const indicesRes = await fetch('/api/indices/global');
            const indicesResult = await indicesRes.json();

            // Fetch volume data
            const volumeRes = await fetch('/api/indices/volume');
            const volumeResult = await volumeRes.json();

            if (indicesResult.success) {
                updateGlobalIndicesTable(indicesResult.data);
            }
            if (volumeResult.success) {
                updateVolumeChart(volumeResult.data);
            }

            autoColorize();
        } catch (e) {
            console.error('Failed to refresh market indices:', e);
        }
    }

    // Precious metals page data fetch
    async function fetchPreciousMetalsData() {
        let hasAnySuccess = false;
        const refreshBtn = document.getElementById('refreshBtn-metals');
        
        // 显示加载状态
        if (refreshBtn) {
            refreshBtn.disabled = true;
            refreshBtn.innerHTML = '⏳ 更新中...';
        }

        try {
            // Fetch real-time gold prices
            const realtimeRes = await fetch('/api/gold/real-time');
            const realtimeResult = await realtimeRes.json();

            // Fetch gold history
            const historyRes = await fetch('/api/gold/history');
            const historyResult = await historyRes.json();

            if (realtimeResult.success) {
                updateRealtimeGoldTable(realtimeResult.data);
                hasAnySuccess = true;
            }
            if (historyResult.success) {
                updateGoldHistoryTable(historyResult.data);
                hasAnySuccess = true;
            }

            autoColorize();
            
            // 只要至少有一部分数据更新成功，就显示成功
            if (hasAnySuccess) {
                // 记录刷新时间并更新显示
                lastRefreshTime = new Date();
                updateRefreshTimeDisplay('metals');
                
                // 显示成功提示（2秒后恢复）
                if (refreshBtn) {
                    refreshBtn.innerHTML = '✅ 更新完成';
                    
                    setTimeout(() => {
                        refreshBtn.innerHTML = '🔄 刷新';
                        refreshBtn.disabled = false;
                        refreshBtn.style.background = ''; // 恢复CSS样式
                    }, 2000);
                }
            } else {
                // 完全没有获取到任何数据
                throw new Error('Failed to fetch any precious metals data');
            }
        } catch (e) {
            console.error('Failed to refresh precious metals:', e);
            if (refreshBtn) {
                refreshBtn.innerHTML = '❌ 更新失败';

                setTimeout(() => {
                    refreshBtn.innerHTML = '🔄 刷新';
                    refreshBtn.disabled = false;
                    refreshBtn.style.background = ''; // 恢复CSS样式
                }, 2000);
            }
        }
    }

    // Sectors page data fetch
    async function fetchSectorsData() {
        try {
            // 获取两个 tab 中可能存在的刷新按钮
            const refreshBtn1 = document.getElementById('refreshBtn-sectors');
            const refreshBtn2 = document.getElementById('refreshBtn-sectors-query');
            
            // 显示加载状态 - 同时更新两个按钮
            if (refreshBtn1) {
                refreshBtn1.disabled = true;
                refreshBtn1.innerHTML = '⏳ 更新中...';
            }
            if (refreshBtn2) {
                refreshBtn2.disabled = true;
                refreshBtn2.innerHTML = '⏳ 更新中...';
            }

            // Fetch sectors data
            const sectorsRes = await fetch('/api/sectors');
            const sectorsResult = await sectorsRes.json();

            if (sectorsResult.success) {
                updateSectorsTable(sectorsResult.data);
            }

            autoColorize();
            
            // 记录刷新时间并更新显示
            lastRefreshTime = new Date();
            updateRefreshTimeDisplay('sectors');
            
            // 显示成功提示（2秒后恢复）- 同时更新两个按钮
            if (refreshBtn1) {
                refreshBtn1.innerHTML = '✅ 更新完成';
                refreshBtn1.style.background = 'var(--accent)';
            }
            if (refreshBtn2) {
                refreshBtn2.innerHTML = '✅ 更新完成';
                refreshBtn2.style.background = 'var(--accent)';
            }
            
            setTimeout(() => {
                if (refreshBtn1) {
                    refreshBtn1.innerHTML = '🔄 刷新';
                    refreshBtn1.disabled = false;
                    refreshBtn1.style.background = 'var(--accent)';  // 恢复到蓝色，不是白色
                }
                if (refreshBtn2) {
                    refreshBtn2.innerHTML = '🔄 刷新';
                    refreshBtn2.disabled = false;
                    refreshBtn2.style.background = 'var(--accent)';  // 恢复到蓝色，不是白色
                }
            }, 2000);
        } catch (e) {
            console.error('Failed to refresh sectors:', e);
            // 获取两个可能的按钮
            const refreshBtn1 = document.getElementById('refreshBtn-sectors');
            const refreshBtn2 = document.getElementById('refreshBtn-sectors-query');
            
            // 同时更新两个按钮的错误状态
            if (refreshBtn1) {
                refreshBtn1.innerHTML = '❌ 更新失败';
                refreshBtn1.style.background = 'var(--accent)';
            }
            if (refreshBtn2) {
                refreshBtn2.innerHTML = '❌ 更新失败';
                refreshBtn2.style.background = 'var(--accent)';
            }

            setTimeout(() => {
                if (refreshBtn1) {
                    refreshBtn1.innerHTML = '🔄 刷新';
                    refreshBtn1.disabled = false;
                    refreshBtn1.style.background = 'var(--accent)';  // 恢复到蓝色，不是白色
                }
                if (refreshBtn2) {
                    refreshBtn2.innerHTML = '🔄 刷新';
                    refreshBtn2.disabled = false;
                    refreshBtn2.style.background = 'var(--accent)';  // 恢复到蓝色，不是白色
                }
            }, 2000);
        }
    }

    // News page data fetch
    async function fetchNewsData() {
        try {
            const newsRes = await fetch('/api/news/7x24');
            const newsResult = await newsRes.json();

            if (newsResult.success) {
                updateNewsTable(newsResult.data);
            }

            autoColorize();
        } catch (e) {
            console.error('Failed to refresh news:', e);
        }
    }

    // Update functions (placeholders - to be implemented based on page structure)
    function updateTimingChart(data) {
        // Update timing chart if chart instance exists
        if (window.timingChartInstance && data.labels && data.labels.length > 0) {
            window.timingChartInstance.data.labels = data.labels;
            window.timingChartInstance.data.datasets[0].data = data.change_pcts || data.prices;
            window.timingChartInstance.update();

            // Update title
            const titleEl = document.getElementById('timingChartTitle');
            if (titleEl && data.current_price !== undefined) {
                const changePct = data.change_pct || 0;
                const color = changePct >= 0 ? '#f44336' : '#4caf50';
                titleEl.style.color = color;
                titleEl.innerHTML = '📉 上证分时 <span style="font-size:0.9em;">' +
                    (changePct >= 0 ? '+' : '') + changePct.toFixed(2) + '% (' +
                    data.current_price.toFixed(2) + ')</span>';
            }
        }
    }

    function updateGlobalIndicesTable(data) {
        // Find and update the global indices table
        const table = document.querySelector('.style-table');
        if (table && data) {
            const tbody = table.querySelector('tbody');
            if (tbody) {
                tbody.innerHTML = data.map(item => `
                    <tr>
                        <td>${item.name}</td>
                        <td>${item.value}</td>
                        <td>${item.change}</td>
                    </tr>
                `).join('');
            }
        }
    }

    function updateVolumeChart(data) {
        // Update volume chart if exists
        if (window.volumeChartInstance && data.labels && data.labels.length > 0) {
            window.volumeChartInstance.data.labels = data.labels;
            window.volumeChartInstance.data.datasets[0].data = data.total || [];
            window.volumeChartInstance.update();
        }
    }

    function updateRealtimeGoldTable(data) {
        // 在贵金属页面，表格在 .metal-card-realtime 下的 .metal-card-content 里
        const metalCard = document.querySelector('.metal-card-realtime');
        if (metalCard && data) {
            const table = metalCard.querySelector('.style-table');
            if (table) {
                const tbody = table.querySelector('tbody');
                if (tbody) {
                    tbody.innerHTML = data.map(item => `
                        <tr>
                            <td>${item.name}</td>
                            <td>${item.price}</td>
                            <td>${item.change_amount}</td>
                            <td>${item.change_pct}</td>
                            <td>${item.open_price}</td>
                            <td>${item.high_price}</td>
                            <td>${item.low_price}</td>
                            <td>${item.prev_close}</td>
                            <td>${item.update_time}</td>
                            <td>${item.unit}</td>
                        </tr>
                    `).join('');
                    // 更新后重新着色
                    autoColorize();
                }
            }
        }
    }

    function updateGoldHistoryTable(data) {
        // 更新历史金价表格，同时重新生成图表
        const metalCard = document.querySelector('.metal-card-history');
        if (metalCard && data) {
            const table = metalCard.querySelector('.style-table');
            if (table) {
                const tbody = table.querySelector('tbody');
                if (tbody) {
                    tbody.innerHTML = data.map(item => `
                        <tr>
                            <td>${item.date}</td>
                            <td>${item.china_gold_price}</td>
                            <td>${item.chow_tai_fook_price}</td>
                            <td>${item.china_gold_change}</td>
                            <td>${item.chow_tai_fook_change}</td>
                        </tr>
                    `).join('');
                }
            }
            
            // 重新生成图表
            recreateGoldChart(data);
        }
    }
    
    function recreateGoldChart(historyData) {
        if (!historyData || historyData.length === 0) return;
        
        const labels = [];
        const prices = [];
        
        historyData.forEach(item => {
            labels.push(item.date);
            prices.push(parseFloat(item.china_gold_price));
        });
        
        const ctx = document.getElementById('goldPriceChart');
        if (!ctx) return;
        
        // 销毁旧图表
        if (window.goldChartInstance) {
            window.goldChartInstance.destroy();
        }
        
        // 创建新图表
        const dataLabelPlugin = {
            id: 'dataLabelPlugin',
            afterDatasetsDraw(chart, args, options) {
                const { ctx } = chart;
                chart.data.datasets.forEach((dataset, datasetIndex) => {
                    const meta = chart.getDatasetMeta(datasetIndex);
                    meta.data.forEach((datapoint, index) => {
                        const value = dataset.data[index];
                        const x = datapoint.x;
                        const y = datapoint.y;

                        ctx.save();
                        ctx.fillStyle = '#f59e0b';
                        ctx.font = 'bold 11px sans-serif';
                        ctx.textAlign = 'center';
                        ctx.textBaseline = 'bottom';
                        ctx.fillText(value.toFixed(2), x, y - 5);
                        ctx.restore();
                    });
                });
            }
        };
        
        window.goldChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels.reverse(),
                datasets: [{
                    label: '金价 (元/克)',
                    data: prices.reverse(),
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245, 158, 11, 0.1)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 4,
                    pointBackgroundColor: '#f59e0b',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointHoverRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: {
                            color: '#9ca3af'
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            color: '#9ca3af'
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        }
                    },
                    y: {
                        ticks: {
                            color: '#9ca3af'
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        }
                    }
                }
            },
            plugins: [dataLabelPlugin]
        });
    }

    function updateSectorsTable(data) {
        // 行业板块页面的表格
        const table = document.querySelector('.style-table');
        if (table && data) {
            const tbody = table.querySelector('tbody');
            if (tbody) {
                tbody.innerHTML = data.map(item => `
                    <tr>
                        <td>${item.name}</td>
                        <td>${item.change}</td>
                        <td>${item.main_inflow}</td>
                        <td>${item.main_inflow_pct}</td>
                        <td>${item.small_inflow}</td>
                        <td>${item.small_inflow_pct}</td>
                    </tr>
                `).join('');
                // 更新后重新着色
                autoColorize();
            }
        }
    }

    function updateNewsTable(data) {
        const table = document.querySelector('.style-table');
        if (table && data) {
            const tbody = table.querySelector('tbody');
            if (tbody) {
                tbody.innerHTML = data.map(item => {
                    // 为利好/利空添加颜色类
                    let sourceClass = '';
                    if (item.source === '利好') {
                        sourceClass = 'positive';
                    } else if (item.source === '利空') {
                        sourceClass = 'negative';
                    }

                    return `
                    <tr>
                        <td>${item.time}</td>
                        <td class="${sourceClass}">${item.source}</td>
                        <td>${item.content}</td>
                    </tr>
                    `;
                }).join('');
            }
        }
    }

    // Page visibility detection - pause refresh when tab is hidden
    document.addEventListener('visibilitychange', function() {
        if (document.hidden) {
            stopAutoRefresh();
        } else {
            // 页面切回可见时仅恢复定时器，不做立即刷新，避免首屏/切页触发“自动点刷新”
            startAutoRefresh();
        }
    });

    // Portfolio 首页仅做轻量初始化，不在首屏强制触发完整刷新
    if (window.location.pathname === '/portfolio') {
        const todayLabel = getDayLabelFromDateKey(formatDateKey(new Date()));
        applyDailyGainLabels(todayLabel, todayLabel);
        initSummaryPanelsToggleByToolbarEstimate();
    }

    // Initialize refresh config and start auto-refresh on page load
    (async function() {
        await initRefreshConfig();
        startAutoRefresh();
    })();

    // Expose refresh function globally for manual refresh button
    window.refreshCurrentPage = refreshCurrentPage;
    window.initRefreshConfig = initRefreshConfig;

    // 切换敏感数值显示/隐藏（显示为****）
    function initSensitiveValuesToggle() {
        const toggleBtn = document.getElementById('toggleSensitiveValues');
        if (!toggleBtn) return;

        const positionSummary = document.getElementById('positionSummary');
        const fundDetailsTable = document.getElementById('fundDetailsTable');

        // 读取保存的状态
        const isHidden = localStorage.getItem('hideSensitiveValues') === 'true';
        if (isHidden) {
            if (positionSummary) positionSummary.classList.add('hide-values');
            if (fundDetailsTable) fundDetailsTable.classList.add('hide-values');
            toggleBtn.textContent = '😑';
        }

        toggleBtn.addEventListener('click', function() {
            const currentlyHidden = localStorage.getItem('hideSensitiveValues') === 'true';
            if (currentlyHidden) {
                if (positionSummary) positionSummary.classList.remove('hide-values');
                if (fundDetailsTable) fundDetailsTable.classList.remove('hide-values');
                localStorage.setItem('hideSensitiveValues', 'false');
                toggleBtn.textContent = '😀';
            } else {
                if (positionSummary) positionSummary.classList.add('hide-values');
                if (fundDetailsTable) fundDetailsTable.classList.add('hide-values');
                localStorage.setItem('hideSensitiveValues', 'true');
                toggleBtn.textContent = '😑';
            }
        });
    }

    // 初始化敏感数值显示/隐藏功能
    initSensitiveValuesToggle();

    // ==================== 炫耀卡片功能 ====================

    // 打开炫耀卡片
    window.openShowoffCard = function() {
        // 检查是否有持仓数据
        const totalValueEl = document.getElementById('totalValue');
        if (!totalValueEl) {
            alert('请先刷新页面加载数据');
            return;
        }

        const realValueText = totalValueEl.querySelector('.real-value')?.textContent || '';
        if (realValueText === '¥0.00' || realValueText === '') {
            alert('暂无持仓数据，无法生成炫耀卡片');
            return;
        }

        // 获取持仓统计数据
        const totalValue = parseFloat(realValueText.replace(/[¥,]/g, '')) || 0;

        const estimatedGainEl = document.getElementById('estimatedGain');
        const estimatedGainText = estimatedGainEl?.querySelector('.real-value')?.textContent || '¥0.00';
        const isEstNegative = estimatedGainEl?.querySelector('.sensitive-value')?.classList.contains('negative') ?? false;
        const estimatedGain = parseFloat(estimatedGainText.replace(/[¥,]/g, '')) * (isEstNegative ? -1 : 1) || 0;

        const actualGainEl = document.getElementById('actualGain');
        const actualGainText = actualGainEl?.querySelector('.real-value')?.textContent || '¥0.00';
        const isActNegative = actualGainEl?.querySelector('.sensitive-value')?.classList.contains('negative') ?? false;
        const actualGain = actualGainText.includes('净值') ? 0 :
            parseFloat(actualGainText.replace(/[¥,]/g, '')) * (isActNegative ? -1 : 1) || 0;

        // 格式化日期
        const today = new Date();
        const dateStr = today.getFullYear() + '-' +
            String(today.getMonth() + 1).padStart(2, '0') + '-' +
            String(today.getDate()).padStart(2, '0');

        // 更新卡片数据
        document.getElementById('showoffDate').textContent = dateStr;
        document.getElementById('showoffTotalValue').textContent =
            '¥' + totalValue.toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2});

        const estGainEl = document.getElementById('showoffEstimatedGain');
        const estMoneySign = estimatedGain < 0 ? '-' : '+';
        estGainEl.textContent = estMoneySign + '¥' + Math.abs(estimatedGain).toLocaleString('zh-CN',
            {minimumFractionDigits: 2, maximumFractionDigits: 2});
        estGainEl.className = 'summary-value ' + (estimatedGain >= 0 ? 'positive' : 'negative');

        const actGainEl = document.getElementById('showoffActualGain');
        const actMoneySign = actualGain < 0 ? '-' : '+';
        actGainEl.textContent = actualGainText.includes('净值') ? '净值未更新' :
            (actMoneySign + '¥' + Math.abs(actualGain).toLocaleString('zh-CN',
            {minimumFractionDigits: 2, maximumFractionDigits: 2}));
        actGainEl.className = 'summary-value ' + (actualGain > 0 ? 'positive' :
            (actualGain < 0 ? 'negative' : ''));

        // 获取Top3基金
        const top3Funds = getTop3Funds();
        renderTop3Funds(top3Funds);

        // 显示模态框
        document.getElementById('showoffModal').classList.add('active');
    };

    // 关闭炫耀卡片
    window.closeShowoffCard = function(event) {
        // 如果没有传入event，或者点击的是遮罩层/关闭按钮，则关闭
        if (!event || event.target.id === 'showoffModal' || event.target.classList.contains('showoff-close')) {
            document.getElementById('showoffModal').classList.remove('active');
        }
    };

    // 获取Top3基金（从已计算的数据中获取）
    function getTop3Funds() {
        // 尝试从全局变量获取基金明细数据
        if (window.fundDetailsData && window.fundDetailsData.length > 0) {
            // 按实际收益降序排序（如果有实际收益），否则按预估收益排序
            const sorted = [...window.fundDetailsData].sort((a, b) => {
                // 优先使用实际收益
                const aGain = a.actualGain !== 0 ? a.actualGain : a.estimatedGain;
                const bGain = b.actualGain !== 0 ? b.actualGain : b.estimatedGain;
                return bGain - aGain;
            });
            return sorted.slice(0, 3);
        }

        // 如果没有全局数据，返回空数组
        return [];
    }

    // 渲染Top3基金列表
    function renderTop3Funds(funds) {
        const container = document.getElementById('showoffFundsList');

        if (!funds || funds.length === 0) {
            container.innerHTML = '<div style="text-align: center; color: rgba(255,255,255,0.4); font-size: 13px;">暂无数据</div>';
            return;
        }

        container.innerHTML = funds.map((fund, index) => {
            // 优先使用实际收益，如果没有实际收益则使用预估收益
            const gain = fund.actualGain !== 0 ? fund.actualGain : (fund.estimatedGain || 0);
            const colorClass = gain >= 0 ? 'positive' : 'negative';

            return `
                <div class="fund-item">
                    <div class="fund-rank">${index + 1}</div>
                    <div class="fund-info">
                        <div class="fund-name">${fund.name}</div>
                    </div>
                    <div class="fund-gain ${colorClass}">¥${Math.abs(gain).toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
                </div>
            `;
        }).join('');
    }

    // 键盘ESC关闭
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const transactionModal = document.getElementById('transactionModal');
            if (transactionModal && transactionModal.classList.contains('active') && typeof window.closeTransactionModal === 'function') {
                window.closeTransactionModal();
                return;
            }
            closeShowoffCard();
        }
    });

});
