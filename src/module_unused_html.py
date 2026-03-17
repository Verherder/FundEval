from .module_html import *

def get_market_page_html(market_data, username=None):
    """生成市场行情页面 - 使用卡片/图表布局"""
    css_style = get_css_style()

    # 生成市场数据卡片
    market_cards = ''
    for key, data in market_data.items():
        card_id = "card-{}".format(key)
        icon = get_market_icon(key)
        market_cards += '''
        <div class="market-card" id="{card_id}">
            <div class="market-card-header">
                <h3 class="market-card-title">
                    <span class="card-icon">{icon}</span>
                    {title}
                </h3>
                <button class="card-toggle" onclick="toggleCard('{card_id}')">
                    <span>▼</span>
                </button>
            </div>
            <div class="market-card-content">
                {content}
            </div>
        </div>
        '''.format(card_id=card_id, icon=icon, title=data['title'], content=data['content'])

    username_display = '<a href="https://github.com/lanZzV/fund" target="_blank" class="nav-star">点个赞</a>'
    username_display += '<a href="https://github.com/lanZzV/fund/issues" target="_blank" class="nav-feedback">反馈</a>'
    if username:
        username_display += '<span class="nav-user">🍎 {username}</span>'.format(username=username)
        username_display += '<a href="/logout" class="nav-logout">退出登录</a>'

    html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>市场行情 - LanFund</title>
    <link rel="icon" href="/static/1.ico">
    {css_style}
    <link rel="stylesheet" href="/static/css/style.css">
    <style>
        body {{
            background-color: var(--terminal-bg);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }}

        /* 顶部导航栏 */
        .top-navbar {{
            background-color: var(--card-bg);
            color: var(--text-main);
            padding: 0.8rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
        }}

        .top-navbar-brand {{
            display: flex;
            align-items: center;
            flex: 0 0 auto;
        }}

        .top-navbar-quote {{
            flex: 1;
            text-align: center;
            font-size: 1rem;
            font-weight: 500;
            color: var(--text-main);
            font-style: italic;
            padding: 0 2rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            letter-spacing: 0.05em;
            transition: opacity 0.5s ease-in-out;
        }}

        .top-navbar-menu {{
            display: flex;
            gap: 1rem;
            align-items: center;
        }}

        .nav-user {{
            color: #3b82f6;
            font-weight: 500;
        }}

        .nav-logout {{
            color: #f85149;
            text-decoration: none;
            font-weight: 500;
        }}

        .nav-star {{
            color: #e3b341;
            text-decoration: none;
            font-weight: 500;
        }}

        .nav-star:hover {{
            color: #f2c94c;
        }}

        .nav-feedback {{
            color: #8b949e;
            text-decoration: none;
            font-weight: 500;
        }}

        .nav-feedback:hover {{
            color: #58a6ff;
        }}

        /* 主容器 */
        .main-container {{
            display: flex;
            flex: 1;
        }}

        /* 内容区域 */
        .content-area {{
            flex: 1;
            padding: 30px;
            overflow-y: auto;
        }}

        .page-header {{
            margin-bottom: 30px;
            text-align: center;
        }}

        .page-header h1 {{
            font-size: 2rem;
            font-weight: 700;
            margin: 0;
            border: none;
            text-decoration: none;
            background: linear-gradient(135deg, var(--accent), var(--down));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .page-header p {{
            color: var(--text-dim);
            margin-top: 10px;
            border: none;
            text-decoration: none;
        }}

        /* 市场行情网格布局 */
        .market-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            max-width: 1600px;
            margin: 0 auto;
        }}

        @media (max-width: 1200px) {{
            .market-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        /* 市场卡片 */
        .market-card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
            transition: all 0.3s ease;
        }}

        .market-card:hover {{
            border-color: var(--accent);
            box-shadow: 0 4px 20px rgba(59, 130, 246, 0.15);
        }}

        .market-card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 20px;
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
            border-bottom: 1px solid var(--border);
            cursor: pointer;
            user-select: none;
        }}

        .market-card-title {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin: 0;
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--text-main);
        }}

        .card-icon {{
            font-size: 1.3rem;
        }}

        .card-toggle {{
            background: none;
            border: none;
            color: var(--text-dim);
            cursor: pointer;
            padding: 4px 8px;
            transition: transform 0.3s ease;
        }}

        .card-toggle.collapsed {{
            transform: rotate(-90deg);
        }}

        .market-card-content {{
            padding: 20px;
            max-height: 600px;
            overflow-y: auto;
            transition: all 0.3s ease;
            opacity: 1;
        }}

        /* 折叠状态：内容隐藏 */
        .market-card.collapsed .market-card-content {{
            display: none;
        }}

        /* 折叠状态：卡片收缩 */
        .market-card.collapsed {{
            max-height: 60px;
        }}

        /* 滚动条样式 */
        .market-card-content::-webkit-scrollbar {{
            width: 8px;
        }}

        .market-card-content::-webkit-scrollbar-track {{
            background: var(--terminal-bg);
        }}

        .market-card-content::-webkit-scrollbar-thumb {{
            background: var(--border);
            border-radius: 4px;
        }}

        .market-card-content::-webkit-scrollbar-thumb:hover {{
            background: var(--accent);
        }}

        @media (max-width: 768px) {{
            .main-container {{
                flex-direction: column;
            }}

            .sidebar {{
                width: 100%;
                border-right: none;
                border-bottom: 1px solid var(--border);
                padding: 10px 0;
            }}

            .sidebar-item {{
                padding: 10px 15px;
                font-size: 0.9rem;
            }}

            .content-area {{
                padding: 15px;
            }}

            /* 顶部导航栏两行布局 */
            .top-navbar {{
                flex-direction: row;
                flex-wrap: wrap;
                height: auto;
                padding: 0.5rem 1rem;
                align-items: center;
                border-bottom: none;
            }}

            .top-navbar > .top-navbar-brand {{
                order: 1;
                flex: 0 0 auto;
                padding-bottom: 0.5rem;
                border-bottom: 1px solid var(--border);
            }}

            .top-navbar-menu {{
                order: 1;
                flex: 0 0 auto;
                margin-left: auto;
                padding-bottom: 0.5rem;
                border-bottom: 1px solid var(--border);
            }}

            .top-navbar-quote {{
                order: 2;
                width: 100%;
                flex-basis: 100%;
                text-align: center;
                padding: 0.5rem 0;
                font-size: 0.8rem;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                border-top: 1px solid var(--border);
                margin-top: 0.5rem;
            }}
        }}
    </style>
</head>
<body>
    <!-- 顶部导航栏 -->
    <nav class="top-navbar">
        <div class="top-navbar-brand">
            <img src="/static/1.ico" alt="Logo" class="navbar-logo">
        </div>
        <div class="top-navbar-quote" id="lyricsDisplay">
            偶然与巧合, 舞动了蝶翼, 谁的心头风起 ————《如果我们不曾相遇》
        </div>
        <div class="top-navbar-menu">
            {username_display}
        </div>
    </nav>

    <!-- 主容器 -->
    <div class="main-container">
        <!-- 汉堡菜单按钮 (移动端) -->
        <button class="hamburger-menu" id="hamburgerMenu">
            <span></span>
            <span></span>
            <span></span>
        </button>

        <!-- 左侧导航栏 -->
        <div class="sidebar collapsed" id="sidebar">
            <div class="sidebar-toggle" id="sidebarToggle">▶</div>
            <a href="/market" class="sidebar-item active">
                <span class="sidebar-icon">📰</span>
                <span>7*24快讯</span>
            </a>
            <a href="/market-indices" class="sidebar-item">
                <span class="sidebar-icon">📊</span>
                <span>市场指数</span>
            </a>
            <a href="/precious-metals" class="sidebar-item">
                <span class="sidebar-icon">🪙</span>
                <span>贵金属行情</span>
            </a>
            <a href="/portfolio" class="sidebar-item">
                <span class="sidebar-icon">💼</span>
                <span>持仓基金</span>
            </a>
            <a href="/sectors" class="sidebar-item">
                <span class="sidebar-icon">🏢</span>
                <span>行业板块</span>
            </a>
        </div>

        <!-- 内容区域 -->
        <div class="content-area">
            <!-- 页面标题 -->
            <div class="page-header">
                <h1>📊 市场行情</h1>
                <p>实时追踪全球市场动态</p>
            </div>

            <!-- 市场数据网格 -->
            <div class="market-grid">
                {market_cards}
            </div>
        </div>
    </div>

    <script>
        function toggleCard(cardId) {{
            const card = document.getElementById(cardId);
            const toggle = card.querySelector('.card-toggle');
            card.classList.toggle('collapsed');
            toggle.classList.toggle('collapsed');
        }}

        // 自动颜色化
        function autoColorize() {{
            const cells = document.querySelectorAll('.style-table td');
            cells.forEach(cell => {{
                const text = cell.textContent.trim();
                const cleanText = text.replace(/[%,亿万手]/g, '');
                const val = parseFloat(cleanText);

                if (!isNaN(val)) {{
                    if (text.includes('%') || text.includes('涨跌')) {{
                        if (text.includes('-')) {{
                            cell.classList.add('negative');
                        }} else if (val > 0) {{
                            cell.classList.add('positive');
                        }}
                    }} else if (text.startsWith('-')) {{
                        cell.classList.add('negative');
                    }} else if (text.startsWith('+')) {{
                        cell.classList.add('positive');
                    }}
                }}
            }});
        }}

        document.addEventListener('DOMContentLoaded', function() {{
            autoColorize();
        }});
    </script>
    <script src="/static/js/main.js"></script>
    <script>
        // 歌词轮播
        (function() {{
            const lyrics = [
                "偶然与巧合, 舞动了蝶翼, 谁的心头风起 ————《如果我们不曾相遇》",
                "如海上的浪花, 如深海的鱼, 浪与鱼相依 ————《鱼仔》",
                "阳光下的泡沫, 是彩色的, 一触就破 ————《泡沫》",
                "如果我变成回忆, 退出了这场生命 ————《如果我变成回忆》"
            ];
            let currentIndex = 0;
            const lyricsElement = document.getElementById('lyricsDisplay');

            function rotateLyrics() {{
                if (!lyricsElement) return;
                lyricsElement.style.opacity = '0';
                setTimeout(() => {{
                    currentIndex = (currentIndex + 1) % lyrics.length;
                    lyricsElement.textContent = lyrics[currentIndex];
                    lyricsElement.style.opacity = '1';
                }}, 500);
            }}

            setInterval(rotateLyrics, 10000);
        }})();
    </script>
</body>
</html>'''.format(css_style=css_style, username_display=username_display, market_cards=market_cards)
    return html


def get_news_page_html(news_content, username=None):
    """生成7*24快讯页面 - 简洁布局"""
    css_style = get_css_style()

    username_display = '<a href="https://github.com/lanZzV/fund" target="_blank" class="nav-star">点个赞</a>'
    username_display += '<a href="https://github.com/lanZzV/fund/issues" target="_blank" class="nav-feedback">反馈</a>'
    if username:
        username_display += '<span class="nav-user">🍎 {username}</span>'.format(username=username)
        username_display += '<a href="/logout" class="nav-logout">退出登录</a>'

    html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>7*24快讯 - LanFund</title>
    <link rel="icon" href="/static/1.ico">
    {css_style}
    <link rel="stylesheet" href="/static/css/style.css">
    <style>
        body {{
            background-color: var(--terminal-bg);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }}

        /* 顶部导航栏 */
        .top-navbar {{
            background-color: var(--card-bg);
            color: var(--text-main);
            padding: 0.8rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
        }}

        .top-navbar-brand {{
            display: flex;
            align-items: center;
            flex: 0 0 auto;
        }}

        .navbar-logo {{
            width: 32px;
            height: 32px;
        }}

        .top-navbar-quote {{
            flex: 1;
            text-align: center;
            font-size: 1rem;
            font-weight: 500;
            color: var(--text-main);
            font-style: italic;
            padding: 0 2rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            letter-spacing: 0.05em;
            transition: opacity 0.5s ease-in-out;
        }}

        .top-navbar-menu {{
            display: flex;
            gap: 1rem;
            align-items: center;
        }}

        .nav-logout {{
            color: #f85149;
            text-decoration: none;
            font-weight: 500;
        }}

        .nav-star {{
            color: #e3b341;
            text-decoration: none;
            font-weight: 500;
        }}

        .nav-star:hover {{
            color: #f2c94c;
        }}

        .nav-feedback {{
            color: #8b949e;
            text-decoration: none;
            font-weight: 500;
        }}

        .nav-feedback:hover {{
            color: #58a6ff;
        }}

        .nav-user {{
            color: #3b82f6;
            font-weight: 500;
        }}

        /* 主容器 */
        .main-container {{
            display: flex;
            flex: 1;
        }}

        /* 内容区域 */
        .content-area {{
            flex: 1;
            padding: 20px;
            overflow-y: auto;
        }}

        /* 隐藏滚动条但保留功能 */
        ::-webkit-scrollbar {{
            width: 6px;
            height: 6px;
        }}

        ::-webkit-scrollbar-track {{
            background: transparent;
        }}

        ::-webkit-scrollbar-thumb {{
            background: rgba(255, 255, 255, 0.1);
            border-radius: 3px;
        }}

        ::-webkit-scrollbar-thumb:hover {{
            background: rgba(255, 255, 255, 0.2);
        }}

        /* Firefox */
        * {{
            scrollbar-width: thin;
            scrollbar-color: rgba(255, 255, 255, 0.1) transparent;
        }}

        .page-header {{
            margin-bottom: 20px;
        }}

        .page-header h1 {{
            font-size: 1.8rem;
            margin: 0;
            color: var(--text-main);
        }}

        .page-header p {{
            margin: 5px 0 0;
            color: var(--text-dim);
        }}

        /* 快讯内容 */
        .news-content {{
            background-color: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 20px;
            max-height: calc(100vh - 200px);
            overflow-y: auto;
        }}

        /* 响应式设计 */
        @media (max-width: 768px) {{
            /* 汉堡菜单显示 */
            .hamburger-menu {{
                display: flex !important;
            }}

            .content-area {{
                padding: 15px;
            }}

            /* 顶部导航栏两行布局 */
            .top-navbar {{
                flex-direction: row;
                flex-wrap: wrap;
                height: auto;
                padding: 0.5rem 1rem;
                align-items: center;
                border-bottom: none;
            }}

            .top-navbar > .top-navbar-brand {{
                order: 1;
                flex: 0 0 auto;
                padding-bottom: 0.5rem;
                border-bottom: 1px solid var(--border);
            }}

            .top-navbar-menu {{
                order: 1;
                flex: 0 0 auto;
                margin-left: auto;
                padding-bottom: 0.5rem;
                border-bottom: 1px solid var(--border);
            }}

            .top-navbar-quote {{
                order: 2;
                width: 100%;
                flex-basis: 100%;
                text-align: center;
                padding: 0.5rem 0;
                font-size: 0.8rem;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                border-top: 1px solid var(--border);
                margin-top: 0.5rem;
            }}
        }}
    </style>
</head>
<body>
    <!-- 顶部导航栏 -->
    <nav class="top-navbar">
        <div class="top-navbar-brand">
            <img src="/static/1.ico" alt="Logo" class="navbar-logo">
        </div>
        <div class="top-navbar-quote" id="lyricsDisplay">
            偶然与巧合, 舞动了蝶翼, 谁的心头风起 ————《如果我们不曾相遇》
        </div>
        <div class="top-navbar-menu">
            {username_display}
        </div>
    </nav>

    <!-- 主容器 -->
    <div class="main-container">
        <!-- 汉堡菜单按钮 (移动端) -->
        <button class="hamburger-menu" id="hamburgerMenu">
            <span></span>
            <span></span>
            <span></span>
        </button>

        <!-- 左侧导航栏 -->
        <div class="sidebar collapsed" id="sidebar">
            <div class="sidebar-toggle" id="sidebarToggle">▶</div>
            <a href="/precious-metals" class="sidebar-item">
                <span class="sidebar-icon">🪙</span>
                <span>贵金属行情</span>
            </a>
            <a href="/portfolio" class="sidebar-item">
                <span class="sidebar-icon">💼</span>
                <span>持仓基金</span>
            </a>
            <a href="/sectors" class="sidebar-item">
                <span class="sidebar-icon">🏢</span>
                <span>行业板块</span>
            </a>
        </div>

        <!-- 内容区域 -->
        <div class="content-area">
            <!-- 页面标题 -->
            <div class="page-header">
                <h1 style="display: flex; align-items: center;">
                    📰 7*24快讯
                    <button id="refreshBtn" onclick="refreshCurrentPage()" class="refresh-button" style="margin-left: 15px; padding: 8px 16px; background: var(--accent); color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem; font-weight: 500; transition: all 0.2s ease; display: inline-flex; align-items: center; gap: 5px;">🔄 刷新</button>
                </h1>
                <p>实时追踪全球市场动态</p>
            </div>

            <!-- 快讯内容 -->
            <div class="news-content">
                {news_content}
            </div>
        </div>
    </div>

    <script src="/static/js/main.js"></script>
    <script src="/static/js/sidebar-nav.js"></script>
    <script>
        // 自动颜色化
        function autoColorize() {{
            const elements = document.querySelectorAll('[data-change]');
            elements.forEach(function(el) {{
                const change = parseFloat(el.getAttribute('data-change'));
                if (change > 0) {{
                    el.style.color = '#f44336';
                }} else if (change < 0) {{
                    el.style.color = '#4caf50';
                }}
            }});
        }}

        document.addEventListener('DOMContentLoaded', function() {{
            // 歌词轮播
            const lyrics = [
                '总要有一首我的歌, 大声唱过, 再看天地辽阔 ————《一颗苹果》',
                '苍狗又白云, 身旁有了你, 匆匆轮回又有何惧 ————《如果我们不曾相遇》',
                '活着其实很好, 再吃一颗苹果 ————《一颗苹果》',
                '偶然与巧合, 舞动了蝶翼, 谁的心头风起 ————《如果我们不曾相遇》'
            ];
            let currentLyricIndex = 0;
            const lyricsElement = document.getElementById('lyricsDisplay');

            // 随机选择初始歌词
            currentLyricIndex = Math.floor(Math.random() * lyrics.length);
            if (lyricsElement) {{
                lyricsElement.textContent = lyrics[currentLyricIndex];

                // 每10秒切换一次歌词
                setInterval(function() {{
                    // 淡出
                    lyricsElement.style.opacity = '0';

                    setTimeout(function() {{
                        // 切换歌词
                        currentLyricIndex = (currentLyricIndex + 1) % lyrics.length;
                        lyricsElement.textContent = lyrics[currentLyricIndex];

                        // 淡入
                        lyricsElement.style.opacity = '1';
                    }}, 500);
                }}, 10000);
            }}

            autoColorize();
        }});
    </script>
</body>
</html>'''.format(css_style=css_style, username_display=username_display, news_content=news_content)
    return html


def get_market_indices_page_html(market_charts=None, chart_data=None, timing_data=None, username=None):
    """生成市场指数页面 - 上证分时、全球指数和成交量趋势"""
    css_style = get_css_style()
    import json

    username_display = '<a href="https://github.com/lanZzV/fund" target="_blank" class="nav-star">点个赞</a>'
    username_display += '<a href="https://github.com/lanZzV/fund/issues" target="_blank" class="nav-feedback">反馈</a>'
    if username:
        username_display += '<span class="nav-user">🍎 {username}</span>'.format(username=username)
        username_display += '<a href="/logout" class="nav-logout">退出登录</a>'

    # 准备图表数据JSON (optional, for future chart enhancements)
    indices_data_json = json.dumps(chart_data.get('indices', {'labels': [], 'prices': [], 'changes': []}) if chart_data else {'labels': [], 'prices': [], 'changes': []})
    volume_data_json = json.dumps(chart_data.get('volume', {'labels': [], 'total': [], 'sh': [], 'sz': [], 'bj': []}) if chart_data else {'labels': [], 'total': [], 'sh': [], 'sz': [], 'bj': []})

    # 准备上证分时数据JSON
    timing_data_json = json.dumps(timing_data if timing_data else {'labels': [], 'prices': [], 'change_pcts': [], 'change_amounts': [], 'volumes': [], 'amounts': []})

    # 生成市场指数HTML - 两行布局
    market_content = '''
        <!-- 市场指数区域 -->
        <div class="market-indices-section" style="padding: 30px;">
            <div class="page-header" style="margin-bottom: 25px;">
                <h1 style="font-size: 1.5rem; font-weight: 600; margin: 0; color: var(--text-main); display: flex; align-items: center;">
                    📊 市场指数
                    <button id="refreshBtn" onclick="refreshCurrentPage()" class="refresh-button" style="margin-left: 15px; padding: 8px 16px; background: var(--accent); color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem; font-weight: 500; transition: all 0.2s ease; display: inline-flex; align-items: center; gap: 5px;">🔄 刷新</button>
                </h1>
            </div>

            <!-- 第一行：上证分时（全宽） -->
            <div class="timing-chart-row" style="margin-bottom: 20px;">
                <div class="chart-card" style="background-color: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; overflow: hidden;">
                    <div class="chart-card-header" style="padding: 12px 15px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;">
                        <h3 id="timingChartTitle" style="margin: 0; font-size: 1rem; color: var(--text-main);">📉 上证分时</h3>
                    </div>
                    <div class="chart-card-content" style="padding: 15px; height: 350px;">
                        <canvas id="timingChart"></canvas>
                    </div>
                </div>
            </div>

            <!-- 第二行：全球指数和成交量趋势 -->
            <div class="market-charts-grid">
                <!-- 全球指数 - 表格 -->
                <div class="chart-card" style="background-color: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; overflow: hidden;">
                    <div class="chart-card-header" style="padding: 12px 15px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;">
                        <h3 style="margin: 0; font-size: 1rem; color: var(--text-main);">🌍 全球指数</h3>
                    </div>
                    <div class="chart-card-content" style="padding: 15px; max-height: 400px; overflow-y: auto;">
                        {indices_content}
                    </div>
                </div>
                <!-- 成交量趋势 - 表格 -->
                <div class="chart-card" style="background-color: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; overflow: hidden;">
                    <div class="chart-card-header" style="padding: 12px 15px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;">
                        <h3 style="margin: 0; font-size: 1rem; color: var(--text-main);">📊 成交量趋势</h3>
                    </div>
                    <div class="chart-card-content" style="padding: 15px; max-height: 400px; overflow-y: auto;">
                        {volume_content}
                    </div>
                </div>
            </div>
        </div>
    '''.format(
        indices_content=market_charts.get('indices', ''),
        volume_content=market_charts.get('volume', '')
    )

    html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>市场指数 - LanFund</title>
    <link rel="icon" href="/static/1.ico">
    {css_style}
    <link rel="stylesheet" href="/static/css/style.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        body {{
            background-color: var(--terminal-bg);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }}

        /* 顶部导航栏 */
        .top-navbar {{
            background-color: var(--card-bg);
            color: var(--text-main);
            padding: 0.8rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
        }}

        .top-navbar-brand {{
            display: flex;
            align-items: center;
            flex: 0 0 auto;
        }}

        .top-navbar-quote {{
            flex: 1;
            text-align: center;
            font-size: 1rem;
            font-weight: 500;
            color: var(--text-main);
            font-style: italic;
            padding: 0 2rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            letter-spacing: 0.05em;
            transition: opacity 0.5s ease-in-out;
        }}

        .top-navbar-menu {{
            display: flex;
            gap: 1rem;
            align-items: center;
        }}

        .nav-user {{
            color: #3b82f6;
            font-weight: 500;
        }}

        .nav-logout {{
            color: #f85149;
            text-decoration: none;
            font-weight: 500;
        }}

        .nav-star {{
            color: #e3b341;
            text-decoration: none;
            font-weight: 500;
        }}

        .nav-star:hover {{
            color: #f2c94c;
        }}

        .nav-feedback {{
            color: #8b949e;
            text-decoration: none;
            font-weight: 500;
        }}

        .nav-feedback:hover {{
            color: #58a6ff;
        }}

        /* 主容器 */
        .main-container {{
            display: flex;
            flex: 1;
        }}

        /* 内容区域 */
        .content-area {{
            flex: 1;
            overflow-y: auto;
        }}

        /* 隐藏滚动条但保留功能 */
        ::-webkit-scrollbar {{
            width: 6px;
            height: 6px;
        }}

        ::-webkit-scrollbar-track {{
            background: transparent;
        }}

        ::-webkit-scrollbar-thumb {{
            background: rgba(255, 255, 255, 0.1);
            border-radius: 3px;
        }}

        ::-webkit-scrollbar-thumb:hover {{
            background: rgba(255, 255, 255, 0.2);
        }}

        /* Firefox */
        * {{
            scrollbar-width: thin;
            scrollbar-color: rgba(255, 255, 255, 0.1) transparent;
        }}

        .chart-card-content::-webkit-scrollbar {{
            width: 4px;
        }}

        .chart-card-content::-webkit-scrollbar-thumb {{
            background: rgba(255, 255, 255, 0.05);
        }}

        @media (max-width: 768px) {{
            /* 顶部导航栏两行布局 */
            .top-navbar {{
                flex-direction: row;
                flex-wrap: wrap;
                height: auto;
                padding: 0.5rem 1rem;
                align-items: center;
                border-bottom: none;
            }}

            .top-navbar > .top-navbar-brand {{
                order: 1;
                flex: 0 0 auto;
                padding-bottom: 0.5rem;
                border-bottom: 1px solid var(--border);
            }}

            .top-navbar-menu {{
                order: 1;
                flex: 0 0 auto;
                margin-left: auto;
                padding-bottom: 0.5rem;
                border-bottom: 1px solid var(--border);
            }}

            .top-navbar-quote {{
                order: 2;
                width: 100%;
                flex-basis: 100%;
                text-align: center;
                padding: 0.5rem 0;
                font-size: 0.8rem;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                border-top: 1px solid var(--border);
                margin-top: 0.5rem;
            }}

            .timing-chart-row .chart-card-content {{
                height: 250px;
            }}
        }}
    </style>
</head>
<body>
    <!-- 顶部导航栏 -->
    <div class="top-navbar">
        <div class="top-navbar-brand">
            <img src="/static/1.ico" alt="Logo" class="navbar-logo">
        </div>
        <div class="top-navbar-quote" id="lyricsDisplay">
            偶然与巧合, 舞动了蝶翼, 谁的心头风起 ————《如果我们不曾相遇》
        </div>
        <div class="top-navbar-menu">
            {username_display}
        </div>
    </div>

    <!-- 主容器 -->
    <div class="main-container">
        <!-- 汉堡菜单按钮 (移动端) -->
        <button class="hamburger-menu" id="hamburgerMenu">
            <span></span>
            <span></span>
            <span></span>
        </button>

        <!-- 左侧导航栏 -->
        <div class="sidebar collapsed" id="sidebar">
            <div class="sidebar-toggle" id="sidebarToggle">▶</div>
            <a href="/market" class="sidebar-item">
                <span class="sidebar-icon">📰</span>
                <span>市场行情</span>
            </a>
            <a href="/market-indices" class="sidebar-item active">
                <span class="sidebar-icon">📊</span>
                <span>市场指数</span>
            </a>
            <a href="/precious-metals" class="sidebar-item">
                <span class="sidebar-icon">🪙</span>
                <span>贵金属行情</span>
            </a>
            <a href="/portfolio" class="sidebar-item">
                <span class="sidebar-icon">💼</span>
                <span>持仓基金</span>
            </a>
            <a href="/sectors" class="sidebar-item">
                <span class="sidebar-icon">🏢</span>
                <span>行业板块</span>
            </a>
        </div>

        <!-- 内容区域 -->
        <div class="content-area">
            {market_content}
        </div>
    </div>

    <script src="/static/js/main.js"></script>
    <script src="/static/js/sidebar-nav.js"></script>
    <script>
        // 上证分时数据
        const timingData = {timing_data_json};

        document.addEventListener('DOMContentLoaded', function() {{
            // 歌词轮播
            const lyrics = [
                '总要有一首我的歌, 大声唱过, 再看天地辽阔 ————《一颗苹果》',
                '苍狗又白云, 身旁有了你, 匆匆轮回又有何惧 ————《如果我们不曾相遇》',
                '活着其实很好, 再吃一颗苹果 ————《一颗苹果》',
                '偶然与巧合, 舞动了蝶翼, 谁的心头风起 ————《如果我们不曾相遇》'
            ];
            let currentLyricIndex = 0;
            const lyricsElement = document.getElementById('lyricsDisplay');

            // 随机选择初始歌词
            currentLyricIndex = Math.floor(Math.random() * lyrics.length);
            if (lyricsElement) {{
                lyricsElement.textContent = lyrics[currentLyricIndex];

                // 每10秒切换一次歌词
                setInterval(function() {{
                    // 淡出
                    lyricsElement.style.opacity = '0';

                    setTimeout(function() {{
                        // 切换歌词
                        currentLyricIndex = (currentLyricIndex + 1) % lyrics.length;
                        lyricsElement.textContent = lyrics[currentLyricIndex];

                        // 淡入
                        lyricsElement.style.opacity = '1';
                    }}, 500);
                }}, 10000);
            }}

            // 自动颜色化
            const cells = document.querySelectorAll('.style-table td');
            cells.forEach(cell => {{
                const text = cell.textContent.trim();
                const cleanText = text.replace(/[%,亿万手]/g, '');
                const val = parseFloat(cleanText);

                if (!isNaN(val)) {{
                    if (text.includes('%') || text.includes('涨跌')) {{
                        if (text.includes('-')) {{
                            cell.classList.add('negative');
                        }} else if (val > 0) {{
                            cell.classList.add('positive');
                        }}
                    }} else if (text.startsWith('-')) {{
                        cell.classList.add('negative');
                    }} else if (text.startsWith('+')) {{
                        cell.classList.add('positive');
                    }}
                }}
            }});

            // 初始化上证分时图表
            initTimingChart();
        }});

        // 上证分时图表 - 使用API返回的实际涨跌幅
        function initTimingChart() {{
            const ctx = document.getElementById('timingChart');
            if (!ctx || timingData.labels.length === 0) return;

            // 使用API返回的实际数据（已经处理好的）
            const changePercentages = timingData.change_pcts || [];
            const changeAmounts = timingData.change_amounts || [];  // 原始涨跌额数据
            const basePrice = timingData.prices[0];
            const lastPrice = timingData.prices[timingData.prices.length - 1];

            // 使用最后一个实际涨跌幅值
            const lastPct = changePercentages.length > 0 ? changePercentages[changePercentages.length - 1] : 0;
            const titleColor = lastPct >= 0 ? '#f44336' : '#4caf50';

            // 更新标题颜色 - 现在主要显示实际涨跌幅
            const titleElement = document.getElementById('timingChartTitle');
            if (titleElement) {{
                titleElement.style.color = titleColor;
                titleElement.innerHTML = '📉 上证分时 <span style="font-size:0.9em;">' +
                    (lastPct >= 0 ? '+' : '') + lastPct.toFixed(2) + '% (' + lastPrice.toFixed(2) + ')</span>';
            }}

            // 保存图表实例到全局变量，方便后续更新
            window.timingChartInstance = new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: timingData.labels,
                    datasets: [{{
                        label: '涨跌幅 (%)',
                        data: changePercentages,
                        borderColor: function(context) {{
                            // 动态返回颜色：>0% 红色，<0% 绿色，=0% 灰色
                            const index = context.dataIndex;
                            if (index === undefined || index < 0) return '#9ca3af';
                            const pct = changePercentages[index];
                            return pct > 0 ? '#f44336' : (pct < 0 ? '#4caf50' : '#9ca3af');
                        }},
                        segment: {{
                            borderColor: function(context) {{
                                // 根据线段的结束点判断颜色
                                const pct = changePercentages[context.p1DataIndex];
                                return pct > 0 ? '#f44336' : (pct < 0 ? '#4caf50' : '#9ca3af');
                            }}
                        }},
                        backgroundColor: function(context) {{
                            const chart = context.chart;
                            const {{ctx, chartArea}} = chart;
                            if (!chartArea) return null;
                            // 根据当前最新涨跌幅判断整体涨跌来设置背景色
                            const lastPct = changePercentages[changePercentages.length - 1];
                            const color = lastPct >= 0 ? '244, 67, 54' : '76, 175, 80';
                            const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
                            gradient.addColorStop(0, 'rgba(' + color + ', 0.2)');
                            gradient.addColorStop(1, 'rgba(' + color + ', 0.0)');
                            return gradient;
                        }},
                        fill: true,
                        tension: 0.4,
                        pointRadius: 0,
                        pointHoverRadius: 4,
                        borderWidth: 2
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {{
                        mode: 'index',
                        intersect: false,
                    }},
                    plugins: {{
                        legend: {{
                            display: true,
                            position: 'top',
                            labels: {{
                                font: {{ size: 11 }},
                                boxWidth: 12,
                                generateLabels: function(chart) {{
                                    const lastPct = changePercentages[changePercentages.length - 1];
                                    const color = lastPct >= 0 ? '#ff4d4f' : '#52c41a';
                                    return [{{
                                        text: '涨跌幅: ' + (lastPct >= 0 ? '+' : '') + lastPct.toFixed(2) + '% (' + lastPrice.toFixed(2) + ')',
                                        fillStyle: color,
                                        strokeStyle: color,
                                        fontColor: color,
                                        lineWidth: 2,
                                        hidden: false,
                                        index: 0
                                    }}];
                                }}
                            }}
                        }},
                        tooltip: {{
                            callbacks: {{
                                title: function(context) {{
                                    return '时间: ' + context[0].label;
                                }},
                                label: function(context) {{
                                    const index = context.dataIndex;
                                    const pct = changePercentages[index];
                                    const price = timingData.prices[index];
                                    const changeAmt = changeAmounts[index];  // 使用原始涨跌额数据
                                    const volume = timingData.volumes ? timingData.volumes[index] : 0;
                                    const amount = timingData.amounts ? timingData.amounts[index] : 0;
                                    return [
                                        '涨跌幅: ' + (pct >= 0 ? '+' : '') + pct.toFixed(2) + '%',
                                        '上证指数: ' + price.toFixed(2),
                                        '涨跌额: ' + (changeAmt >= 0 ? '+' : '') + changeAmt.toFixed(2),
                                        '成交量: ' + volume.toFixed(0) + '万手',
                                        '成交额: ' + amount.toFixed(2) + '亿'
                                    ];
                                }}
                            }}
                        }},
                        datalabels: {{
                            display: false
                        }}
                    }},
                    scales: {{
                        x: {{
                            ticks: {{
                                color: '#9ca3af',
                                font: {{ size: 10 }},
                                maxTicksLimit: 6
                            }},
                            grid: {{
                                color: 'rgba(255, 255, 255, 0.1)'
                            }}
                        }},
                        y: {{
                            title: {{
                                display: true,
                                text: '涨跌幅 (%)',
                                color: '#9ca3af',
                                font: {{ size: 11 }}
                            }},
                            ticks: {{
                                color: '#9ca3af',
                                callback: function(value) {{
                                    return (value >= 0 ? '+' : '') + value.toFixed(2) + '%';
                                }}
                            }},
                            grid: {{
                                color: 'rgba(255, 255, 255, 0.1)'
                            }}
                        }}
                    }}
                }}
            }});
        }}
    </script>
</body>
</html>'''.format(
        css_style=css_style,
        username_display=username_display,
        market_content=market_content,
        timing_data_json=timing_data_json
    )
    return html


def get_precious_metals_page_html(metals_data, username=None):
    """生成贵金属行情页面"""
    css_style = get_css_style()

    username_display = '<a href="https://github.com/lanZzV/fund" target="_blank" class="nav-star">点个赞</a>'
    username_display += '<a href="https://github.com/lanZzV/fund/issues" target="_blank" class="nav-feedback">反馈</a>'
    if username:
        username_display += '<span class="nav-user">🍎 {username}</span>'.format(username=username)
        username_display += '<a href="/logout" class="nav-logout">退出登录</a>'

    html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>贵金属行情 - LanFund</title>
    <link rel="icon" href="/static/1.ico">
    {css_style}
    <link rel="stylesheet" href="/static/css/style.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        body {{
            background-color: var(--terminal-bg);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }}

        /* 顶部导航栏 */
        .top-navbar {{
            background-color: var(--card-bg);
            color: var(--text-main);
            padding: 0.8rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
        }}

        .top-navbar-brand {{
            display: flex;
            align-items: center;
            flex: 0 0 auto;
        }}

        .navbar-logo {{
            width: 32px;
            height: 32px;
        }}

        .top-navbar-quote {{
            flex: 1;
            text-align: center;
            font-size: 1rem;
            font-weight: 500;
            color: var(--text-main);
            font-style: italic;
            padding: 0 2rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            letter-spacing: 0.05em;
            transition: opacity 0.5s ease-in-out;
        }}

        .top-navbar-menu {{
            display: flex;
            gap: 1rem;
            align-items: center;
        }}

        .nav-logout {{
            color: #f85149;
            text-decoration: none;
            font-weight: 500;
        }}

        .nav-star {{
            color: #e3b341;
            text-decoration: none;
            font-weight: 500;
        }}

        .nav-star:hover {{
            color: #f2c94c;
        }}

        .nav-feedback {{
            color: #8b949e;
            text-decoration: none;
            font-weight: 500;
        }}

        .nav-feedback:hover {{
            color: #58a6ff;
        }}

        .nav-user {{
            color: #3b82f6;
            font-weight: 500;
        }}

        /* 主容器 */
        .main-container {{
            display: flex;
            flex: 1;
        }}

        /* 内容区域 */
        .content-area {{
            flex: 1;
            padding: 20px;
            overflow-y: auto;
        }}

        /* 隐藏滚动条但保留功能 */
        ::-webkit-scrollbar {{
            width: 6px;
            height: 6px;
        }}

        ::-webkit-scrollbar-track {{
            background: transparent;
        }}

        ::-webkit-scrollbar-thumb {{
            background: rgba(255, 255, 255, 0.1);
            border-radius: 3px;
        }}

        ::-webkit-scrollbar-thumb:hover {{
            background: rgba(255, 255, 255, 0.2);
        }}

        /* Firefox */
        * {{
            scrollbar-width: thin;
            scrollbar-color: rgba(255, 255, 255, 0.1) transparent;
        }}

        .page-header {{
            margin-bottom: 20px;
        }}

        .page-header h1 {{
            font-size: 1.8rem;
            margin: 0;
            color: var(--text-main);
        }}

        .page-header p {{
            margin: 5px 0 0;
            color: var(--text-dim);
        }}

        /* 贵金属网格布局 - 上下两栏 */
        .metals-grid {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 20px;
            max-width: 100%;
        }}

        .metal-card {{
            background-color: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            overflow: hidden;
            width: 100%;
        }}

        .metal-card-realtime {{
            min-height: 200px;
        }}

        .metal-card-history {{
            min-height: 400px;
        }}

        .metal-card {{
            background-color: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            overflow: hidden;
        }}

        .metal-card-header {{
            padding: 15px 20px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .metal-card-title {{
            font-size: 1.1rem;
            font-weight: 500;
            color: var(--text-main);
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .metal-card-content {{
            padding: 20px;
            max-height: 500px;
            overflow-y: auto;
        }}

        .chart-container {{
            position: relative;
            height: 400px;
            width: 100%;
        }}

        /* 确保表格容器支持横向滚动 */
        .metal-card-realtime .table-container {{
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }}

        .metal-card-realtime .style-table {{
            min-width: max-content;
            white-space: nowrap;
        }}

        /* 响应式设计 */
        @media (max-width: 768px) {{
            .metals-grid {{
                grid-template-columns: 1fr;
            }}

            .content-area {{
                padding: 15px;
            }}

            /* 顶部导航栏两行布局 */
            .top-navbar {{
                flex-direction: row;
                flex-wrap: wrap;
                height: auto;
                padding: 0.5rem 1rem;
                align-items: center;
                border-bottom: none;
            }}

            .top-navbar > .top-navbar-brand {{
                order: 1;
                flex: 0 0 auto;
                padding-bottom: 0.5rem;
                border-bottom: 1px solid var(--border);
            }}

            .top-navbar-menu {{
                order: 1;
                flex: 0 0 auto;
                margin-left: auto;
                padding-bottom: 0.5rem;
                border-bottom: 1px solid var(--border);
            }}

            .top-navbar-quote {{
                order: 2;
                width: 100%;
                flex-basis: 100%;
                text-align: center;
                padding: 0.5rem 0;
                font-size: 0.8rem;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                border-top: 1px solid var(--border);
                margin-top: 0.5rem;
            }}

            /* 汉堡菜单显示 */
            .hamburger-menu {{
                display: flex !important;
            }}

            .metal-card-history {{
                min-height: 300px;
            }}

            .chart-container {{
                height: 280px;
            }}
        }}
    </style>
</head>
<body>
    <!-- 顶部导航栏 -->
    <nav class="top-navbar">
        <div class="top-navbar-brand">
            <img src="/static/1.ico" alt="Logo" class="navbar-logo">
        </div>
        <div class="top-navbar-quote" id="lyricsDisplay">
            偶然与巧合, 舞动了蝶翼, 谁的心头风起 ————《如果我们不曾相遇》
        </div>
        <div class="top-navbar-menu">
            {username_display}
        </div>
    </nav>

    <!-- 主容器 -->
    <div class="main-container">
        <!-- 汉堡菜单按钮 (移动端) -->
        <button class="hamburger-menu" id="hamburgerMenu">
            <span></span>
            <span></span>
            <span></span>
        </button>

        <!-- 左侧导航栏 -->
        <div class="sidebar collapsed" id="sidebar">
            <div class="sidebar-toggle" id="sidebarToggle">▶</div>
            <a href="/precious-metals" class="sidebar-item active">
                <span class="sidebar-icon">🪙</span>
                <span>贵金属行情</span>
            </a>
            <a href="/portfolio" class="sidebar-item">
                <span class="sidebar-icon">💼</span>
                <span>持仓基金</span>
            </a>
            <a href="/sectors" class="sidebar-item">
                <span class="sidebar-icon">🏢</span>
                <span>行业板块</span>
            </a>
        </div>

        <!-- 内容区域 -->
        <div class="content-area">
            <!-- 页面标题 -->
            <div class="page-header">
                <h1 style="display: flex; align-items: center;">
                    🪙 贵金属行情
                    <div style="margin-left: 15px; display: flex; align-items: center; gap: 10px;">
                        <button id="refreshBtn-metals" onclick="refreshCurrentPage()" class="refresh-button" style="padding: 8px 16px; background: var(--accent); color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem; font-weight: 500; transition: all 0.2s ease; display: inline-flex; align-items: center; gap: 5px;">🔄 刷新</button>
                        <span id="lastRefreshTime-metals" style="font-size: 0.85rem; color: #666; min-width: 60px;">未刷新</span>
                    </div>
                </h1>
                <p>实时追踪贵金属价格走势</p>
            </div>

            <!-- 贵金属网格 - 上下两栏布局 -->
            <div class="metals-grid">
                <!-- 实时贵金属 -->
                <div class="metal-card metal-card-realtime">
                    <div class="metal-card-header">
                        <h3 class="metal-card-title">
                            <span>⚡</span>
                            <span>实时贵金属</span>
                        </h3>
                    </div>
                    <div class="metal-card-content">
                        {real_time_content}
                    </div>
                </div>

                <!-- 历史金价 -->
                <div class="metal-card metal-card-history">
                    <div class="metal-card-header">
                        <h3 class="metal-card-title">
                            <span>📈</span>
                            <span>历史金价</span>
                        </h3>
                    </div>
                    <div class="metal-card-content">
                        <!-- Hidden div to store history data for parsing -->
                        <div id="goldHistoryData" style="display:none;">
                            {history_content}
                        </div>
                        <div class="chart-container">
                            <canvas id="goldPriceChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="/static/js/main.js"></script>
    <script src="/static/js/sidebar-nav.js"></script>
    <script>
        // 自动颜色化
        function autoColorize() {{
            const elements = document.querySelectorAll('[data-change]');
            elements.forEach(function(el) {{
                const change = parseFloat(el.getAttribute('data-change'));
                if (change > 0) {{
                    el.style.color = '#f44336';
                }} else if (change < 0) {{
                    el.style.color = '#4caf50';
                }}
            }});
        }}

        // 解析历史金价数据并创建图表
        function createGoldChart() {{
            // 从隐藏的div中获取历史金价表格
            const historyContainer = document.getElementById('goldHistoryData');
            if (!historyContainer) return;

            const table = historyContainer.querySelector('table');
            if (!table) return;

            const rows = table.querySelectorAll('tbody tr');
            const labels = [];
            const prices = [];

            rows.forEach(row => {{
                const cells = row.querySelectorAll('td');
                if (cells.length >= 2) {{
                    labels.push(cells[0].textContent.trim());
                    prices.push(parseFloat(cells[1].textContent.trim()));
                }}
            }});

            // 创建图表
            const ctx = document.getElementById('goldPriceChart').getContext('2d');

            // 注册插件以在数据点上显示数值
            const dataLabelPlugin = {{
                id: 'dataLabelPlugin',
                afterDatasetsDraw(chart, args, options) {{
                    const {{ ctx }} = chart;
                    chart.data.datasets.forEach((dataset, datasetIndex) => {{
                        const meta = chart.getDatasetMeta(datasetIndex);
                        meta.data.forEach((datapoint, index) => {{
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
                        }});
                    }});
                }}
            }};

            new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: labels.reverse(),
                    datasets: [{{
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
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            labels: {{
                                color: '#9ca3af'
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{
                            ticks: {{
                                color: '#9ca3af'
                            }},
                            grid: {{
                                color: 'rgba(255, 255, 255, 0.1)'
                            }}
                        }},
                        y: {{
                            ticks: {{
                                color: '#9ca3af'
                            }},
                            grid: {{
                                color: 'rgba(255, 255, 255, 0.1)'
                            }}
                        }}
                    }}
                }},
                plugins: [dataLabelPlugin]
            }});
        }}

        document.addEventListener('DOMContentLoaded', function() {{
            // 歌词轮播
            const lyrics = [
                '总要有一首我的歌, 大声唱过, 再看天地辽阔 ————《一颗苹果》',
                '苍狗又白云, 身旁有了你, 匆匆轮回又有何惧 ————《如果我们不曾相遇》',
                '活着其实很好, 再吃一颗苹果 ————《一颗苹果》',
                '偶然与巧合, 舞动了蝶翼, 谁的心头风起 ————《如果我们不曾相遇》'
            ];
            let currentLyricIndex = 0;
            const lyricsElement = document.getElementById('lyricsDisplay');

            // 随机选择初始歌词
            currentLyricIndex = Math.floor(Math.random() * lyrics.length);
            if (lyricsElement) {{
                lyricsElement.textContent = lyrics[currentLyricIndex];

                // 每10秒切换一次歌词
                setInterval(function() {{
                    // 淡出
                    lyricsElement.style.opacity = '0';

                    setTimeout(function() {{
                        // 切换歌词
                        currentLyricIndex = (currentLyricIndex + 1) % lyrics.length;
                        lyricsElement.textContent = lyrics[currentLyricIndex];

                        // 淡入
                        lyricsElement.style.opacity = '1';
                    }}, 500);
                }}, 10000);
            }}

            autoColorize();
            createGoldChart();
        }});
    </script>
</body>
</html>'''.format(
        css_style=css_style,
        username_display=username_display,
        real_time_content=metals_data.get('real_time', ''),
        history_content=metals_data.get('history', '')
    )
    return html

