// Polyfill process for React libraries
window.process = {
    env: {
        NODE_ENV: 'production'
    }
};

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Auto Colorize
    autoColorize();

    // 基金表格“标记”列：点击五角星切换持有/取消持有（事件委托，动态内容也生效）
    if (!window._fundHoldStarListenerAdded) {
        window._fundHoldStarListenerAdded = true;
        document.body.addEventListener('click', async function(e) {
            const star = e.target.closest('.fund-hold-star');
            const codeCell = !star ? e.target.closest('.fund-code-cell') : null;
            const nameCell = !star && !codeCell ? e.target.closest('.fund-name-cell') : null;
            if (!star && !codeCell && !nameCell) return;
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

            // 基金编码点击：展开/收起当前行的业绩曲线
            if (codeCell && window.toggleFundRowChart) {
                const code = codeCell.dataset.code;
                window.toggleFundRowChart(code, 'performance', 'ONE_YEAR');
                return;
            }

            // 基金名称点击：展开/收起当前行的估值趋势图
            if (nameCell && window.toggleFundRowChart) {
                const code = nameCell.dataset.code;
                window.toggleFundRowChart(code);
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

    // 计算并显示持仓统计
    function calculatePositionSummary() {
        let totalValue = 0;
        let estimatedGain = 0;
        let actualGain = 0;
        let settledValue = 0;
        const today = new Date().toISOString().split('T')[0];

        // 存储每个基金的详细涨跌信息
        const fundDetailsData = [];

        // 遍历所有基金行
        const fundRows = document.querySelectorAll('.style-table tbody tr');
        fundRows.forEach(row => {
            const cells = row.querySelectorAll('td');
            if (cells.length < 6) return;

            // 获取基金代码（第一列）
            const codeCell = cells[0];
            const fundCode = codeCell.textContent.trim();

            // 从全局数据获取份额
            const shares = (window.fundSharesData && window.fundSharesData[fundCode]) || 0;
            if (shares <= 0) return;

            try {
                // 获取基金名称（第二列，索引1），使用 innerHTML 保留 HTML 标签（如板块标签样式）
                const fundName = cells[1].innerHTML.trim();

                // 解析净值 "1.234(2025-02-02)" (第四列，索引3)
                const netValueText = cells[3].textContent.trim();
                const netValueMatch = netValueText.match(/([0-9.]+)\(([0-9-]+)\)/);
                if (!netValueMatch) return;

                const netValue = parseFloat(netValueMatch[1]);
                let netValueDate = netValueMatch[2];

                // 处理净值日期格式：API可能返回"MM-DD"或"YYYY-MM-DD"
                // 如果是"MM-DD"格式，添加当前年份
                if (netValueDate.length === 5) {  // 格式为"MM-DD"
                    const currentYear = new Date().getFullYear();
                    netValueDate = `${currentYear}-${netValueDate}`;
                }

                // 解析估值增长率 (第五列，索引4)
                const estimatedGrowthText = cells[4].textContent.trim();
                const estimatedGrowth = estimatedGrowthText !== 'N/A' ?
                    parseFloat(estimatedGrowthText.replace('%', '')) : 0;

                // 解析日涨幅 (第六列，索引5)
                const dayGrowthText = cells[5].textContent.trim();
                const dayGrowth = dayGrowthText !== 'N/A' ?
                    parseFloat(dayGrowthText.replace('%', '')) : 0;

                // 计算持仓市值
                const positionValue = shares * netValue;
                totalValue += positionValue;

                // 计算预估涨跌（始终计算）
                const fundEstimatedGain = positionValue * estimatedGrowth / 100;
                estimatedGain += fundEstimatedGain;

                // 计算实际涨跌
                // 逻辑：只有当净值日期是今天时（今日净值已更新），才计算实际涨跌
                let fundActualGain = 0;
                if (netValueDate === today) {
                    // 今日净值已更新，计算实际收益
                    fundActualGain = positionValue * dayGrowth / 100;
                    actualGain += fundActualGain;
                    settledValue += positionValue;
                }

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
                    actualGain: fundActualGain,
                    actualGainPct: netValueDate === today ? dayGrowth : 0,
                    sectors: sectors
                });
            } catch (e) {
                console.warn('解析基金数据失败:', fundCode, e);
            }
        });

        // 保存基金明细数据到全局变量，供炫耀卡片使用
        window.fundDetailsData = fundDetailsData;

        // 显示或隐藏持仓统计区域 (旧版布局)
        const summaryDiv = document.getElementById('positionSummary');
        if (summaryDiv && totalValue > 0) {
            summaryDiv.style.display = 'block';
        } else if (summaryDiv) {
            summaryDiv.style.display = 'none';
        }

        // 更新持仓基金页面的汇总数据 (始终执行)
        // 更新总持仓金额
        const totalValueEl = document.getElementById('totalValue');
        if (totalValueEl) {
            totalValueEl.className = 'sensitive-value';
            const realValueSpan = totalValueEl.querySelector('.real-value');
            if (realValueSpan) {
                realValueSpan.textContent = '¥' + totalValue.toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
            }
        }

        // 更新今日预估
        const estimatedGainEl = document.getElementById('estimatedGain');
        const estimatedGainPctEl = document.getElementById('estimatedGainPct');
        if (estimatedGainEl && estimatedGainPctEl) {
            const estGainPct = totalValue > 0 ? (estimatedGain / totalValue * 100) : 0;
            const estSign = estimatedGain >= 0 ? '+' : '';
            const sensitiveSpan = estimatedGainEl.querySelector('.sensitive-value');
            if (sensitiveSpan) {
                sensitiveSpan.className = estimatedGain >= 0 ? 'sensitive-value positive' : 'sensitive-value negative';
            }
            const realValueSpan = estimatedGainEl.querySelector('.real-value');
            if (realValueSpan) {
                realValueSpan.textContent = `${estSign}¥${Math.abs(estimatedGain).toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            }
            estimatedGainPctEl.textContent = ` (${estSign}${estGainPct.toFixed(2)}%)`;
            estimatedGainPctEl.style.color = estimatedGain >= 0 ? '#f44336' : '#4caf50';
        }

        // 更新今日实际（只有当有基金净值更新至今日时才显示数值）
        const actualGainEl = document.getElementById('actualGain');
        const actualGainPctEl = document.getElementById('actualGainPct');
        if (actualGainEl && actualGainPctEl) {
            if (settledValue > 0) {
                const actGainPct = (actualGain / settledValue * 100);
                const actSign = actualGain >= 0 ? '+' : '';
                const sensitiveSpan = actualGainEl.querySelector('.sensitive-value');
                if (sensitiveSpan) {
                    sensitiveSpan.className = actualGain >= 0 ? 'sensitive-value positive' : 'sensitive-value negative';
                }
                const realValueSpan = actualGainEl.querySelector('.real-value');
                if (realValueSpan) {
                    realValueSpan.textContent = `${actSign}¥${Math.abs(actualGain).toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
                }
                actualGainPctEl.textContent = ` (${actSign}${actGainPct.toFixed(2)}%)`;
                actualGainPctEl.style.color = actualGain >= 0 ? '#f44336' : '#4caf50';
            } else {
                const sensitiveSpan = actualGainEl.querySelector('.sensitive-value');
                if (sensitiveSpan) {
                    sensitiveSpan.className = 'sensitive-value';
                }
                const realValueSpan = actualGainEl.querySelector('.real-value');
                if (realValueSpan) {
                    realValueSpan.textContent = '净值未更新';
                }
                actualGainPctEl.textContent = '';
            }
        }

        // 更新持仓数量
        const holdCountEl = document.getElementById('holdCount');
        if (holdCountEl) {
            // 从全局数据计算持仓数量
            let heldCount = 0;
            if (window.fundSharesData) {
                for (const code in window.fundSharesData) {
                    if (window.fundSharesData[code] > 0) {
                        heldCount++;
                    }
                }
            }
            holdCountEl.textContent = heldCount + ' 只';
        }

        // 填充分基金明细表格
        const fundDetailsDiv = document.getElementById('fundDetailsSummary');
        if (fundDetailsDiv && fundDetailsData.length > 0) {
            fundDetailsDiv.style.display = 'block';
            const tableBody = document.getElementById('fundDetailsTableBody');
            if (tableBody) {
                tableBody.innerHTML = fundDetailsData.map(fund => {
                    const estColor = fund.estimatedGain >= 0 ? '#f44336' : '#4caf50';
                    const actColor = fund.actualGain >= 0 ? '#f44336' : '#4caf50';
                    const estSign = fund.estimatedGain >= 0 ? '+' : '';
                    const actSign = fund.actualGain >= 0 ? '+' : '';
                    // 基金名称中已包含板块标签，不再重复添加
                    return `
                        <tr style="border-bottom: 1px solid var(--border);">
                            <td style="padding: 10px; text-align: center; vertical-align: middle; color: var(--accent); font-weight: 500;">${fund.code}</td>
                            <td style="padding: 10px; text-align: center; vertical-align: middle; color: var(--text-main); white-space: nowrap; min-width: 120px;">${fund.name}</td>
                            <td class="sensitive-value" style="padding: 10px; text-align: center; vertical-align: middle; font-family: var(--font-mono);"><span class="real-value">${fund.shares.toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span><span class="hidden-value">****</span></td>
                            <td class="sensitive-value" style="padding: 10px; text-align: center; vertical-align: middle; font-family: var(--font-mono); font-weight: 600;"><span class="real-value">¥${fund.positionValue.toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span><span class="hidden-value">****</span></td>
                            <td class="sensitive-value ${estColor === '#f44336' ? 'positive' : 'negative'}" style="padding: 10px; text-align: center; vertical-align: middle; font-family: var(--font-mono); color: ${estColor}; font-weight: 500;"><span class="real-value">¥${Math.abs(fund.estimatedGain).toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span><span class="hidden-value">****</span></td>
                            <td class="${estColor === '#f44336' ? 'positive' : 'negative'}" style="padding: 10px; text-align: center; vertical-align: middle; font-family: var(--font-mono); color: ${estColor}; font-weight: 500;">${estSign}${fund.estimatedGainPct.toFixed(2)}%</td>
                            <td class="sensitive-value ${actColor === '#f44336' ? 'positive' : 'negative'}" style="padding: 10px; text-align: center; vertical-align: middle; font-family: var(--font-mono); color: ${actColor}; font-weight: 500;"><span class="real-value">¥${Math.abs(fund.actualGain).toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span><span class="hidden-value">****</span></td>
                            <td class="${actColor === '#f44336' ? 'positive' : 'negative'}" style="padding: 10px; text-align: center; vertical-align: middle; font-family: var(--font-mono); color: ${actColor}; font-weight: 500;">${actSign}${fund.actualGainPct.toFixed(2)}%</td>
                        </tr>
                    `;
                }).join('');
            }
        } else if (fundDetailsDiv) {
            fundDetailsDiv.style.display = 'none';
        }

        // Update new summary bar if it exists (sidebar layout)
        const summaryBar = document.getElementById('summaryBar');
        if (summaryBar) {
            // Count held funds from global data
            let heldCount = 0;
            if (window.fundSharesData) {
                for (const code in window.fundSharesData) {
                    if (window.fundSharesData[code] > 0) {
                        heldCount++;
                    }
                }
            }

            // Update total value
            const summaryTotalValue = document.getElementById('summaryTotalValue');
            if (summaryTotalValue) {
                summaryTotalValue.textContent = '¥' + totalValue.toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
            }

            // Update total change
            const summaryTotalChange = document.getElementById('summaryTotalChange');
            if (summaryTotalChange) {
                const totalPct = totalValue > 0 ? ((estimatedGain + actualGain) / totalValue * 100) : 0;
                const totalSign = (estimatedGain + actualGain) >= 0 ? '+' : '';
                summaryTotalChange.textContent = `${totalSign}${totalPct.toFixed(2)}%`;
                summaryTotalChange.className = 'summary-change ' + ((estimatedGain + actualGain) >= 0 ? 'positive' : 'negative');
            }

            // Update estimated gain
            const summaryEstGain = document.getElementById('summaryEstGain');
            if (summaryEstGain) {
                const estSign = estimatedGain >= 0 ? '+' : '';
                summaryEstGain.textContent = `${estSign}¥${Math.abs(estimatedGain).toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            }

            // Update estimated change
            const summaryEstChange = document.getElementById('summaryEstChange');
            if (summaryEstChange) {
                const estGainPct = totalValue > 0 ? (estimatedGain / totalValue * 100) : 0;
                const estSign = estimatedGain >= 0 ? '+' : '';
                summaryEstChange.textContent = `${estSign}${estGainPct.toFixed(2)}%`;
                summaryEstChange.className = 'summary-change ' + (estimatedGain >= 0 ? 'positive' : 'negative');
            }

            // Update actual gain
            const summaryActualGain = document.getElementById('summaryActualGain');
            if (summaryActualGain) {
                const actSign = actualGain >= 0 ? '+' : '';
                summaryActualGain.textContent = `${actSign}¥${Math.abs(actualGain).toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            }

            // Update actual change
            const summaryActualChange = document.getElementById('summaryActualChange');
            if (summaryActualChange) {
                if (settledValue > 0) {
                    const actGainPct = (actualGain / settledValue * 100);
                    const actSign = actualGain >= 0 ? '+' : '';
                    summaryActualChange.textContent = `${actSign}${actGainPct.toFixed(2)}%`;
                    summaryActualChange.className = 'summary-change ' + (actualGain >= 0 ? 'positive' : 'negative');
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
    window.downloadFundMap = downloadFundMap;
    window.uploadFundMap = uploadFundMap;
    window.addFunds = addFunds;
    window.markHold = markHold;
    window.unmarkHold = unmarkHold;
    window.deleteFunds = deleteFunds;
    window.openSectorModal = openSectorModal;
    window.closeSectorModal = closeSectorModal;
    window.confirmSector = confirmSector;
    window.removeSector = removeSector;

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
                // 更新全局存储
                if (!window.fundSharesData) {
                    window.fundSharesData = {};
                }
                window.fundSharesData[currentSharesFundCode] = shares;

                // 更新按钮状态
                updateSharesButton(currentSharesFundCode, shares);

                // 重新计算持仓统计
                calculatePositionSummary();

                // 关闭弹窗
                window.closeSharesModal();

                alert(result.message);
            } else {
                alert(result.message);
            }
        } catch (e) {
            alert('设置份额失败: ' + e.message);
        }
    };

    // 全局暴露份额相关函数
    window.openSharesModal = openSharesModal;
    window.closeSharesModal = closeSharesModal;
    window.confirmShares = confirmShares;
    window.getFundShares = getFundShares;

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
        try {
            const refreshBtn = document.getElementById('refreshBtn-portfolio');
            
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

            // 无新数据：不替换表格、不更新时间
            if (!hasTableChanges && !hasSharesChanges) {
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

            // 如果之前有展开的趋势图，刷新后自动还原
            if (window.currentFundChartState && window.toggleFundRowChart) {
                const chartState = { ...window.currentFundChartState };
                window.currentFundChartState = null;
                window.toggleFundRowChart(
                    chartState.code,
                    chartState.type,
                    chartState.interval || 'ONE_YEAR',
                    { forceOpen: true }
                );
            }

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

            const refreshBtn = document.getElementById('refreshBtn-portfolio');
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
            // Immediate refresh when tab becomes visible
            refreshCurrentPage();
            startAutoRefresh();
        }
    });

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
        estGainEl.textContent = '¥' + Math.abs(estimatedGain).toLocaleString('zh-CN',
            {minimumFractionDigits: 2, maximumFractionDigits: 2});
        estGainEl.className = 'summary-value ' + (estimatedGain >= 0 ? 'positive' : 'negative');

        const actGainEl = document.getElementById('showoffActualGain');
        actGainEl.textContent = actualGainText.includes('净值') ? '净值未更新' :
            ('¥' + Math.abs(actualGain).toLocaleString('zh-CN',
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
            closeShowoffCard();
        }
    });

});
