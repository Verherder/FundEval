# -*- coding: UTF-8 -*-
import re

from flask import url_for


def enhance_fund_tab_content(content, shares_map=None):
    """
    Enhance the fund tab content with operations panel, file operations, and shares input.
    Args:
        content: HTML content to enhance
        shares_map: Dict mapping fund_code -> shares value (optional)
    """
    # 添加文件操作和持仓统计区域
    file_operations = f"""
        <div class="file-operations" style="margin-bottom: 15px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
            <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
                <button class="btn btn-secondary fund-io-btn" onclick="downloadFundMap()">📥 导出基金列表</button>
                <input type="file" id="uploadFile" accept=".json" style="display:none" onchange="uploadFundMap(this.files[0])">
                <button class="btn btn-secondary fund-io-btn" onclick="document.getElementById('uploadFile').click()">📤 导入基金列表</button>
                <input type="file" id="uploadTradeFile" accept=".xlsx" style="display:none" onchange="uploadTransactionRecords(this.files[0])">
                <button class="btn btn-secondary fund-io-btn" onclick="document.getElementById('uploadTradeFile').click()">📑 导入交易记录</button>
            </div>
            <div id="toolbarEstimatedGainWrap" style="margin-left:auto; display:flex; align-items:center; gap:8px; padding:8px 12px; border:1px solid var(--border); border-radius:8px; background: var(--card-bg); min-height: 38px;">
                <span id="toolbarEstimatedGainLabel" style="font-size:13px; color: var(--text-dim); white-space:nowrap;">xx日收益估计</span>
                <span id="toolbarEstimatedGain" style="font-size:14px; font-weight:600; color: var(--text-main); font-family: var(--font-mono); white-space:nowrap;">--</span>
                <span id="toolbarEstimatedGainPct" style="font-size:12px; color: var(--text-dim); font-family: var(--font-mono); white-space:nowrap;">--</span>
            </div>
            <span style="color: #f59e0b; font-size: 13px; width: 100%;">
                <span style="color: #f59e0b;">⚠️</span> 导入/导出为覆盖性操作，直接应用最新配置（非累加）
            </span>
        </div>
    """

    # 添加持仓统计区域（将通过JavaScript动态填充）
    position_summary = """
        <div id="positionSummary" class="position-summary" style="display: none; background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-bottom: 4px;">
            <h3 style="margin: 0 0 15px 0; font-size: 18px; font-weight: 600; color: var(--text-main); display: flex; justify-content: space-between; align-items: center;">
                💰 持仓统计
                <div style="display: flex; gap: 10px; align-items: center;">
                    <button id="showoffBtn" onclick="openShowoffCard()"
                            style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                   border: none; border-radius: 20px; padding: 6px 16px;
                                   color: white; font-size: 14px; font-weight: 600;
                                   cursor: pointer; display: flex; align-items: center; gap: 6px;
                                   box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
                                   transition: all 0.3s ease; white-space: nowrap;">
                        ✨ 一键炫耀
                    </button>
                    <span id="toggleSensitiveValues" style="cursor: pointer; font-size: 18px; user-select: none;" title="显示 / 隐藏 收益明细">😀</span>
                </div>
            </h3>
            <div class="stats-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                <div class="stat-item" style="text-align: center;">
                    <div style="font-size: 12px; color: var(--text-dim); margin-bottom: 5px;">总持仓金额</div>
                    <div id="totalValue" class="sensitive-value" style="font-size: 24px; font-weight: bold; color: var(--text-main); text-align: center;">
                        <span class="real-value">¥0.00</span><span class="hidden-value">****</span>
                    </div>
                </div>
                <div class="stat-item" style="text-align: center;">
                    <div id="estimatedGainLabel" style="font-size: 12px; color: var(--text-dim); margin-bottom: 5px;">xx日预估收益</div>
                    <div id="estimatedGain" style="font-size: 24px; font-weight: bold; white-space: nowrap; color: var(--text-main); text-align: center;">
                        <span class="sensitive-value"><span class="real-value">¥0.00</span><span class="hidden-value">****</span></span><span id="estimatedGainPct"> (+0.00%)</span>
                    </div>
                    <div id="estimatedGainNote" style="display:none; margin-top: 6px; font-size: 11px; color: var(--text-dim);"></div>
                </div>
                <div class="stat-item" style="text-align: center;">
                    <div id="actualGainLabel" style="font-size: 12px; color: var(--text-dim); margin-bottom: 5px;">xx日实际收益</div>
                    <div id="actualGain" style="font-size: 24px; font-weight: bold; white-space: nowrap; color: var(--text-main); text-align: center;">
                        <span class="sensitive-value"><span class="real-value">¥0.00</span><span class="hidden-value">****</span></span><span id="actualGainPct"> (+0.00%)</span>
                    </div>
                    <div id="actualGainNote" style="display:none; margin-top: 6px; font-size: 11px; color: var(--text-dim);"></div>
                </div>
            </div>
        </div>

        <div id="fundDetailsSummary" class="fund-details-summary" style="display: none; background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-bottom: 20px;">
            <h3 style="margin: 0 0 15px 0; font-size: 16px; font-weight: 600; color: var(--text-main);">📊 分基金涨跌明细</h3>
            <div style="overflow-x: auto;">
                <table id="fundDetailsTable" style="width: 100%; min-width: 600px; border-collapse: collapse; font-size: 13px; table-layout: auto; white-space: nowrap;">
                    <thead>
                        <tr style="background: rgba(59, 130, 246, 0.1);">
                            <th style="padding: 10px; text-align: center; white-space: nowrap; vertical-align: middle; color: var(--text-dim); font-weight: 500;">基金代码</th>
                            <th style="padding: 10px; text-align: center; white-space: nowrap; vertical-align: middle; color: var(--text-dim); font-weight: 500;">基金名称</th>
                            <th style="padding: 10px; text-align: center; white-space: nowrap; vertical-align: middle; color: var(--text-dim); font-weight: 500;">持仓份额</th>
                            <th class="sortable" onclick="sortTable(this.closest('table'), 3)" style="padding: 10px; text-align: center; white-space: nowrap; vertical-align: middle; color: var(--text-dim); font-weight: 500; cursor: pointer; user-select: none;">持仓市值</th>
                            <th class="sortable" onclick="sortTable(this.closest('table'), 4)" style="padding: 10px; text-align: center; white-space: nowrap; vertical-align: middle; color: var(--text-dim); font-weight: 500; cursor: pointer; user-select: none;">预估收益</th>
                            <th class="sortable" onclick="sortTable(this.closest('table'), 5)" style="padding: 10px; text-align: center; white-space: nowrap; vertical-align: middle; color: var(--text-dim); font-weight: 500; cursor: pointer; user-select: none;">实际收益</th>
                        </tr>
                    </thead>
                    <tbody id="fundDetailsTableBody">
                    </tbody>
                </table>
            </div>
        </div>

        <!-- 炫耀卡片模态框 -->
        <div id="showoffModal" class="showoff-modal" onclick="closeShowoffCard(event)">
            <div class="showoff-card" onclick="event.stopPropagation()">
                <!-- 关闭按钮 -->
                <button class="showoff-close" onclick="closeShowoffCard()">✕</button>

                <!-- 左上角品牌标识 -->
                <div class="showoff-brand-corner">
                    <img src="{url_for('static', filename='1.ico')}" alt="MiniFund" class="brand-logo" onerror="this.style.display='none'">
                    <span class="brand-name">MiniFund</span>
                </div>

                <!-- 卡片背景装饰 -->
                <div class="showoff-bg-decoration">
                    <div class="bg-circle circle-1"></div>
                    <div class="bg-circle circle-2"></div>
                    <div class="bg-circle circle-3"></div>
                    <div class="bg-stars"></div>
                </div>

                <!-- 卡片头部 -->
                <div class="showoff-header">
                    <div class="showoff-icon">💰</div>
                    <h2 class="showoff-title">今日收益</h2>
                    <p class="showoff-date" id="showoffDate">2026-02-03</p>
                </div>

                <!-- 持仓统计摘要 -->
                <div class="showoff-summary">
                    <div class="summary-row summary-row-total">
                        <div class="summary-item">
                            <div class="summary-label">总持仓</div>
                            <div class="summary-value" id="showoffTotalValue">¥0.00</div>
                        </div>
                    </div>
                    <div class="summary-row">
                        <div class="summary-item">
                            <div class="summary-label">今日预估</div>
                            <div class="summary-value" id="showoffEstimatedGain">+¥0.00</div>
                        </div>
                        <div class="summary-item">
                            <div class="summary-label">今日实际</div>
                            <div class="summary-value" id="showoffActualGain">+¥0.00</div>
                        </div>
                    </div>
                </div>

                <!-- Top3基金明细 -->
                <div class="showoff-funds">
                    <div class="funds-header">
                        <span class="funds-title">🏆 收益Top3</span>
                    </div>
                    <div class="funds-list" id="showoffFundsList">
                        <!-- 动态生成 -->
                    </div>
                </div>
            </div>
        </div>
    """

    # 操作区域：把板块/删除操作放到"添加"按钮后，并用 | 分隔
    operations_panel = ""  # 兼容旧逻辑：不再单独渲染按钮面板

    add_fund_area = """
        <div class="add-fund-input" style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
            <input type="text" id="fundCodesInput"
                   placeholder="输入基金代码（逗号分隔，如：016858,007872）"
                   style="flex: 1 1 260px; min-width: 200px;">
            <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
                <button class="btn btn-primary" onclick="addFunds()">添加</button>
                <span style="opacity:0.6; user-select:none;">|</span>
                <button class="btn btn-info" onclick="openFundSelectionModal('sector')">🏷️ 标注板块</button>
                <span style="opacity:0.6; user-select:none;">|</span>
                <button class="btn btn-warning" onclick="openFundSelectionModal('unsector')">🏷️ 删除板块</button>
                <span style="opacity:0.6; user-select:none;">|</span>
                <button class="btn btn-danger" onclick="openFundSelectionModal('delete')">🗑️ 删除基金</button>
            </div>
        </div>
    """

    trade_modal = """
        <div class="sector-modal" id="tradeModal">
            <div class="sector-modal-content" style="max-width: 420px;">
                <div class="sector-modal-header" id="tradeModalTitle">基金交易</div>
                <div style="padding: 20px;">
                    <div style="margin-bottom: 15px;">
                        <label style="display: block; margin-bottom: 8px; color: var(--text-main); font-weight: 500;">基金代码</label>
                        <div id="tradeModalFundCode" style="padding: 10px; background: rgba(59, 130, 246, 0.1); border-radius: 6px; color: #3b82f6; font-weight: 600; font-family: monospace;"></div>
                    </div>
                    <div style="margin-bottom: 10px;">
                        <label for="tradeModalInput" id="tradeModalInputLabel" style="display: block; margin-bottom: 8px; color: var(--text-main); font-weight: 500;">请输入数值</label>
                        <input type="number" id="tradeModalInput" step="0.01" min="0" placeholder="请输入数值"
                               style="width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 6px; font-size: 14px; background: var(--card-bg); color: var(--text-main);">
                    </div>
                    <div id="tradeModalHint" style="font-size: 12px; color: var(--text-dim);"></div>
                </div>
                <div class="sector-modal-footer">
                    <button class="btn btn-secondary" onclick="closeTradeModal()">取消</button>
                    <button class="btn btn-primary" id="tradeModalConfirmBtn" onclick="confirmTrade()">确定</button>
                </div>
            </div>
        </div>
    """

    backfill_modal = """
        <div class="sector-modal" id="backfillModal">
            <div class="sector-modal-content" style="width: min(540px, 92vw); max-width: 540px; min-width: 320px;">
                <div class="sector-modal-header" id="backfillModalTitle">补录交易</div>
                <div style="padding: 20px;">
                    <div style="margin-bottom: 15px;">
                        <label style="display: block; margin-bottom: 8px; color: var(--text-main); font-weight: 500;">基金代码</label>
                        <div id="backfillModalFundCode" style="padding: 10px; background: rgba(59, 130, 246, 0.1); border-radius: 6px; color: #3b82f6; font-weight: 600; font-family: monospace;"></div>
                    </div>
                    <div style="margin-bottom: 12px; display:flex; gap:8px;">
                        <button type="button" class="btn btn-primary" id="backfillViewTradeBtn" onclick="setBackfillView('trade')">买入/卖出</button>
                        <button type="button" class="btn btn-secondary" id="backfillViewDividendBtn" onclick="setBackfillView('dividend')">分红</button>
                    </div>
                    <div id="backfillTopGrid" style="display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-bottom: 8px;">
                        <div>
                            <label for="backfillTradeDate" style="display: block; margin-bottom: 8px; color: var(--text-main); font-weight: 500;">交易日期</label>
                            <input type="date" id="backfillTradeDate"
                                   style="width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 6px; font-size: 14px; background: var(--card-bg); color: var(--text-main); font-family: var(--font-mono);">
                        </div>
                        <div id="backfillNetValueGroup">
                            <label for="backfillNetValue" id="backfillNetValueLabel" style="display: block; margin-bottom: 8px; color: var(--text-main); font-weight: 500;">当日净值</label>
                            <input type="number" id="backfillNetValue" step="0.0001" min="0" placeholder="例如 1.5803"
                                   style="width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 6px; font-size: 14px; background: var(--card-bg); color: var(--text-main);">
                        </div>
                    </div>
                    <div id="backfillNetValueHint" style="margin: -2px 0 12px; font-size: 12px; color: var(--text-dim);">选择日期后将尝试自动填充净值（若趋势数据可用）</div>
                    <div id="backfillAmountSharesGrid" style="display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-bottom: 8px; align-items:start;">
                        <div id="backfillAmountGroup">
                            <label for="backfillAmount" id="backfillAmountLabel" style="display: block; margin-bottom: 8px; color: var(--text-main); font-weight: 500;">金额（买入/分红，元）</label>
                            <input type="number" id="backfillAmount" step="0.01" min="0" placeholder="例如 100"
                                   style="width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 6px; font-size: 14px; background: var(--card-bg); color: var(--text-main);">
                            <div id="backfillAmountQuickButtons" style="margin-top: 8px; display: flex; gap: 8px; flex-wrap: wrap;">
                                <button type="button" class="btn btn-secondary" style="padding: 4px 10px; font-size: 12px;" onclick="setBackfillAmountQuick(500)">500</button>
                                <button type="button" class="btn btn-secondary" style="padding: 4px 10px; font-size: 12px;" onclick="setBackfillAmountQuick(1000)">1000</button>
                                <button type="button" class="btn btn-secondary" style="padding: 4px 10px; font-size: 12px;" onclick="setBackfillAmountQuick(2000)">2000</button>
                                <button type="button" class="btn btn-secondary" style="padding: 4px 10px; font-size: 12px;" onclick="setBackfillAmountQuick(4000)">4000</button>
                            </div>
                        </div>
                        <div id="backfillSharesGroup">
                            <label for="backfillShares" id="backfillSharesLabel" style="display: block; margin-bottom: 8px; color: var(--text-main); font-weight: 500;">份额（卖出填写 / 买入参考）</label>
                            <input type="number" id="backfillShares" step="0.01" min="0" placeholder="卖出时填写；买入会自动折算参考值"
                                   style="width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 6px; font-size: 14px; background: var(--card-bg); color: var(--text-main);">
                        </div>
                    </div>
                    <div id="backfillFeeGroup" style="margin-bottom: 8px;">
                        <label for="backfillFee" id="backfillFeeLabel" style="display: block; margin-bottom: 8px; color: var(--text-main); font-weight: 500;">手续费（元）</label>
                        <input type="number" id="backfillFee" step="0.01" min="0" placeholder="默认 0"
                               style="width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 6px; font-size: 14px; background: var(--card-bg); color: var(--text-main);">
                    </div>
                </div>
                <div class="sector-modal-footer">
                    <button class="btn btn-secondary" onclick="closeBackfillModal()">取消</button>
                    <div id="backfillTradeActions" style="display:flex; gap:8px;">
                        <button class="btn btn-primary" id="backfillModalBuyBtn" onclick="confirmBackfillTrade('buy')">补录买入</button>
                        <button class="btn" id="backfillModalSellBtn" style="background: #10b981; color: #fff;" onclick="confirmBackfillTrade('sell')">补录卖出</button>
                    </div>
                    <button class="btn btn-primary" id="backfillModalDividendBtn" style="display:none;" onclick="confirmBackfillTrade('dividend')">补录分红</button>
                </div>
            </div>
        </div>
    """

    bottom_danger_zone = """
        <div style="margin-top: 24px; padding: 12px 0 4px; display:flex; justify-content:flex-end; gap: 12px; border-top: 1px dashed var(--border);">
            <button class="btn btn-secondary" style="padding:6px 12px; font-size:12px;" onclick="backfillEstablishmentDates()">🗓️ 回填成立日期</button>
            <button class="btn btn-danger" style="padding:6px 12px; font-size:12px; opacity:0.78;" onclick="clearFundTransactionsDanger()">高级危险操作：清空交易记录</button>
        </div>
    """

    transaction_modal = """
        <div class="sector-modal" id="transactionModal">
            <div class="sector-modal-content" style="max-width: 1080px; width: min(1080px, 96vw); max-height: 90vh; display:flex; flex-direction:column; overflow:hidden;">
                <div class="sector-modal-header" style="display:flex; align-items:center; justify-content:center; gap:8px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
                    <span>交易记录</span>
                    <span style="color: var(--text-dim);">·</span>
                    <span id="transactionModalFundCode" style="font-family: monospace; color: #3b82f6;"></span>
                    <span id="transactionModalFundName" style="color: var(--text-main); overflow:hidden; text-overflow:ellipsis;"></span>
                </div>
                <div id="transactionModalBody" style="padding: 20px; overflow:auto;">
                    <div id="transactionModalSummary" style="display:grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-bottom: 10px;">
                        <div style="padding: 8px 10px; border: 1px solid var(--border); border-radius: 6px; background: var(--card-bg);">
                            <div style="font-size: 12px; color: var(--text-dim);">持仓收益</div>
                            <div id="transactionHoldingGain" style="margin-top: 4px; font-size: 14px; font-weight: 600; color: var(--text-main);">--</div>
                        </div>
                        <div style="padding: 8px 10px; border: 1px solid var(--border); border-radius: 6px; background: var(--card-bg);">
                            <div style="font-size: 12px; color: var(--text-dim);">持仓收益率</div>
                            <div id="transactionHoldingReturn" style="margin-top: 4px; font-size: 14px; font-weight: 600; color: var(--text-main);">--</div>
                        </div>
                        <div style="padding: 8px 10px; border: 1px solid var(--border); border-radius: 6px; background: var(--card-bg);">
                            <div style="font-size: 12px; color: var(--text-dim);">持有周期(天)</div>
                            <div id="transactionHoldingDays" style="margin-top: 4px; font-size: 14px; font-weight: 600; color: var(--text-main);">--</div>
                        </div>
                        <div style="padding: 8px 10px; border: 1px solid var(--border); border-radius: 6px; background: var(--card-bg);">
                            <div style="font-size: 12px; color: var(--text-dim);">总手续费</div>
                            <div id="transactionTotalFee" style="margin-top: 4px; font-size: 14px; font-weight: 600; color: var(--text-main);">--</div>
                        </div>
                        <div style="padding: 8px 10px; border: 1px solid var(--border); border-radius: 6px; background: var(--card-bg);">
                            <div style="font-size: 12px; color: var(--text-dim);">总收益</div>
                            <div id="transactionTotalGain" style="margin-top: 4px; font-size: 14px; font-weight: 600; color: var(--text-main);">--</div>
                        </div>
                        <div style="padding: 8px 10px; border: 1px solid var(--border); border-radius: 6px; background: var(--card-bg);">
                            <div style="font-size: 12px; color: var(--text-dim);">总收益率</div>
                            <div id="transactionTotalReturn" style="margin-top: 4px; font-size: 14px; font-weight: 600; color: var(--text-main);">--</div>
                        </div>
                    </div>
                    <div style="margin: -2px 0 10px; font-size: 12px; color: var(--text-dim); line-height: 1.5;">
                        口径说明：总收益 = 累计卖出 + 累计分红 + 当前持仓市值 - 累计买入；总收益率 = 总收益 / 累计买入。持仓收益/率与主表"持仓/收益、持有/年化"口径一致。
                    </div>
                    <div id="transactionModalHint" style="margin-bottom: 10px; font-size: 12px; color: var(--text-dim);"></div>
                    <div id="transactionModalTableWrap" style="max-height: 52vh; overflow: auto; border: 1px solid var(--border); border-radius: 6px;">
                        <table style="width: 100%; border-collapse: collapse;">
                            <thead>
                                <tr style="background: rgba(59, 130, 246, 0.08);">
                                    <th style="padding: 10px; text-align: left; font-size: 13px;">日期</th>
                                    <th style="padding: 10px; text-align: left; font-size: 13px;">类型</th>
                                    <th style="padding: 10px; text-align: right; font-size: 13px;">确认金额(元)</th>
                                    <th style="padding: 10px; text-align: right; font-size: 13px;">份额</th>
                                    <th style="padding: 10px; text-align: right; font-size: 13px;">净值</th>
                                    <th style="padding: 10px; text-align: right; font-size: 13px;">手续费</th>
                                    <th style="padding: 10px; text-align: right; font-size: 13px;">持仓成本价</th>
                                    <th style="padding: 10px; text-align: center; font-size: 13px;">操作</th>
                                </tr>
                            </thead>
                            <tbody id="transactionModalTbody"></tbody>
                        </table>
                    </div>
                </div>
                <div class="sector-modal-footer" style="flex-shrink:0; border-top: 1px solid var(--border); background: var(--card-bg);">
                    <button class="btn btn-secondary" onclick="closeTransactionModal()">关闭</button>
                </div>
            </div>
        </div>
    """

    # 在"持有/年化"列后拼接"操作"列（UI增强列，不属于fund.py数据列）
    content = re.sub(r'(<th[^>]*>持有/年化</th>)',
                   r'\1\n                    <th>操作</th>',
                   content, count=1)

    # 在每个数据行拼接买入/卖出操作按钮
    def add_operation_to_row(match):
        row_content = match.group(0)
        code_match = re.search(r'data-code="(\d{6})"', row_content) or re.search(r'<td[^>]*>(\d{6})</td>', row_content)
        if not code_match:
            return row_content

        fund_code = code_match.group(1)
        row_with_ops = row_content[:-5] + f'''<td>
            <div style="display:flex;gap:6px;justify-content:center;align-items:center;flex-wrap:nowrap;">
                <button class="shares-button" id="backfillBtn_{fund_code}"
                        onclick="window.openBackfillModal && window.openBackfillModal('{fund_code}')"
                        style="padding: 6px 10px; background: #6366f1; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 12px; transition: all 0.2s;">
                    补录
                </button>
            </div>
        </td></tr>'''
        return row_with_ops

    content = re.sub(r'<tr>.*?</tr>', add_operation_to_row, content, flags=re.DOTALL)

    return file_operations + position_summary + operations_panel + add_fund_area + trade_modal + backfill_modal + transaction_modal + content + bottom_danger_zone
