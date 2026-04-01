# -*- coding: UTF-8 -*-
import re


def enhance_fund_tab_content(content, shares_map=None):
    """
    Enhance the fund tab content with operations panel, file operations, and shares input.
    Args:
        content: HTML content to enhance
        shares_map: Dict mapping fund_code -> shares value (optional)
    """
    # 添加文件操作和持仓统计区域
    file_operations = """
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
        <div id="positionSummary" class="position-summary" style="display: none; background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-bottom: 20px;">
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
                <table id="fundDetailsTable" style="width: 100%; min-width: 700px; border-collapse: collapse; font-size: 13px; table-layout: auto; white-space: nowrap;">
                    <thead>
                        <tr style="background: rgba(59, 130, 246, 0.1);">
                            <th style="padding: 10px; text-align: center; white-space: nowrap; vertical-align: middle; color: var(--text-dim); font-weight: 500;">基金代码</th>
                            <th style="padding: 10px; text-align: center; white-space: nowrap; vertical-align: middle; color: var(--text-dim); font-weight: 500;">基金名称</th>
                            <th style="padding: 10px; text-align: center; white-space: nowrap; vertical-align: middle; color: var(--text-dim); font-weight: 500;">持仓份额</th>
                            <th class="sortable" onclick="sortTable(this.closest('table'), 3)" style="padding: 10px; text-align: center; white-space: nowrap; vertical-align: middle; color: var(--text-dim); font-weight: 500; cursor: pointer; user-select: none;">持仓市值</th>
                            <th class="sortable" onclick="sortTable(this.closest('table'), 4)" style="padding: 10px; text-align: center; white-space: nowrap; vertical-align: middle; color: var(--text-dim); font-weight: 500; cursor: pointer; user-select: none;">预估收益</th>
                            <th class="sortable" onclick="sortTable(this.closest('table'), 5)" style="padding: 10px; text-align: center; white-space: nowrap; vertical-align: middle; color: var(--text-dim); font-weight: 500; cursor: pointer; user-select: none;">预估涨跌</th>
                            <th class="sortable" onclick="sortTable(this.closest('table'), 6)" style="padding: 10px; text-align: center; white-space: nowrap; vertical-align: middle; color: var(--text-dim); font-weight: 500; cursor: pointer; user-select: none;">实际收益</th>
                            <th class="sortable" onclick="sortTable(this.closest('table'), 7)" style="padding: 10px; text-align: center; white-space: nowrap; vertical-align: middle; color: var(--text-dim); font-weight: 500; cursor: pointer; user-select: none;">实际涨跌</th>
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
                    <img src="/static/1.ico" alt="Lan Fund" class="brand-logo" onerror="this.style.display='none'">
                    <span class="brand-name">Lan Fund</span>
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

    # 操作区域：把板块/删除操作放到“添加”按钮后，并用 | 分隔
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
        <div style="margin-top: 24px; padding: 12px 0 4px; display:flex; justify-content:flex-end; border-top: 1px dashed var(--border);">
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
                        口径说明：总收益 = 累计卖出 + 累计分红 + 当前持仓市值 - 累计买入；总收益率 = 总收益 / 累计买入。持仓收益/率与主表“持仓/收益、持有/年化”口径一致。
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


def get_top_navbar_html(username=None):
    """
    生成顶部导航栏HTML（包含歌词）。
    支持桌面端单行布局和移动端两行布局。
    :param username: str, 用户名（可选）
    :return: tuple, (navbar_html, username_display)
    """
    username_display = '<a href="https://github.com/lanZzV/fund" target="_blank" class="nav-star">点个赞</a>'
    username_display += '<a href="https://github.com/lanZzV/fund/issues" target="_blank" class="nav-feedback">反馈</a>'
    if username:
        username_display += '<span class="nav-user">🍎 {username}</span>'.format(username=username)
        username_display += '<a href="/logout" class="nav-logout">退出登录</a>'

    navbar_html = '''
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
    '''.format(username_display=username_display)

    return navbar_html, username_display


def get_legacy_sidebar_html(active_page):
    """
    生成传统侧边栏HTML（用于非portfolio页面）。
    :param active_page: str, 当前激活的页面 ('market', 'market-indices', 'precious-metals', 'portfolio', 'sectors')
    :return: str, 侧边栏HTML
    """
    # 定义菜单项
    menu_items = [
        # ('market', '📰', '市场行情'),
        # ('market-indices', '📊', '市场指数'),
        # ('precious-metals', '🪙', '贵金属行情'),
        ('portfolio', '💼', '持仓基金'),
        ('sectors', '🏢', '行业板块'),
    ]

    # 生成菜单项HTML
    menu_html = ''
    for page_id, icon, label in menu_items:
        active_class = 'active' if page_id == active_page else ''
        href = f'/{page_id}'
        menu_html += f'''
            <a href="{href}" class="sidebar-item {active_class}">
                <span class="sidebar-icon">{icon}</span>
                <span>{label}</span>
            </a>
        '''

    return '''
        <!-- 汉堡菜单按钮 (移动端) -->
        <button class="hamburger-menu" id="hamburgerMenu">
            <span></span>
            <span></span>
            <span></span>
        </button>

        <!-- 左侧导航栏 -->
        <div class="sidebar collapsed" id="sidebar">
            <div class="sidebar-toggle" id="sidebarToggle">▶</div>
            {menu_items}
        </div>
    '''.format(menu_items=menu_html)


def get_lyrics_script():
    """
    生成歌词轮播的JavaScript代码。
    :return: str, JavaScript代码
    """
    return '''
    <script>
        // 歌词轮播
        (function() {
            const lyrics = [
                "偶然与巧合, 舞动了蝶翼, 谁的心头风起 ————《如果我们不曾相遇》",
                "如海上的浪花, 如深海的鱼, 浪与鱼相依 ————《鱼仔》",
                "阳光下的泡沫, 是彩色的, 一触就破 ————《泡沫》",
                "如果我变成回忆, 退出了这场生命 ————《如果我变成回忆》"
            ];
            let currentIndex = 0;
            const lyricsElement = document.getElementById('lyricsDisplay');

            function rotateLyrics() {
                if (!lyricsElement) return;
                lyricsElement.style.opacity = '0';
                setTimeout(() => {
                    currentIndex = (currentIndex + 1) % lyrics.length;
                    lyricsElement.textContent = lyrics[currentIndex];
                    lyricsElement.style.opacity = '1';
                }, 500);
            }

            setInterval(rotateLyrics, 10000);
        })();
    </script>
    '''


def get_table_html(title, data, sortable_columns=None):
    """
    生成单个表格的HTML代码，将数据组织成表格。
    :param title: list, 表头标题列表。
    :param data: list of lists, 表格数据。
    :param sortable_columns: list, 可排序的列的索引 (从0开始)。例如 [1, 2, 3]
    """
    if sortable_columns is None:
        sortable_columns = []

    ths = []
    for i, col_name in enumerate(title):
        if i in sortable_columns:
            ths.append(f'<th class="sortable" onclick="sortTable(this.closest(\'table\'), {i})">{col_name}</th>')
        else:
            ths.append(f"<th>{col_name}</th>")

    thead_html = f"""
    <thead>
        <tr>
            {''.join(ths)}
        </tr>
    </thead>
    """

    tbody_rows = []
    for row_data in data:
        tds = [f"<td>{x}</td>" for x in row_data]
        tbody_rows.append(f"<tr>{''.join(tds)}</tr>")

    tbody_html = f"""
    <tbody>
        {''.join(tbody_rows)}
    </tbody>
    """

    return f"""
    <div class="table-container">
        <table class="style-table">
            {thead_html}
            {tbody_html}
        </table>
    </div>
    """


def generate_holdings_cards_html(fund_data_map):
    """
    Generate holdings cards HTML for funds marked as held.
    :param fund_data_map: dict, mapping of fund code to fund data
    :return: str, HTML for holdings cards section
    """
    # Filter held funds
    held_funds = []
    for code, data in fund_data_map.items():
        if data.get('is_hold', False):
            held_funds.append((code, data))

    if not held_funds:
        return ""

    cards_html = []
    for code, data in held_funds:
        fund_name = data.get('fund_name', 'Unknown')
        sectors = data.get('sectors', [])

        # Generate sector tags with icon and gray text (like delete sector popup)
        sector_tags = f'<span style="color: #8b949e; font-size: 12px;"> 🏷️ {", ".join(sectors)}</span>' if sectors else ''

        # Card HTML
        card_html = f"""
        <div class="holding-card" data-code="{code}">
            <div class="holding-card-header">
                <div class="holding-card-title">
                    <div class="holding-card-code">{code}</div>
                    <div class="holding-card-name">{fund_name}</div>
                    {f'<div class="holding-card-sectors">{sector_tags}</div>' if sectors else ''}
                </div>
                <div class="holding-card-badge">⭐</div>
            </div>
            <div class="holding-card-metrics">
                <div class="holding-metric">
                    <div class="holding-metric-label">净值</div>
                    <div class="holding-metric-value" id="card-netvalue-{code}">--</div>
                </div>
                <div class="holding-metric">
                    <div class="holding-metric-label">估值增长</div>
                    <div class="holding-metric-value" id="card-estimated-{code}">--</div>
                </div>
                <div class="holding-metric">
                    <div class="holding-metric-label">日涨幅</div>
                    <div class="holding-metric-value" id="card-daygrowth-{code}">--</div>
                </div>
                <div class="holding-metric">
                    <div class="holding-metric-label">持仓市值</div>
                    <div class="holding-metric-value" id="card-position-{code}">¥0.00</div>
                </div>
            </div>
            <div class="holding-card-footer">
                <div class="holding-footer-item">
                    <div class="holding-footer-label">连涨/跌</div>
                    <div class="holding-footer-value" id="card-consecutive-{code}">--</div>
                </div>
                <div class="holding-footer-item">
                    <div class="holding-footer-label">近30天</div>
                    <div class="holding-footer-value" id="card-monthly-{code}">--</div>
                </div>
                <div class="holding-footer-item">
                    <div class="holding-footer-label">份额</div>
                    <div class="holding-footer-value">
                        <input type="number" step="0.01" min="0"
                               id="card-shares-{code}"
                               class="shares-input"
                               data-code="{code}"
                               placeholder="0"
                               value=""
                               style="width: 60px; padding: 2px 4px; border: 1px solid var(--border); border-radius: 4px; font-size: 11px; background: var(--card-bg); color: var(--text-main);"
                               onchange="updateShares('{code}', this.value)">
                    </div>
                </div>
            </div>
        </div>
        """
        cards_html.append(card_html)

    return f"""
    <div class="holdings-section">
        <div class="holdings-header">
            <div class="holdings-title">💎 Core Holdings</div>
            <div class="holdings-count">{len(held_funds)} Positions</div>
        </div>
        <div class="holdings-grid">
            {''.join(cards_html)}
        </div>
    </div>
    """


def generate_terminal_dashboard_html():
    """
    Generate the Terminal Dashboard HTML (will be populated by JavaScript).
    """
    return """
    <div class="terminal-dashboard" id="terminalDashboard" style="display: none;">
        <div class="stat-group">
            <label>今日预估收益 (EST. TODAY)</label>
            <div class="big-num" id="dashEstGain">¥0.00</div>
            <div class="stat-change" id="dashEstGainPct">0.00% ↑</div>
        </div>
        <div class="stat-group">
            <label>持仓市值 (MARKET VALUE)</label>
            <div class="big-num" id="dashTotalValue">¥0.00</div>
            <div class="stat-change" id="dashHoldingCount">0 只持有中</div>
        </div>
        <div class="stat-group">
            <label>昨日结算 (SETTLED)</label>
            <div class="big-num" id="dashActualGain">¥0.00</div>
            <div class="stat-change" id="dashActualGainPct">0.00% ↓</div>
        </div>
    </div>
    """


def get_full_page_html_sidebar(tabs_data, username=None):
    """Generate full page HTML with sidebar navigation"""
    js_script = get_javascript_code()
    css_style = get_css_style()

    # Get fund data for holdings/watchlist sections
    fund_map = {}
    for tab in tabs_data:
        if tab['id'] == 'fund':
            # Extract fund_map from fund tab - will be passed from fund_server.py
            fund_map = tab.get('fund_map', {})
            break

    # Generate sections for other tabs (hidden by default)
    other_sections_html = ''
    for tab in tabs_data:
        if tab['id'] != 'fund':
            tab_id = tab['id']
            tab_title = tab['title']
            other_sections_html += f'''
                <section class="content-section hidden" id="{tab_id}Section">
                    <div class="section-header">
                        <h2 class="section-heading">{tab_title}</h2>
                    </div>
                    <div class="section-content" id="{tab_id}Content"></div>
                </section>
            '''

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LanFund Terminal</title>
    {css_style}
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
    <!-- Navbar with logo and quote -->
    <nav class="navbar">
        <div class="navbar-brand">
            <img src="/static/1.ico" alt="Logo" class="navbar-logo">
        </div>
        <div class="navbar-quote">
            偶然与巧合, 舞动了蝶翼, 谁的心头风起 ————《如果我们不曾相遇》
        </div>
        <div class="navbar-menu">
            <span class="navbar-item">实时行情</span>
            <a href="https://github.com/lanZzV/fund" target="_blank" class="navbar-item" style="color: #8b949e; text-decoration: none;">点个赞</a>
            <a href="https://github.com/lanZzV/fund/issues" target="_blank" class="navbar-item" style="color: #8b949e; text-decoration: none;">反馈</a>
            {f'<span class="navbar-item" style="color: #3b82f6;">🍎 {username}</span>' if username else ''}
            {f'<a href="/logout" class="navbar-item" style="color: #f85149; text-decoration: none;">退出登录</a>' if username else ''}
        </div>
    </nav>

    <!-- App Container with Sidebar -->
    <div class="app-container-sidebar">
        {get_sidebar_navigation_html()}

        <main class="main-content-area">
            {get_header_bar_html()}
            {get_summary_bar_html()}

            <div class="content-body" id="contentBody">
                <!-- Holdings & Watchlist Sections -->
                {generate_holdings_section_html(fund_map)}
                {generate_watchlist_section_html(fund_map)}

                <!-- Other tab sections (hidden by default) -->
                {other_sections_html}
            </div>
        </main>
    </div>

    <!-- Modals (preserved) -->
    <!-- 板块选择对话框 -->
    <div class="sector-modal" id="sectorModal">
        <div class="sector-modal-content">
            <div class="sector-modal-header">选择板块</div>
            <input type="text" class="sector-modal-search" id="sectorSearch" placeholder="搜索板块名称...">
            <div id="sectorCategories">
                <!-- 板块分类将通过JS动态生成 -->
            </div>
            <div class="sector-modal-footer">
                <button class="btn btn-secondary" onclick="closeSectorModal()">取消</button>
                <button class="btn btn-primary" onclick="confirmSector()">确定</button>
            </div>
        </div>
    </div>

    <!-- 基金选择对话框 -->
    <div class="sector-modal" id="fundSelectionModal">
        <div class="sector-modal-content">
            <div class="sector-modal-header" id="fundSelectionTitle">选择基金</div>
            <input type="text" class="sector-modal-search" id="fundSelectionSearch" placeholder="搜索基金代码或名称...">
            <div id="fundSelectionList" style="max-height: 400px; overflow-y: auto;">
                <!-- 基金列表将通过JS动态生成 -->
            </div>
            <div class="sector-modal-footer">
                <button class="btn btn-secondary" onclick="closeFundSelectionModal()">取消</button>
                <button class="btn btn-primary" id="fundSelectionConfirmBtn" onclick="confirmFundSelection()">确定</button>
            </div>
        </div>
    </div>

    <!-- 确认对话框 -->
    <div class="confirm-dialog" id="confirmDialog">
        <div class="confirm-dialog-content">
            <h3 id="confirmTitle" class="confirm-title"></h3>
            <p id="confirmMessage" class="confirm-message"></p>
            <div class="confirm-actions">
                <button class="btn btn-secondary" onclick="closeConfirmDialog()">取消</button>
                <button class="btn btn-primary" id="confirmBtn">确定</button>
            </div>
        </div>
    </div>

    <!-- 份额设置弹窗 -->
    <div class="sector-modal" id="sharesModal">
        <div class="sector-modal-content" style="max-width: 400px;">
            <div class="sector-modal-header">设置持仓份额</div>
            <div style="padding: 20px;">
                <div style="margin-bottom: 15px;">
                    <label style="display: block; margin-bottom: 8px; color: var(--text-main); font-weight: 500;">基金代码</label>
                    <div id="sharesModalFundCode" style="padding: 10px; background: rgba(59, 130, 246, 0.1); border-radius: 6px; color: #3b82f6; font-weight: 600; font-family: monospace;"></div>
                </div>
                <div style="margin-bottom: 15px;">
                    <label for="sharesModalInput" style="display: block; margin-bottom: 8px; color: var(--text-main); font-weight: 500;">持仓份额</label>
                    <input type="number" id="sharesModalInput" step="0.01" min="0" placeholder="请输入份额"
                           style="width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 6px; font-size: 14px; background: var(--card-bg); color: var(--text-main);">
                </div>
            </div>
            <div class="sector-modal-footer">
                <button class="btn btn-secondary" onclick="closeSharesModal()">取消</button>
                <button class="btn btn-primary" onclick="confirmShares()">确定</button>
            </div>
        </div>
    </div>

    {js_script}
    <script src="/static/js/main.js?v=20260323a"></script>
    <script src="/static/js/sidebar-nav.js"></script>
</body>
</html>'''

    return html


def get_full_page_html(tabs_data, username=None, use_sidebar=False):
    # Use new sidebar layout if requested
    if use_sidebar:
        return get_full_page_html_sidebar(tabs_data, username)

    js_script = get_javascript_code()
    css_style = get_css_style()

    # Generate Tab Headers
    tab_headers = []
    tab_contents = []

    # Check if tabs_data is a list of dicts (new format) or list of strings (old format fallback)
    if isinstance(tabs_data, list) and len(tabs_data) > 0 and isinstance(tabs_data[0], str):
        # Fallback for old format
        return f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>LanFund Dashboard</title>
            {css_style}
        </head>
        <body>
            <div class="app-container">
                <div class="main-content">
                    <div class="dashboard-grid">
                        {''.join(tabs_data)}
                    </div>
                </div>
            </div>
            {js_script}
        </body>
        </html>
        """

    for index, tab in enumerate(tabs_data):
        is_active = 'active' if index == 0 else ''
        tab_id = tab['id']
        tab_title = tab['title']
        content = tab['content']

        tab_headers.append(f"""
            <button class="tab-button {is_active}" onclick="openTab(event, '{tab_id}')">
                {tab_title}
            </button>
        """)

        # 为"自选基金"标签页添加操作区域
        if tab_id == "fund":
            # 使用 enhance_fund_tab_content 函数来添加操作区域（避免重复代码）
            enhanced_content = enhance_fund_tab_content(content)
        else:
            enhanced_content = content

        tab_contents.append(f"""
            <div id="{tab_id}" class="tab-content {is_active}">
                {enhanced_content}
            </div>
        """)

    # Check if we have actual data or if this is initial SSE setup
    has_data = tabs_data and len(tabs_data) > 0 and tabs_data[0].get('content', '').strip()

    if not has_data:
        # Return SSE-enabled loading page
        return get_sse_loading_page(css_style, js_script)

    return f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
        <meta http-equiv="Pragma" content="no-cache">
        <meta http-equiv="Expires" content="0">
        <title>LanFund Dashboard</title>
        {css_style}
    </head>
    <body>
        <nav class="navbar">
            <div class="navbar-brand">BuBu Fund LanFund助手</div>
            <div class="navbar-menu">
                <span class="navbar-item">实时行情</span>
                <a href="https://github.com/lanZzV/fund" target="_blank" class="navbar-item" style="color: #8b949e; text-decoration: none;">点个赞</a>
                <a href="https://github.com/lanZzV/fund/issues" target="_blank" class="navbar-item" style="color: #8b949e; text-decoration: none;">反馈</a>
                {f'<span class="navbar-item" style="color: #3b82f6;">🍎 {username}</span>' if username else ''}
                {f'<a href="/logout" class="navbar-item" style="color: #f85149; text-decoration: none;">退出登录</a>' if username else ''}
            </div>
        </nav>
        
        <div class="app-container">
            <div class="main-content">
                <div class="tabs-header">
                    {''.join(tab_headers)}
                </div>
                <div class="dashboard-grid">
                    {''.join(tab_contents)}
                </div>
            </div>
        </div>

        <!-- 板块选择对话框 -->
        <div class="sector-modal" id="sectorModal">
            <div class="sector-modal-content">
                <div class="sector-modal-header">选择板块</div>
                <input type="text" class="sector-modal-search" id="sectorSearch" placeholder="搜索板块名称...">
                <div id="sectorCategories">
                    <!-- 板块分类将通过JS动态生成 -->
                </div>
                <div class="sector-modal-footer">
                    <button class="btn btn-secondary" onclick="closeSectorModal()">取消</button>
                    <button class="btn btn-primary" onclick="confirmSector()">确定</button>
                </div>
            </div>
        </div>

        <!-- 基金选择对话框 -->
        <div class="sector-modal" id="fundSelectionModal">
            <div class="sector-modal-content">
                <div class="sector-modal-header" id="fundSelectionTitle">选择基金</div>
                <input type="text" class="sector-modal-search" id="fundSelectionSearch" placeholder="搜索基金代码或名称...">
                <div id="fundSelectionList" style="max-height: 400px; overflow-y: auto;">
                    <!-- 基金列表将通过JS动态生成 -->
                </div>
                <div class="sector-modal-footer">
                    <button class="btn btn-secondary" onclick="closeFundSelectionModal()">取消</button>
                    <button class="btn btn-primary" id="fundSelectionConfirmBtn" onclick="confirmFundSelection()">确定</button>
                </div>
            </div>
        </div>

        <!-- 确认对话框 -->
        <div class="confirm-dialog" id="confirmDialog">
            <div class="confirm-dialog-content">
                <h3 id="confirmTitle" class="confirm-title"></h3>
                <p id="confirmMessage" class="confirm-message"></p>
                <div class="confirm-actions">
                    <button class="btn btn-secondary" onclick="closeConfirmDialog()">取消</button>
                    <button class="btn btn-primary" id="confirmBtn">确定</button>
                </div>
            </div>
        </div>

        {js_script}
    </body>
    </html>
    """


def get_sse_loading_page(css_style, js_script):
    """Return a loading page that will be updated via SSE"""
    return f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>LanFund Dashboard - Loading</title>
        {css_style}
        <style>
            .loading-container {{
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 100%;
                padding: 2rem;
            }}
            .navbar-brand {{
                display: flex;
                align-items: center;
            }}
            .navbar-logo {{
                width: 32px;
                height: 32px;
                margin-right: 12px;
            }}
            .loading-spinner {{
                border: 4px solid #f3f3f3;
                border-top: 4px solid var(--bloomberg-blue);
                border-radius: 50%;
                width: 50px;
                height: 50px;
                animation: spin 1s linear infinite;
            }}
            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
            .loading-status {{
                margin-top: 1rem;
                font-size: 0.9rem;
                color: #666;
            }}
            .task-list {{
                margin-top: 1rem;
                max-width: 400px;
            }}
            .task-item {{
                padding: 0.5rem;
                margin: 0.3rem 0;
                border-radius: 4px;
                background: #f5f5f5;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            .task-item.completed {{
                background: #d4edda;
                color: #155724;
            }}
            .task-item.error {{
                background: #f8d7da;
                color: #721c24;
            }}
        </style>
    </head>
    <body>
        <nav class="navbar">
            <div class="navbar-brand">
                <img src="/static/1.ico" alt="Logo" class="navbar-logo">
                <span>BuBu Fund LanFund助手</span>
            </div>
            <div class="navbar-menu">
                <span class="navbar-item">加载中...</span>
                <a href="https://github.com/lanZzV/fund" target="_blank" class="navbar-item" style="color: #8b949e; text-decoration: none;">点个赞</a>
                <a href="https://github.com/lanZzV/fund/issues" target="_blank" class="navbar-item" style="color: #8b949e; text-decoration: none;">反馈</a>
            </div>
        </nav>
        
        <div class="app-container">
            <div class="main-content">
                <div class="loading-container">
                    <div class="loading-spinner"></div>
                    <div class="loading-status" id="status">正在连接数据源...</div>
                    <div class="task-list" id="task-list"></div>
                </div>
            </div>
        </div>

        <script>
        const eventSource = new EventSource('/fund' + window.location.search);
        const taskList = document.getElementById('task-list');
        const statusEl = document.getElementById('status');
        const taskElements = {{}};

        eventSource.addEventListener('message', function(e) {{
            try {{
                const data = JSON.parse(e.data);
                
                if (data.type === 'init') {{
                    statusEl.textContent = '正在加载数据模块...';
                    data.tasks.forEach(taskName => {{
                        const taskEl = document.createElement('div');
                        taskEl.className = 'task-item';
                        taskEl.innerHTML = `<span>${{getTaskTitle(taskName)}}</span><span>⏳</span>`;
                        taskList.appendChild(taskEl);
                        taskElements[taskName] = taskEl;
                    }});
                }}
                else if (data.type === 'task_complete') {{
                    if (taskElements[data.name]) {{
                        taskElements[data.name].className = 'task-item completed';
                        taskElements[data.name].querySelector('span:last-child').textContent = '✓';
                    }}
                }}
                else if (data.type === 'error') {{
                    if (taskElements[data.name]) {{
                        taskElements[data.name].className = 'task-item error';
                        taskElements[data.name].querySelector('span:last-child').textContent = '✗';
                    }}
                }}
                else if (data.type === 'complete') {{
                    statusEl.textContent = '加载完成！正在渲染页面...';
                    eventSource.close();
                    // Replace entire page with the complete HTML
                    document.open();
                    document.write(data.html);
                    document.close();
                }}
            }} catch (err) {{
                console.error('SSE parse error:', err);
            }}
        }});

        eventSource.addEventListener('error', function(e) {{
            statusEl.textContent = '连接错误，正在重试...';
            console.error('SSE error:', e);
        }});

        function getTaskTitle(taskName) {{
            const titles = {{
                'kx': '7*24快讯',
                'marker': '全球指数',
                'real_time_gold': '实时贵金属',
                'gold': '历史金价',
                'seven_A': '成交量趋势',
                'A': '上证分时',
                'fund': '自选基金',
                'bk': '行业板块'
            }};
            return titles[taskName] || taskName;
        }}
        </script>
    </body>
    </html>
    """


def get_sidebar_navigation_html():
    """Generate 70px sidebar with 9 section icons"""
    sections = [
        {'id': 'news', 'icon': '📰', 'label': '快讯', 'tab_id': 'kx'},
        {'id': 'indices', 'icon': '📊', 'label': '指数', 'tab_id': 'marker'},
        {'id': 'gold-realtime', 'icon': '🥇', 'label': '贵金属', 'tab_id': 'real_time_gold'},
        {'id': 'gold-history', 'icon': '📈', 'label': '金价', 'tab_id': 'gold'},
        {'id': 'volume', 'icon': '📉', 'label': '成交量', 'tab_id': 'seven_A'},
        {'id': 'timing', 'icon': '🔴', 'label': '分时', 'tab_id': 'A'},
        {'id': 'funds', 'icon': '💼', 'label': '基金', 'tab_id': 'fund'},
        {'id': 'sectors', 'icon': '🏢', 'label': '板块', 'tab_id': 'bk'},
        {'id': 'query', 'icon': '🔍', 'label': '查询', 'tab_id': 'select_fund'},
    ]

    html = '<aside class="sidebar-nav" id="sidebarNav">\n'
    html += '  <div class="sidebar-icons">\n'

    for i, section in enumerate(sections):
        active = ' active' if i == 6 else ''  # funds section active by default
        html += f'''    <button class="sidebar-icon{active}" data-section="{section['id']}" data-tab-id="{section['tab_id']}">
      <i class="icon">{section['icon']}</i>
      <span class="icon-label">{section['label']}</span>
    </button>\n'''

    html += '''    <button class="sidebar-toggle" id="sidebarToggle">
      <span>▶</span>
      <span class="toggle-text">展开</span>
    </button>
'''
    html += '  </div>\n'
    html += '</aside>\n'

    return html


def get_header_bar_html(section_title='自选基金'):
    """Generate header bar with section title and market status"""
    return f'''<header class="content-header">
  <div class="header-left">
    <h1 class="section-title" id="sectionTitle">{section_title}</h1>
    <span class="market-status">
      <span class="status-dot"></span>
      <span id="marketStatusText">市场开盘中</span>
    </span>
  </div>
  <div class="header-right">
    <span class="last-update" id="lastUpdate">更新于 --:--:--</span>
  </div>
</header>'''


def get_summary_bar_html():
    """Generate 4-column summary bar (populated by JavaScript)"""
    return '''<section class="summary-bar" id="summaryBar">
  <div class="summary-card">
    <div class="summary-label">总持仓</div>
    <div class="summary-value" id="summaryTotalValue">¥0.00</div>
    <div class="summary-change neutral" id="summaryTotalChange">--</div>
  </div>
  <div class="summary-card">
    <div class="summary-label">今日预估</div>
    <div class="summary-value" id="summaryEstGain">¥0.00</div>
    <div class="summary-change neutral" id="summaryEstChange">+0.00%</div>
  </div>
  <div class="summary-card">
    <div class="summary-label">已结算</div>
    <div class="summary-value" id="summaryActualGain">¥0.00</div>
    <div class="summary-change neutral" id="summaryActualChange">+0.00%</div>
  </div>
  <div class="summary-card">
    <div class="summary-label">持仓数量</div>
    <div class="summary-value" id="summaryHoldCount">0 只</div>
    <div class="summary-change neutral">已标记</div>
  </div>
</section>'''


def generate_fund_row_html(fund_code, fund_data, is_held=True):
    """Generate a single fund row (replaces holdings cards)"""
    import html

    # Extract fund data
    name = fund_data.get('fund_name', '')
    sectors = fund_data.get('sectors', [])
    shares = fund_data.get('shares', 0)

    # Escape fund_code and name for safe HTML/JavaScript usage
    safe_code = html.escape(str(fund_code))
    safe_name = html.escape(str(name))

    # Build sector tags
    sector_tags = ''
    if is_held:
        sector_tags += '<span class="tag tag-hold">⭐ 持有</span>'
    if sectors:
        # Display sectors with icon and gray text (like delete sector popup style)
        safe_sectors = html.escape(', '.join(str(s) for s in sectors))
        sector_tags += f'<span style="color: #8b949e; font-size: 12px;"> 🏷️ {safe_sectors}</span>'

    # Shares input (only for held funds)
    shares_html = ''
    if is_held:
        shares_html = f'''<div class="metric metric-shares">
        <span class="metric-label">持仓份额</span>
        <input type="number" class="shares-input" id="shares_{safe_code}"
               value="{shares}" step="0.01" min="0"
               onchange="updateShares('{safe_code}', this.value)">
      </div>'''

    return f'''<div class="fund-row" data-code="{safe_code}">
  <div class="fund-row-main">
    <div class="fund-info">
      <div class="fund-code-name">
        <span class="fund-code">{safe_code}</span>
        <span class="fund-name">{safe_name}</span>
      </div>
      <div class="fund-tags">{sector_tags}</div>
    </div>
    <div class="fund-metrics" id="metrics_{safe_code}">
      <!-- Metrics populated by JavaScript -->
      <div class="metric"><span class="metric-label">净值</span><span class="metric-value">--</span></div>
      <div class="metric"><span class="metric-label">估值增长</span><span class="metric-value">--</span></div>
      <div class="metric"><span class="metric-label">日涨幅</span><span class="metric-value">--</span></div>
      <div class="metric"><span class="metric-label">连涨/跌</span><span class="metric-value">--</span></div>
      <div class="metric"><span class="metric-label">近30天</span><span class="metric-value">--</span></div>
      {shares_html}
    </div>
  </div>
  <div class="fund-row-actions">
    <button class="btn-icon" onclick="toggleFundExpand('{safe_code}')" title="展开/收起">
      <span>▼</span>
    </button>
  </div>
</div>'''


def generate_holdings_section_html(fund_map):
    """Generate Core Holdings section with held funds"""
    held_funds = {code: data for code, data in fund_map.items() if data.get('is_hold', False)}

    html = '''<section class="content-section" id="holdingsSection">
  <div class="section-header">
    <h2 class="section-heading">
      <span class="heading-icon">💎</span>
      核心持仓
    </h2>
    <div class="section-meta">
      <span class="fund-count" id="holdingsCount">''' + str(len(held_funds)) + ''' 只基金</span>
    </div>
  </div>
  <div class="section-content" id="holdingsContent">'''

    for code, data in held_funds.items():
        html += generate_fund_row_html(code, data, is_held=True)

    if not held_funds:
        html += '<div class="empty-state">暂无持仓基金</div>'

    html += '  </div>\n</section>'
    return html


def generate_watchlist_section_html(fund_map):
    """Generate Market Watchlist section with non-held funds"""
    watchlist_funds = {code: data for code, data in fund_map.items() if not data.get('is_hold', False)}

    html = '''<section class="content-section" id="watchlistSection">
  <div class="section-header">
    <h2 class="section-heading">
      <span class="heading-icon">📋</span>
      市场观察
    </h2>
    <div class="section-meta">
      <span class="fund-count" id="watchlistCount">''' + str(len(watchlist_funds)) + ''' 只基金</span>
    </div>
  </div>
  <div class="section-content" id="watchlistContent">'''

    for code, data in watchlist_funds.items():
        html += generate_fund_row_html(code, data, is_held=False)

    if not watchlist_funds:
        html += '<div class="empty-state">暂无观察基金</div>'

    html += '  </div>\n</section>'
    return html


def get_css_style():
    return r"""
    <style>
        :root {
            /* Light Theme (白底黑字) */
            --terminal-bg: #ffffff;
            --card-bg: #ffffff;
            --border: #e5e7eb;
            --accent: #3b82f6;
            --text-main: #111827;
            --text-dim: #6b7280;
            --text-muted: #9ca3af;
            --up: #ef4444;    /* 专业红 */
            --down: #10b981;  /* 专业绿 */
            --font-mono: 'JetBrains Mono', 'Courier New', Consolas, monospace;
            --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: var(--font-family);
            background-color: var(--terminal-bg);
            color: var(--text-main);
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
            min-height: 100vh;
        }

        /* ==================== TERMINAL DASHBOARD (资产看板) ==================== */
        .terminal-dashboard {
            display: grid;
            grid-template-columns: 1.5fr 1fr 1fr;
            gap: 20px;
            background: var(--card-bg);
            padding: 24px;
            border-radius: 12px;
            border: 1px solid var(--border);
            margin-bottom: 24px;
        }

        .stat-group label {
            color: var(--text-dim);
            font-size: 13px;
            display: block;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-weight: 600;
        }

        .stat-group .big-num {
            font-family: var(--font-mono);
            font-size: 32px;
            font-weight: 700;
            line-height: 1.2;
            margin-bottom: 6px;
        }

        .stat-group .big-num.up {
            color: var(--up);
        }

        .stat-group .big-num.down {
            color: var(--down);
        }

        .stat-group .stat-change {
            font-size: 14px;
            font-family: var(--font-mono);
            color: var(--text-dim);
        }

        .stat-group .stat-change.up {
            color: var(--up);
        }

        .stat-group .stat-change.down {
            color: var(--down);
        }

        /* ==================== FUND GLASS CARDS (基金玻璃态卡片) ==================== */
        .holdings-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 16px;
            margin-top: 20px;
        }

        .fund-glass-card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            padding: 16px;
            border-radius: 10px;
            transition: all 0.2s ease;
            position: relative;
        }

        .fund-glass-card:hover {
            border-color: var(--accent);
            background: #1c222d;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 12px;
        }

        .card-title {
            font-weight: 600;
            font-size: 15px;
            color: var(--text-main);
            margin-bottom: 4px;
        }

        .card-code {
            color: var(--text-dim);
            font-family: var(--font-mono);
            font-size: 12px;
        }

        .card-code .tag {
            display: inline-block;
            background: rgba(59, 130, 246, 0.1);
            color: var(--accent);
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
            margin-left: 6px;
        }

        .card-badge {
            font-size: 20px;
            line-height: 1;
        }

        .card-main-data {
            display: flex;
            align-items: baseline;
            gap: 10px;
            margin: 10px 0;
        }

        .est-pct {
            font-family: var(--font-mono);
            font-size: 24px;
            font-weight: 700;
        }

        .est-pct.up {
            color: var(--up);
        }

        .est-pct.down {
            color: var(--down);
        }

        .card-details {
            display: grid;
            grid-template-columns: 1fr 1fr;
            border-top: 1px solid var(--border);
            padding-top: 12px;
            gap: 8px;
        }

        .detail-item {
            font-size: 12px;
            color: var(--text-dim);
        }

        .detail-item b {
            color: var(--text-main);
            font-family: var(--font-mono);
            display: block;
            font-size: 14px;
            margin-top: 4px;
        }

        .detail-item b.up {
            color: var(--up);
        }

        .detail-item b.down {
            color: var(--down);
        }

        /* Navbar */
        .navbar {
            background-color: var(--card-bg);
            color: var(--text-main);
            padding: 0.8rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
        }

        .navbar-brand {
            font-size: 1.25rem;
            font-weight: 600;
            letter-spacing: -0.02em;
            background: linear-gradient(135deg, var(--accent), var(--down));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            display: flex;
            align-items: center;
            flex: 0 0 auto;
        }

        .navbar-logo {
            width: 32px;
            height: 32px;
            margin-right: 0;
            vertical-align: middle;
            border-radius: 6px;
            object-fit: contain;
        }

        .navbar-quote {
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
        }

        .navbar-menu {
            display: flex;
            gap: 1rem;
            align-items: center;
        }

        .navbar-item {
            font-weight: 500;
            font-size: 0.9rem;
        }

        /* Layout */
        .app-container {
            display: flex;
            min-height: calc(100vh - 60px); /* Subtract navbar height */
            overflow: hidden; /* Prevent body scroll */
        }

        .tabs-header {
            display: flex;
            border-bottom: 2px solid var(--border);
            margin-bottom: 1rem;
            background: var(--card-bg);
            padding: 0 1rem;
        }

        .tab-button {
            padding: 12px 24px;
            background: none;
            border: none;
            cursor: pointer;
            font-weight: 500;
            text-align: center;
            position: relative;
            transition: all 0.2s;
            color: var(--text-dim);
            font-size: 0.9rem;
            border-bottom: 2px solid transparent;
        }

        .tab-button:hover {
            color: var(--text-main);
            background-color: var(--card-bg);
        }

        .tab-button.active {
            color: var(--text-main);
            border-bottom: 2px solid var(--accent);
        }

        .tab-content {
            display: none;
            padding: 1rem 0;
            animation: fadeIn 0.2s ease-in-out;
        }

        .tab-content.active {
            display: block;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(5px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .dashboard-grid {
            display: flex;
            flex-direction: column;
            gap: 2rem;
            max-width: 1200px;
            margin: 0 auto;
            padding-bottom: 40px;
        }

        .main-content {
            padding: 2rem;
            flex: 1;
            margin: 0;
            overflow-y: auto;
            height: calc(100vh - 60px);
            background-color: var(--terminal-bg);
        }

        /* Tables */
        .table-container {
            background: var(--card-bg);
            border: 1px solid var(--border);
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            margin-bottom: 1rem;
            border-radius: 12px;
        }

        .style-table {
            width: 100%;
            min-width: max-content;
            border-collapse: collapse;
            font-size: 0.9rem;
            white-space: nowrap;
        }

        .style-table th {
            text-align: center;
            padding: 12px 16px;
            background-color: var(--card-bg);
            font-weight: 600;
            color: var(--text-main);
            border-bottom: 1px solid var(--border);
            white-space: nowrap;
            letter-spacing: 0.01em;
        }

        .style-table td {
            padding: 12px 16px;
            border-bottom: 1px solid var(--border);
            color: var(--text-main);
            font-weight: 400;
            text-align: center;
            white-space: nowrap;
        }

        .style-table tbody tr:hover {
            background-color: var(--card-bg);
        }

        /* 最后一行的下划线加粗 */
        .style-table tbody tr:last-child td {
            border-bottom: 1px solid var(--border);
        }

        /* Sortable Headers */
        .style-table th.sortable {
            cursor: pointer;
            user-select: none;
            transition: color 0.2s;
        }

        .style-table th.sortable:hover {
            color: var(--accent);
        }

        .style-table th.sortable::after {
            content: '↕';
            display: inline-block;
            margin-left: 8px;
            font-size: 0.8em;
            color: var(--text-muted);
        }

        .style-table th.sorted-asc::after {
            content: '↑';
            color: var(--accent);
        }

        .style-table th.sorted-desc::after {
            content: '↓';
            color: var(--accent);
        }

        /* Numeric Columns Alignment & Font */
        .style-table th:nth-child(n+2),
        .style-table td:nth-child(n+2) {
            text-align: center;
            vertical-align: middle;
            font-family: var(--font-mono);
            font-variant-numeric: tabular-nums;
        }

        /* Sticky first column for mobile/tablet */
        @media (max-width: 1024px) {
            .style-table th:first-child,
            .style-table td:first-child {
                position: sticky;
                left: 0;
                background-color: var(--terminal-bg);
                z-index: 10;
                box-shadow: 2px 0 4px rgba(0,0,0,0.1);
            }

            .style-table th:first-child {
                z-index: 20;
                background-color: var(--card-bg);
            }

            .style-table tbody tr:hover td:first-child {
                background-color: var(--card-bg);
            }
        }

        /* Colors */
        .positive {
            color: var(--up) !important;
            font-weight: 600;
        }

        .negative {
            color: var(--down) !important;
            font-weight: 600;
        }
        
        /* Specific tweaks for small screens */
        @media (max-width: 768px) {
            body {
                font-size: 14px;
            }

            /* Navbar */
            .navbar {
                padding: 0.6rem 1rem;
                flex-wrap: wrap;
                gap: 0.5rem;
            }

            .navbar-brand {
                font-size: 1rem;
                flex: 0 0 auto;
                min-width: auto;
                display: flex;
                align-items: center;
            }

            .navbar-logo {
                width: 24px;
                height: 24px;
                margin-right: 0;
            }

            .navbar-quote {
                flex: 1;
                font-size: 0.75rem;
                font-weight: 500;
                padding: 0 0.5rem;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                text-align: center;
            }

            .navbar-menu {
                display: flex;
                align-items: center;
                gap: 0.5rem;
                width: 100%;
                justify-content: flex-end;
            }

            .navbar-item {
                font-size: 0.75rem;
            }

            #toggle-chat-btn {
                font-size: 0.75rem !important;
                padding: 0 8px !important;
            }

            /* App container */
            .app-container {
                flex-direction: column;
                overflow: visible;
            }

            .main-content {
                height: auto;
                min-height: calc(100vh - 100px);
                padding: 1rem;
                overflow-y: visible;
            }

            .dashboard-grid {
                max-width: 100%;
                padding-bottom: 20px;
            }

            /* Tabs */
            .tabs-header {
                padding: 0;
                overflow-x: auto;
                -webkit-overflow-scrolling: touch;
                scrollbar-width: none;
            }

            .tabs-header::-webkit-scrollbar {
                display: none;
            }

            .tab-button {
                padding: 10px 12px;
                font-size: 0.8rem;
                white-space: nowrap;
                flex: 0 0 auto;
                min-width: 80px;
            }

            /* Tables - Enable horizontal scroll */
            .table-container {
                overflow-x: auto;
                -webkit-overflow-scrolling: touch;
                border-radius: 0;
            }

            .style-table {
                font-size: 0.75rem;
                min-width: 100%;
            }

            .style-table th {
                padding: 8px 10px;
                font-size: 0.75rem;
                white-space: nowrap;
            }

            .style-table td {
                padding: 8px 10px;
                font-size: 0.75rem;
                white-space: nowrap;
            }

            /* Make numeric columns more compact on mobile */
            .style-table th:nth-child(n+4),
            .style-table td:nth-child(n+4) {
                padding: 8px 6px;
                font-size: 0.7rem;
                white-space: nowrap;
            }

            /* Ensure table container supports horizontal scroll on small screens */
            .table-container {
                overflow-x: auto;
                -webkit-overflow-scrolling: touch;
            }

            .style-table {
                min-width: max-content;
            }

            /* Loading page adjustments */
            .loading-container {
                padding: 1rem;
            }

            .task-list {
                max-width: 100%;
            }

            .task-item {
                font-size: 0.85rem;
            }
        }

        /* Fund Operations Panel */
        .fund-operations {
            position: sticky;
            top: 0;
            background: var(--card-bg);
            backdrop-filter: blur(10px);
            padding: 16px;
            border-radius: 12px;
            box-shadow: 0 4px 16px rgba(102, 126, 234, 0.15);
            margin-bottom: 20px;
            z-index: 100;
            border: 1px solid var(--border);
        }

        .operation-group {
            display: flex;
            gap: 12px;
            align-items: center;
            margin-bottom: 12px;
            flex-wrap: wrap;
        }

        .operation-group:last-child {
            margin-bottom: 0;
        }

        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            color: white;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s ease;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            border: 1px solid transparent;
        }

        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
        }

        .btn:active {
            transform: translateY(0);
        }

        .btn-primary {
            background: var(--accent);
            border-color: var(--accent);
        }

        .btn-primary:hover {
            background: var(--accent);
            border-color: var(--accent);
        }

        .btn-success {
            color: #ffffff;
            background-color: var(--down);
            border-color: var(--down);
        }

        .btn-success:hover {
            background-color: #059669;
            border-color: #059669;
        }

        .btn-warning {
            color: #ffffff;
            background-color: #f59e0b;
            border-color: #f59e0b;
        }

        .btn-warning:hover {
            background-color: #d97706;
            border-color: #d97706;
        }

        .btn-info {
            color: #ffffff;
            background: var(--accent);
            border-color: var(--accent);
        }

        .btn-info:hover {
            background: var(--accent);
            border-color: var(--accent);
        }

        .btn-danger {
            color: #ffffff;
            background-color: var(--up);
            border-color: var(--up);
        }

        .btn-danger:hover {
            background-color: #dc2626;
            border-color: #dc2626;
        }

        .btn-secondary {
            color: #ffffff;
            background-color: #6b7280;
            border-color: #6b7280;
        }

        .btn-secondary:hover {
            background-color: #4b5563;
            border-color: #4b5563;
        }

        /* 份额按钮样式 */
        .shares-button {
            padding: 6px 12px;
            background: #3b82f6;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            transition: all 0.2s;
        }

        .shares-button:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
        }

        .shares-button:active {
            transform: translateY(0);
        }

        #fundCodesInput {
            flex: 1;
            min-width: 250px;
            padding: 8px 12px;
            border: 1px solid var(--border);
            border-radius: 6px;
            font-size: 14px;
            outline: none;
            transition: border-color 0.2s, box-shadow 0.2s;
            color: var(--text-main);
            background-color: var(--terminal-bg);
        }

        #fundCodesInput:focus {
            border-color: var(--accent);
            box-shadow: 0 0 0 3px rgba(9, 105, 218, 0.3);
        }

        #fundCodesInput::placeholder {
            color: var(--text-muted);
        }

        .selected-info {
            margin-left: auto;
            color: var(--text-dim);
            font-size: 14px;
        }

        .selected-info strong {
            color: var(--accent);
            font-size: 16px;
        }

        /* Checkbox styling */
        .fund-checkbox {
            width: 18px;
            height: 18px;
            cursor: pointer;
            accent-color: var(--accent);
        }

        #selectAll {
            width: 18px;
            height: 18px;
            cursor: pointer;
            accent-color: var(--accent);
        }

        /* Sector Modal */
        .sector-modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }

        .sector-modal.active {
            display: flex;
        }

        .sector-modal-content {
            background: var(--terminal-bg);
            padding: 24px;
            border: 1px solid var(--border);
            border-radius: 6px;
            width: 90%;
            max-width: 600px;
            max-height: 80vh;
            overflow-y: auto;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
        }

        .sector-modal-header {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 20px;
            color: var(--text-main);
        }

        .sector-modal-search {
            width: 100%;
            padding: 8px 12px;
            border: 1px solid var(--border);
            border-radius: 6px;
            margin-bottom: 16px;
            font-size: 14px;
            color: var(--text-main);
            background-color: var(--terminal-bg);
        }

        .sector-modal-search:focus {
            border-color: var(--accent);
            outline: none;
            box-shadow: 0 0 0 3px rgba(9, 105, 218, 0.3);
        }

        .sector-category {
            margin-bottom: 16px;
        }

        .sector-category-header {
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 8px;
            color: var(--accent);
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .sector-category-header:hover {
            text-decoration: underline;
        }

        .sector-items {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
            gap: 8px;
        }

        .sector-item {
            padding: 8px 12px;
            border: 1px solid var(--border);
            border-radius: 6px;
            cursor: pointer;
            text-align: center;
            transition: all 0.2s;
            font-size: 13px;
            color: var(--text-main);
            background-color: var(--terminal-bg);
        }

        .sector-item:hover {
            background-color: var(--card-bg);
            border-color: var(--accent);
        }

        .sector-item.selected {
            background-color: var(--accent);
            color: white;
            border-color: var(--accent);
        }

        .sector-modal-footer {
            display: flex;
            gap: 12px;
            justify-content: flex-end;
            margin-top: 20px;
        }

        /* Floating Action Bar */
        .floating-action-bar {
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: var(--terminal-bg);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 12px 20px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            display: none;
            z-index: 100;
            gap: 8px;
            align-items: center;
        }

        .floating-action-bar.visible {
            display: flex;
        }

        /* Add Fund Input */
        .add-fund-input {
            display: flex;
            gap: 12px;
            align-items: center;
            margin-bottom: 20px;
            padding: 16px;
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 6px;
        }

        /* Confirm Dialog */
        .confirm-dialog {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 1000;
        }

        .confirm-dialog.active {
            display: flex;
        }

        .confirm-dialog-content {
            background: var(--terminal-bg);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 24px;
            max-width: 400px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
        }

        .confirm-title {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 12px;
            color: var(--text-main);
        }

        .confirm-message {
            font-size: 14px;
            color: var(--text-dim);
            margin-bottom: 20px;
            line-height: 1.5;
        }

        .confirm-actions {
            display: flex;
            gap: 12px;
            justify-content: flex-end;
        }

        /* Responsive adjustments */
        @media (max-width: 768px) {
            .floating-action-bar {
                flex-wrap: wrap;
                bottom: 10px;
                left: 10px;
                right: 10px;
                transform: none;
            }

            .add-fund-input {
                flex-direction: column;
                align-items: stretch;
            }

            .btn {
                justify-content: center;
            }

            #fundCodesInput {
                min-width: 100%;
            }

            .selected-info {
                margin-left: 0;
                text-align: center;
            }
        }
    </style>
    """


def get_javascript_code():
    return r"""
    <!-- Import Map for ESM modules -->
    <script>
    // Polyfill process for React libraries
    window.process = {
        env: {
            NODE_ENV: 'production'
        }
    };
    window.onerror = function(message, source, lineno, colno, error) {
        console.error("Global Error Caught:", error);
        const root = document.getElementById('pro-chat-root');
        if (root && root.innerHTML === '') {
            root.innerHTML = `<div style="padding:20px; color:red;">
                <h3>Failed to load Pro Chat</h3>
                <p>Error: ${message}</p>
                <p>Dependencies might be missing in CDN mode.</p>
                <button onclick="location.reload()" style="padding:5px 10px; margin-top:10px;">Retry</button>
            </div>`;
        }
    };
    </script>
    <link rel="stylesheet" href="https://unpkg.com/quikchat/dist/quikchat.css">
    <script src="https://unpkg.com/quikchat"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>

    <script>
    document.addEventListener('DOMContentLoaded', function() {
        // Initialize Auto Colorize
        autoColorize();

        // 🔧 独立的对话历史管理 - 不依赖 QuikChat 内部状态
        let conversationHistory = [];

        // Initialize QuikChat
        const chat = new quikchat('#pro-chat-root', async (instance, message) => {
            // Display user message immediately
            instance.messageAddNew(message, 'You', 'right');
            
            // 🔧 添加用户消息到独立历史
            conversationHistory.push({
                role: 'user',
                content: message
            });
            
            console.log("💬 Current conversation history:", conversationHistory);
            
            // 不再收集前端context，所有数据由后端获取
            console.log("Sending message to backend (context will be fetched by backend)");

            // Create loading indicator
            const loadingHtml = '<div class="ai-loading-indicator" style="display: flex; align-items: center; gap: 10px;"><div class="typing-indicator"><span></span><span></span><span></span></div><span style="color: #999;">AI Analyst is thinking...</span></div>';
            instance.messageAddNew(loadingHtml, 'System', 'left');

            try {
                let streamingContent = '';
                let hasReceivedContent = false;
                let contentDisplayed = false;
                let loadingRemoved = false;
                let currentStepElement = null; // Track current step status element
                
                // Helper to remove loading indicator
                function removeLoadingIndicator() {
                    if (!loadingRemoved) {
                        try {
                            // Find and remove by class name
                            const loadingElements = document.querySelectorAll('.ai-loading-indicator');
                            loadingElements.forEach(el => {
                                const messageDiv = el.closest('.quikchat-message');
                                if (messageDiv) {
                                    messageDiv.remove();
                                }
                            });
                            loadingRemoved = true;
                            console.log('Loading indicator removed');
                        } catch (e) {
                            console.warn('Failed to remove loading indicator:', e);
                        }
                    }
                }
                
                // Helper to show step status
                function showStepStatus(message, icon = '⏳') {
                    // Remove previous step if exists
                    if (currentStepElement) {
                        try {
                            currentStepElement.remove();
                            console.log('Previous step removed');
                        } catch (e) {
                            console.warn('Failed to remove previous step:', e);
                        }
                    }
                    
                    // Create new step status
                    const stepHtml = `<div style="display: flex; align-items: center; gap: 8px; padding: 4px 8px; background: rgba(13,138,188,0.1); border-radius: 4px;">
                        <span style="font-size: 1.2em;">${icon}</span>
                        <span style="color: #42a5f5; font-size: 0.9em;">${message}</span>
                    </div>`;
                    
                    instance.messageAddNew(stepHtml, 'System', 'left');
                    
                    // Get the newly added element
                    setTimeout(() => {
                        const allMessages = document.querySelectorAll('.quikchat-message');
                        currentStepElement = allMessages[allMessages.length - 1];
                    }, 10);
                }
                
                // Use fetch with SSE
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        message: message,
                        history: conversationHistory.slice(0, -1)  // 🔧 使用独立历史，排除刚添加的当前消息
                    })
                });

                if (!response.ok) {
                    instance.messageAddNew('Network Error: ' + response.statusText, 'System', 'left');
                    return;
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';
                let lastChunkTime = Date.now();
                
                // Timeout checker
                const timeoutChecker = setInterval(() => {
                    const timeSinceLastChunk = Date.now() - lastChunkTime;
                    if (timeSinceLastChunk > 30000) { // 30 seconds timeout
                        console.warn('Stream timeout detected');
                        clearInterval(timeoutChecker);
                        reader.cancel();
                    }
                }, 5000);
                
                // Helper function to detect and render content
                function renderContent(content) {
                    const looksLikeHTML = content.trim().startsWith('<') && /<[^>]+>/.test(content);
                    if (looksLikeHTML) {
                        return content;
                    } else {
                        try {
                            if (typeof marked !== 'undefined') {
                                return marked.parse(content);
                            }
                        } catch (e) {
                            console.warn('Marked.js not available or parsing failed:', e);
                        }
                        return content;
                    }
                }
                
                // Helper function to display content with typewriter effect
                function displayWithTypewriter(content) {
                    if (contentDisplayed) return; // Prevent duplicate display
                    contentDisplayed = true;
                    
                    // 🔧 重要：将AI的真实回复保存到独立历史中
                    conversationHistory.push({
                        role: 'assistant',
                        content: content  // 保存原始内容（HTML格式）
                    });
                    console.log('✅ AI response saved to conversation history');
                    console.log('💬 Updated conversation history:', conversationHistory);
                    
                    const uniqueId = 'typewriter-' + Date.now();
                    instance.messageAddNew(`<div id="${uniqueId}"></div>`, 'AI Analyst', 'left');
                    
                    setTimeout(() => {
                        const typewriterDiv = document.getElementById(uniqueId);
                        if (typewriterDiv) {
                            const contentLength = content.length;
                            let currentIndex = 0;
                            
                            let speed, interval;
                            if (contentLength < 500) {
                                speed = 15;
                                interval = 20;
                            } else if (contentLength < 2000) {
                                speed = 30;
                                interval = 15;
                            } else {
                                speed = 50;
                                interval = 10;
                            }
                            
                            console.log(`Typewriter: ${contentLength} chars, speed=${speed}, interval=${interval}ms`);

                            const typewriterInterval = setInterval(() => {
                                if (currentIndex < contentLength) {
                                    currentIndex += speed;
                                    typewriterDiv.textContent = content.substring(0, Math.min(currentIndex, contentLength));

                                    // Auto-scroll to keep the message visible
                                    typewriterDiv.scrollIntoView({ behavior: 'smooth', block: 'end' });
                                } else {
                                    const renderedContent = renderContent(content);
                                    typewriterDiv.innerHTML = renderedContent;
                                    typewriterDiv.removeAttribute('id');
                                    clearInterval(typewriterInterval);

                                    // Final scroll to ensure full content is visible
                                    typewriterDiv.scrollIntoView({ behavior: 'smooth', block: 'end' });
                                    console.log('Content rendered');
                                }
                            }, interval);
                        }
                    }, 50);
                }
                
                while (true) {
                    const { done, value } = await reader.read();
                    
                    if (done) {
                        clearInterval(timeoutChecker);
                        break;
                    }
                    
                    lastChunkTime = Date.now();
                    buffer += decoder.decode(value, { stream: true });
                    
                    // Process SSE messages
                    const lines = buffer.split('\n');
                    buffer = lines.pop(); // Keep incomplete line in buffer
                    
                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            try {
                                const data = JSON.parse(line.substring(6));
                                
                                if (data.type === 'status') {
                                    // Remove initial loading indicator on first status
                                    removeLoadingIndicator();
                                    
                                    // Show step status with animated icon
                                    showStepStatus(data.message, '⏳');
                                    console.log('Status:', data.message);
                                } else if (data.type === 'tool_call') {
                                    // Show tool call step
                                    const toolNames = data.tools.join(', ');
                                    showStepStatus(`正在调用: ${toolNames}`, '🔍');
                                    console.log('Calling tools:', data.tools);
                                } else if (data.type === 'content') {
                                    // Remove all status indicators when content starts
                                    removeLoadingIndicator();
                                    if (currentStepElement) {
                                        currentStepElement.remove();
                                        currentStepElement = null;
                                    }
                                    console.log('All indicators removed, starting content');
                                    
                                    streamingContent += data.chunk;
                                    hasReceivedContent = true;
                                } else if (data.type === 'done') {
                                    console.log('Streaming complete, total length:', streamingContent.length);
                                    // Remove any remaining step indicators
                                    if (currentStepElement) {
                                        currentStepElement.remove();
                                        currentStepElement = null;
                                    }
                                    if (streamingContent) {
                                        displayWithTypewriter(streamingContent);
                                    }
                                } else if (data.type === 'error' || data.error) {
                                    // Remove step indicators on error
                                    if (currentStepElement) {
                                        currentStepElement.remove();
                                        currentStepElement = null;
                                    }
                                    instance.messageAddNew('Error: ' + (data.message || data.error), 'System', 'left');
                                }
                            } catch (e) {
                                console.error('Failed to parse SSE data:', e, 'Line:', line);
                            }
                        }
                    }
                }

                // Fallback: if we received content but no 'done' signal, display it anyway
                if (hasReceivedContent && streamingContent && !contentDisplayed) {
                    console.warn('Stream ended without done signal, displaying partial content');
                    displayWithTypewriter(streamingContent);
                } else if (!streamingContent && !contentDisplayed) {
                    instance.messageAddNew('No response received.', 'System', 'left');
                }

            } catch (err) {
                console.error('Chat error:', err);
                instance.messageAddNew('Network Error: ' + err.message, 'System', 'left');
            }
        }, {
            theme: 'quikchat-theme-dark',
            botName: 'AI Analyst',
            userAvatar: 'https://ui-avatars.com/api/?name=User&background=0D8ABC&color=fff',
            botAvatar: 'https://ui-avatars.com/api/?name=AI&background=ff9900&color=fff',
            placeholder: 'Ask about market data...'
        });

        // Add welcome message
        setTimeout(() => {
            const welcomeMsg = "Welcome to LanFund Pro Terminal. Connected to market data stream.";
            chat.messageAddNew(welcomeMsg, 'System', 'left');
            
            // 🔧 将欢迎消息也添加到历史中（作为 assistant 消息）
            conversationHistory.push({
                role: 'assistant',
                content: welcomeMsg
            });
            console.log('💬 Initialized conversation history with welcome message');
        }, 500);

        // Initialize resize functionality
        const resizeHandle = document.getElementById('resize-handle');
        const chatSidebar = document.getElementById('chat-sidebar');
        let isResizing = false;
        let startX = 0;
        let startWidth = 0;

        resizeHandle.addEventListener('mousedown', function(e) {
            isResizing = true;
            startX = e.clientX;
            startWidth = chatSidebar.offsetWidth;
            resizeHandle.classList.add('resizing');
            document.body.style.cursor = 'ew-resize';
            document.body.style.userSelect = 'none';
            e.preventDefault();
        });

        document.addEventListener('mousemove', function(e) {
            if (!isResizing) return;
            
            const dx = startX - e.clientX; // Reversed because we're dragging from the left
            const newWidth = startWidth + dx;
            
            // Constrain width between min and max
            const minWidth = 300;
            const maxWidth = 800;
            const constrainedWidth = Math.min(Math.max(newWidth, minWidth), maxWidth);
            
            chatSidebar.style.width = constrainedWidth + 'px';
        });

        document.addEventListener('mouseup', function() {
            if (isResizing) {
                isResizing = false;
                resizeHandle.classList.remove('resizing');
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
            }
        });
    });

    // Toggle chat sidebar function
    function toggleChatSidebar() {
        const chatSidebar = document.getElementById('chat-sidebar');
        const toggleIcon = document.getElementById('chat-toggle-icon');

        if (chatSidebar.classList.contains('hidden')) {
            chatSidebar.classList.remove('hidden');
            toggleIcon.textContent = '◀';
        } else {
            chatSidebar.classList.add('hidden');
            toggleIcon.textContent = '▶';
        }
    }
    </script>


    <!-- Standard JS for table coloring -->
    <script>
    document.addEventListener('DOMContentLoaded', function() {
        autoColorize();
    });

    function autoColorize() {
        const cells = document.querySelectorAll('.style-table td');
        cells.forEach(cell => {
            const text = cell.textContent.trim();
            const cleanText = text.replace(/[%,亿万手]/g, '');
            const val = parseFloat(cleanText);

            if (!isNaN(val)) {
                if (text.includes('%') || text.includes('涨跌')) {
                    if (text.includes('-')) {
                        cell.classList.add('negative');
                    } else if (val > 0) {
                        cell.classList.add('positive');
                    }
                } else if (text.startsWith('-')) {
                    cell.classList.add('negative');
                } else if (text.startsWith('+')) {
                    cell.classList.add('positive');
                }
            }
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
        const cleanedVal = val.replace(/%|亿|万|元\/克|手/g, '').replace(/,/g, '');
        const num = parseFloat(cleanedVal);
        return isNaN(num) ? val.toLowerCase() : num;
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

            // 渲染基金列表
            renderFundSelectionList(allFunds);

            // 显示模态框
            document.getElementById('fundSelectionModal').classList.add('active');
        } catch (e) {
            alert('获取基金列表失败: ' + e.message);
        }
    }

    // 渲染基金选择列表
    function renderFundSelectionList(funds) {
        const listContainer = document.getElementById('fundSelectionList');

        // HTML escape function to prevent XSS and syntax errors
        const escapeHtml = (text) => {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        };

        // Escape fund code for use in onclick attribute
        const escapeJs = (text) => {
            if (!text) return '';
            return text.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        };

        listContainer.innerHTML = funds.map(fund => {
            const safeCode = escapeHtml(String(fund.code));
            const safeName = escapeHtml(String(fund.name));
            const safeCodeForJs = escapeJs(String(fund.code));
            const safeSectors = fund.sectors && fund.sectors.length > 0
                ? escapeHtml(fund.sectors.join(', '))
                : '';

            return `
            <div class="sector-item" style="text-align: left; padding: 12px; margin-bottom: 8px; cursor: pointer; display: flex; align-items: center; gap: 10px;"
                 onclick="toggleFundSelection('${safeCodeForJs}', this)">
                <input type="checkbox" class="fund-selection-checkbox" data-code="${safeCode}"
                       style="width: 18px; height: 18px; cursor: pointer;" onclick="event.stopPropagation();">
                <div style="flex: 1;">
                    <div style="font-weight: 600;">${safeCode} - ${safeName}</div>
                    ${fund.is_hold ? '<span style="color: #3b82f6; font-size: 12px;">⭐ 持有</span>' : ''}
                    ${safeSectors ? `<span style="color: #8b949e; font-size: 12px;"> 🏷️ ${safeSectors}</span>` : ''}
                </div>
            </div>
            `;
        }).join('');
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
                closeFundSelectionModal();
                openSectorModal(selectedFundsForOperation);
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
                const filtered = allFunds.filter(fund =>
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

    document.getElementById('confirmBtn').addEventListener('click', function() {
        if (confirmCallback) {
            confirmCallback();
        }
        closeConfirmDialog();
    });

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
        const codes = getSelectedCodes();
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

    // 表格中“标记”列五角星点击：切换持有/取消持有（事件委托，仅绑定一次）
    if (!window._fundHoldStarListenerAdded) {
        window._fundHoldStarListenerAdded = true;
        document.body.addEventListener('click', async function(e) {
            const star = e.target.closest('.fund-hold-star');
            if (!star) return;
            e.preventDefault();
            e.stopPropagation();
            const code = star.dataset.code;
            const currentlyHeld = star.dataset.hold === '1';
            const newHold = !currentlyHeld;
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
                    alert(result.message);
                }
            } catch (err) {
                alert('操作失败: ' + (err.message || err));
            }
        });
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

    // ==================== 新增功能：份额管理和文件操作 ====================

    // 当前正在编辑份额的基金代码
    let currentSharesFundCode = null;

    // 获取基金份额（从内存或DOM）- 必须在 openSharesModal 之前定义
    window.getFundShares = function(fundCode) {
        // 先从全局存储获取
        if (window.fundSharesData && window.fundSharesData[fundCode]) {
            return window.fundSharesData[fundCode];
        }
        return 0;
    };

    // 更新份额按钮状态 - 必须在 openSharesModal 之前定义
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
        header.textContent = sharesValue > 0 ? '修改持仓份额' : '设置持仓份额';

        modal.classList.add('active');
        setTimeout(() => sharesInput.focus(), 100);
    };

    // 关闭份额设置弹窗
    window.closeSharesModal = function() {
        const modal = document.getElementById('sharesModal');
        modal.classList.remove('active');
        currentSharesFundCode = null;
    };

    // 确认份额设置
    window.confirmShares = async function() {
        if (!currentSharesFundCode) {
            alert('基金代码无效');
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
                // 更新全局份额数据
                if (!window.fundSharesData) {
                    window.fundSharesData = {};
                }
                window.fundSharesData[currentSharesFundCode] = shares;

                // 更新按钮文本
                updateSharesButton(currentSharesFundCode, shares);
                // 重新计算持仓统计
                calculatePositionSummary();
                // 关闭弹窗
                closeSharesModal();
            } else {
                alert(result.message);
            }
        } catch (e) {
            alert('更新份额失败: ' + e.message);
        }
    };

    // 下载fund_map.json
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
                // 更新全局份额数据
                if (!window.fundSharesData) {
                    window.fundSharesData = {};
                }
                window.fundSharesData[fundCode] = sharesValue;

                // 更新按钮状态
                updateSharesButton(fundCode, sharesValue);
                // 更新成功后重新计算持仓统计
                calculatePositionSummary();
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
    async function calculatePositionSummary() {
        let totalValue = 0;
        let estimatedGain = 0;
        let actualGain = 0;
        let settledValue = 0;
        const today = new Date().toISOString().split('T')[0];

        // Get fund data map for holdings cards
        let fundDataMap = {};
        try {
            const response = await fetch('/api/fund/data');
            if (response.ok) {
                fundDataMap = await response.json();
            }
        } catch (e) {
            console.warn('Failed to fetch fund data map:', e);
        }

        // Collect held funds data for cards
        const heldFundsData = [];
        // Collect fund details for summary table
        const fundDetailsData = [];

        // 遍历所有基金行
        const fundRows = document.querySelectorAll('.style-table tbody tr');
        fundRows.forEach(row => {
            const cells = row.querySelectorAll('td');
            if (cells.length < 9) return;

            // 获取基金代码
            const codeCell = cells[1]; // 第二列是基金代码（第一列是复选框）
            const fundCode = codeCell.textContent.trim();

            // Check if this fund is held
            const isHeld = fundDataMap[fundCode]?.is_hold || false;

            // 获取份额数据（从全局数据对象）
            const shares = window.fundSharesData && window.fundSharesData[fundCode] ? parseFloat(window.fundSharesData[fundCode]) : 0;
            if (shares <= 0) return;  // 只处理有份额的基金

            try {
                // 解析净值 "1.234(2025-02-02)"
                const netValueText = cells[4].textContent.trim();
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

                // 解析估值增长率
                const estimatedGrowthText = cells[5].textContent.trim();
                const estimatedGrowth = estimatedGrowthText !== 'N/A' ?
                    parseFloat(estimatedGrowthText.replace('%', '')) : 0;

                // 解析日涨幅
                const dayGrowthText = cells[6].textContent.trim();
                const dayGrowth = dayGrowthText !== 'N/A' ?
                    parseFloat(dayGrowthText.replace('%', '')) : 0;

                // 解析连涨/跌
                const consecutiveText = cells[7].textContent.trim();

                // 解析近30天
                const monthlyText = cells[8].textContent.trim();

                // 计算持仓市值
                const positionValue = shares * netValue;

                // If this fund is held, collect its data for cards
                if (isHeld) {
                    heldFundsData.push({
                        code: fundCode,
                        name: fundDataMap[fundCode]?.fund_name || 'Unknown',
                        sectors: fundDataMap[fundCode]?.sectors || [],
                        netValue: netValue,
                        netValueDate: netValueDate,
                        estimatedGrowth: estimatedGrowth,
                        dayGrowth: dayGrowth,
                        consecutive: consecutiveText,
                        monthly: monthlyText,
                        shares: shares,
                        positionValue: positionValue
                    });
                }

                if (shares > 0) {
                    totalValue += positionValue;

                    // 计算预估涨跌
                    const fundEstimatedGain = positionValue * estimatedGrowth / 100;
                    estimatedGain += fundEstimatedGain;

                    // 计算实际涨跌（仅当日结算）
                    let fundActualGain = 0;
                    if (netValueDate === today) {
                        fundActualGain = positionValue * dayGrowth / 100;
                        actualGain += fundActualGain;
                        settledValue += positionValue;
                    }

                    // Collect fund details for summary table
                    const fundName = cells[2].textContent.trim();
                    fundDetailsData.push({
                        code: fundCode,
                        name: fundName,
                        shares: shares,
                        positionValue: positionValue,
                        estimatedGain: fundEstimatedGain,
                        estimatedGainPct: estimatedGrowth,
                        actualGain: fundActualGain,
                        actualGainPct: netValueDate === today ? dayGrowth : 0
                    });
                }
            } catch (e) {
                console.warn('解析基金数据失败:', fundCode, e);
            }
        });

        // Update Asset Hero Section
        const assetHero = document.getElementById('assetHero');
        if (assetHero) {
            if (totalValue > 0) {
                assetHero.style.display = 'block';

            // Update total value
            document.getElementById('heroTotalValue').textContent =
                '¥' + totalValue.toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2});

            // Update estimated gain
            const estGainPct = totalValue > 0 ? (estimatedGain / totalValue * 100) : 0;
            const estSign = estimatedGain >= 0 ? '+' : '';
            const estClass = estimatedGain >= 0 ? 'positive' : 'negative';
            document.getElementById('heroEstimatedGain').textContent =
                estSign + '¥' + Math.abs(estimatedGain).toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
            document.getElementById('heroEstimatedGain').className = 'asset-metric-value ' + estClass;
            document.getElementById('heroEstimatedGainPct').textContent = estSign + estGainPct.toFixed(2) + '%';

            // Update actual gain
            if (settledValue > 0) {
                const actGainPct = (actualGain / settledValue * 100);
                const actSign = actualGain >= 0 ? '+' : '';
                const actClass = actualGain >= 0 ? 'positive' : 'negative';
                document.getElementById('heroActualGain').textContent =
                    actSign + '¥' + Math.abs(actualGain).toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
                document.getElementById('heroActualGain').className = 'asset-metric-value ' + actClass;
                document.getElementById('heroActualGainPct').textContent = actSign + actGainPct.toFixed(2) + '% (Settled)';
            } else {
                document.getElementById('heroActualGain').textContent = '¥0.00';
                document.getElementById('heroActualGain').className = 'asset-metric-value neutral';
                document.getElementById('heroActualGainPct').textContent = '0.00% (Settled)';
            }
            } else {
                assetHero.style.display = 'none';
            }
        }

        // Generate and populate holdings cards
        if (heldFundsData.length > 0) {
            const cardsHTML = heldFundsData.map(fund => {
                const sectorTags = fund.sectors && fund.sectors.length > 0
                    ? `<span style="color: #8b949e; font-size: 12px;"> 🏷️ ${fund.sectors.join(', ')}</span>`
                    : '';
                const estClass = fund.estimatedGrowth >= 0 ? 'up' : 'down';
                const dayClass = fund.dayGrowth >= 0 ? 'up' : 'down';

                return `
                <div class="fund-glass-card" data-code="${fund.code}">
                    <div class="card-header">
                        <div>
                            <div class="card-title">${fund.name}</div>
                            <div class="card-code">${fund.code} ${sectorTags}</div>
                        </div>
                        <div class="card-badge">⭐</div>
                    </div>
                    <div class="card-main-data">
                        <span class="est-pct ${estClass}">${fund.estimatedGrowth >= 0 ? '+' : ''}${fund.estimatedGrowth.toFixed(2)}%</span>
                        <span style="font-size: 12px; color: var(--text-dim)">实时估值</span>
                    </div>
                    <div class="card-details">
                        <div class="detail-item">持仓份额 <b>${fund.shares.toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</b></div>
                        <div class="detail-item">估值盈亏 <b class="${estClass}">${fund.estimatedGrowth >= 0 ? '+' : ''}¥${(fund.positionValue * fund.estimatedGrowth / 100).toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</b></div>
                        <div class="detail-item">当前净值 <b>${fund.netValue.toFixed(4)}</b></div>
                        <div class="detail-item">日涨幅 <b class="${dayClass}">${fund.dayGrowth >= 0 ? '+' : ''}${fund.dayGrowth.toFixed(2)}%</b></div>
                    </div>
                </div>
                `;
            }).join('');

            const holdingsSection = `
            <div style="margin-bottom: 24px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <div style="font-size: 18px; font-weight: 600; color: var(--text-main);">💎 核心持仓</div>
                    <div style="font-size: 14px; color: var(--text-dim); font-family: var(--font-mono);">${heldFundsData.length} 只</div>
                </div>
                <div class="holdings-grid">
                    ${cardsHTML}
                </div>
            </div>
            `;

            document.getElementById('holdingsCardsContainer').innerHTML = holdingsSection;
        } else {
            document.getElementById('holdingsCardsContainer').innerHTML = '';
        }

        // 显示或隐藏持仓统计区域
        const summaryDiv = document.getElementById('positionSummary');
        const fundDetailsDiv = document.getElementById('fundDetailsSummary');
        if (!summaryDiv) {
            // positionSummary element not found (sidebar layout), skip old layout summary
            console.log('positionSummary element not found - using sidebar layout');
        } else if (totalValue > 0) {
            summaryDiv.style.display = 'block';

            // 更新总持仓金额
            const totalValueEl = document.getElementById('totalValue');
            if (totalValueEl) {
                totalValueEl.textContent =
                    '¥' + totalValue.toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
            }

            // 更新预估涨跌
            const estGainPct = totalValue > 0 ? (estimatedGain / totalValue * 100) : 0;
            const estColor = estimatedGain >= 0 ? '#ef4444' : '#10b981';
            const estimatedGainEl = document.getElementById('estimatedGain');
            if (estimatedGainEl) {
                estimatedGainEl.innerHTML =
                    `<span class="sensitive-value ${estimatedGain >= 0 ? 'positive' : 'negative'}" style="color: ${estColor}"><span class="real-value">¥${Math.abs(estimatedGain).toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span><span class="hidden-value">****</span></span><span id="estimatedGainPct" style="color: ${estColor}"> (${estGainPct.toFixed(2)}%)</span>`;
            }

            // 更新实际涨跌
            const actualGainEl = document.getElementById('actualGain');
            if (actualGainEl) {
                if (settledValue > 0) {
                    const actGainPct = (actualGain / settledValue * 100);
                    const actColor = actualGain >= 0 ? '#ef4444' : '#10b981';
                    actualGainEl.innerHTML =
                        `<span class="sensitive-value ${actualGain >= 0 ? 'positive' : 'negative'}" style="color: ${actColor}"><span class="real-value">¥${Math.abs(actualGain).toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span><span class="hidden-value">****</span></span><span id="actualGainPct" style="color: ${actColor}"> (${actGainPct.toFixed(2)}%)</span>`;
                } else {
                    actualGainEl.innerHTML =
                        '<span style="color: var(--text-dim);">净值未更新</span>';
                }
            }

            // 填充分基金明细表格
            if (fundDetailsDiv && fundDetailsData.length > 0) {
                fundDetailsDiv.style.display = 'block';
                const tableBody = document.getElementById('fundDetailsTableBody');
                if (tableBody) {
                    tableBody.innerHTML = fundDetailsData.map(fund => {
                        const estColor = fund.estimatedGain >= 0 ? '#f44336' : '#4caf50';
                        const actColor = fund.actualGain >= 0 ? '#f44336' : '#4caf50';
                        return `
                            <tr style="border-bottom: 1px solid var(--border);">
                                <td style="padding: 10px; text-align: center; white-space: nowrap; vertical-align: middle; color: var(--accent); font-weight: 500;">${fund.code}</td>
                                <td style="padding: 10px; text-align: center; white-space: nowrap; vertical-align: middle; color: var(--text-main); min-width: 120px;">${fund.name}</td>
                                <td style="padding: 10px; text-align: center; white-space: nowrap; vertical-align: middle; font-family: var(--font-mono);">${fund.shares.toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                                <td style="padding: 10px; text-align: center; white-space: nowrap; vertical-align: middle; font-family: var(--font-mono); font-weight: 600;">¥${fund.positionValue.toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                                <td style="padding: 10px; text-align: center; white-space: nowrap; vertical-align: middle; font-family: var(--font-mono); color: ${estColor}; font-weight: 500;">¥${Math.abs(fund.estimatedGain).toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                                <td style="padding: 10px; text-align: center; white-space: nowrap; vertical-align: middle; font-family: var(--font-mono); color: ${estColor}; font-weight: 500;">${fund.estimatedGainPct.toFixed(2)}%</td>
                                <td style="padding: 10px; text-align: center; white-space: nowrap; vertical-align: middle; font-family: var(--font-mono); color: ${actColor}; font-weight: 500;">¥${Math.abs(fund.actualGain).toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                                <td style="padding: 10px; text-align: center; white-space: nowrap; vertical-align: middle; font-family: var(--font-mono); color: ${actColor}; font-weight: 500;">${fund.actualGainPct.toFixed(2)}%</td>
                            </tr>
                        `;
                    }).join('');
                }
            } else if (fundDetailsDiv) {
                fundDetailsDiv.style.display = 'none';
            }
        } else {
            summaryDiv.style.display = 'none';
            if (fundDetailsDiv) {
                fundDetailsDiv.style.display = 'none';
            }
        }
    }

    // 页面加载时加载份额数据并计算持仓统计
    async function loadSharesData() {
        try {
            // 从后端API获取用户的基金数据（包含份额）
            const response = await fetch('/api/fund/data');
            if (response.ok) {
                const fundData = await response.json();

                // 存储份额数据到全局变量
                window.fundSharesData = {};

                // 先存储数据，稍后更新按钮
                for (const [code, data] of Object.entries(fundData)) {
                    const shares = parseFloat(data.shares) || 0;
                    window.fundSharesData[code] = shares;
                }

                // 等待DOM加载完成后更新按钮状态
                updateAllSharesButtons();

                // 计算持仓统计
                calculatePositionSummary();
            }
        } catch (e) {
            console.error('加载份额数据失败:', e);
            // 即使加载失败，也尝试计算持仓统计
            calculatePositionSummary();
        }
    }

    // 更新所有份额按钮状态（在DOM加载后调用）
    function updateAllSharesButtons() {
        if (!window.fundSharesData) return;

        for (const [code, shares] of Object.entries(window.fundSharesData)) {
            updateSharesButton(code, shares);
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

        // 初始化 - 首屏先渲染，再异步加载份额数据与统计，避免 /portfolio 已返回但页面仍长时间无响应
        requestAnimationFrame(function() {
            setTimeout(function() {
                loadSharesData();
            }, 0);
        });

        // 份额弹窗 - 点击外部关闭
        const sharesModal = document.getElementById('sharesModal');
        if (sharesModal) {
            sharesModal.addEventListener('click', function(e) {
                if (e.target === sharesModal) {
                    closeSharesModal();
                }
            });

            // 份额弹窗 - 回车键确认
            const sharesInput = document.getElementById('sharesModalInput');
            if (sharesInput) {
                sharesInput.addEventListener('keypress', function(e) {
                    if (e.key === 'Enter') {
                        confirmShares();
                    }
                });
            }
        }
    });
    </script>
    """


# ==================== 新页面布局函数 ====================

def get_portfolio_page_html(fund_content, fund_map, fund_chart_data=None, fund_chart_info=None, username=None):
    """生成持仓基金页面"""
    css_style = get_css_style()
    import json

    username_display = '<a href="https://github.com/lanZzV/fund" target="_blank" class="nav-star">点个赞</a>'
    username_display += '<a href="https://github.com/lanZzV/fund/issues" target="_blank" class="nav-feedback">反馈</a>'
    if username:
        username_display += '<span class="nav-user">🍎 {username}</span>'.format(username=username)
        username_display += '<a href="/logout" class="nav-logout">退出登录</a>'

    # 准备估值趋势图数据JSON
    fund_chart_data_json = json.dumps(fund_chart_data if fund_chart_data else {'labels': [], 'growth': [], 'net_values': []})
    fund_chart_info_json = json.dumps(fund_chart_info if fund_chart_info else {})

    html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>持仓基金 - LanFund</title>
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
            padding: 30px;
            overflow-y: auto;
        }}

        .portfolio-header {{
            margin-bottom: 20px;
        }}

        .portfolio-header h1 {{
            font-size: 1.5rem;
            font-weight: 600;
            margin: 0;
            color: var(--text-main);
        }}

        .portfolio-header p {{
            color: var(--text-dim);
            margin: 5px 0 0;
            font-size: 0.9rem;
        }}

        .operations-panel {{
            background: rgba(102, 126, 234, 0.05);
            border: 1px solid rgba(102, 126, 234, 0.1);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 30px;
        }}

        .operation-group {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }}

        .fund-content {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
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

            .market-charts-grid {{
                grid-template-columns: 1fr;
                gap: 15px;
            }}

            .chart-card {{
                min-height: auto;
            }}

            .chart-card-content {{
                max-height: 200px;
            }}

            .chart-card h3 {{
                font-size: 0.9rem;
            }}
        }}

        @media (max-width: 1024px) {{
            .market-charts-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}

        /* 基金选择器容器 */
        .fund-selector-wrapper {{
            position: relative;
            display: flex;
            align-items: center;
            flex: 1;
            min-width: 200px;
            max-width: 500px;
        }}

        /* 输入框样式 - 隐藏原生箭头 */
        #fundSelector {{
            flex: 1;
            width: 100%;
            min-width: 150px;
            padding: 6px 32px 6px 12px;
            background: var(--card-bg);
            color: var(--text-main);
            border: 1px solid var(--border);
            border-radius: 6px;
            font-size: 14px;
            line-height: 1.5;
            /* 隐藏原生datalist箭头 */
            appearance: none;
            -webkit-appearance: none;
            -moz-appearance: none;
        }}

        /* 隐藏Webkit浏览器的下拉按钮 */
        #fundSelector::-webkit-calendar-picker-indicator {{
            opacity: 0;
            display: none;
        }}

        /* 输入框焦点样式 */
        #fundSelector:focus {{
            outline: none;
            border-color: #3b82f6;
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
        }}

        /* 清除按钮 */
        .input-clear-btn {{
            position: absolute;
            right: 8px;
            top: 50%;
            transform: translateY(-50%);
            display: flex;
            align-items: center;
            justify-content: center;
            width: 16px;
            height: 16px;
            border-radius: 50%;
            background-color: #9ca3af;
            color: #fff !important;
            font-size: 10px !important;
            font-weight: bold;
            cursor: pointer;
            opacity: 0;
            transition: opacity 0.2s ease, background-color 0.2s ease;
            z-index: 2;
        }}

        /* 有内容且hover时显示清除按钮 */
        .fund-selector-wrapper.has-value:hover .input-clear-btn {{
            opacity: 1;
        }}

        .input-clear-btn:hover {{
            background-color: #6b7280;
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
            <a href="/portfolio" class="sidebar-item active">
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
                    💼 持仓基金
                    <div style="display: flex; align-items: center; gap: 10px; margin-left: 15px; flex-wrap: wrap;">
                        <button id="refreshBtn-portfolio" onclick="refreshCurrentPage()" class="refresh-button">🔄 刷新</button>
                        <span id="lastRefreshTime-portfolio" style="font-size: 0.85rem; color: #666; min-width: 60px;"></span>
                        <span style="font-size: 0.8rem; color: var(--text-dim);">⚠️ 预估数据仅供参考，实际以基金公司结算为准</span>
                    </div>
                </h1>
            </div>

            <!-- Refresh button styling -->
            <style>
                .refresh-button {{
                    margin-left: 15px;
                    padding: 8px 16px;
                    background: var(--accent);
                    color: white;
                    border: none;
                    border-radius: 6px;
                    cursor: pointer;
                    font-size: 0.9rem;
                    font-weight: 500;
                    transition: all 0.2s ease;
                    display: inline-flex;
                    align-items: center;
                    gap: 5px;
                }}
                .refresh-button:hover {{
                    background: #2563eb;
                    transform: translateY(-1px);
                }}
                .refresh-button:disabled {{
                    background: #6b7280;
                    cursor: not-allowed;
                    transform: none;
                }}
                .portfolio-header h1 {{
                    display: flex;
                    align-items: center;
                }}
            </style>

            <!-- 基金内容 -->
            <div class="fund-content">
                {fund_content}
            </div>
        </div>
    </div>

    <!-- Modals (复用现有模态框) -->
    <div class="sector-modal" id="sectorModal">
        <div class="sector-modal-content">
            <div class="sector-modal-header">选择板块</div>
            <input type="text" class="sector-modal-search" id="sectorSearch" placeholder="搜索板块名称...">
            <div id="sectorCategories"></div>
            <div class="sector-modal-footer">
                <button class="btn btn-secondary" onclick="closeSectorModal()">取消</button>
                <button class="btn btn-primary" onclick="confirmSector()">确定</button>
            </div>
        </div>
    </div>

    <div class="sector-modal" id="fundSelectionModal">
        <div class="sector-modal-content">
            <div class="sector-modal-header" id="fundSelectionTitle">选择基金</div>
            <input type="text" class="sector-modal-search" id="fundSelectionSearch" placeholder="搜索基金代码或名称...">
            <div id="fundSelectionList" style="max-height: 400px; overflow-y: auto;"></div>
            <div class="sector-modal-footer">
                <button class="btn btn-secondary" onclick="closeFundSelectionModal()">取消</button>
                <button class="btn btn-primary" id="fundSelectionConfirmBtn" onclick="confirmFundSelection()">确定</button>
            </div>
        </div>
    </div>

    <div class="confirm-dialog" id="confirmDialog">
        <div class="confirm-dialog-content">
            <h3 id="confirmTitle" class="confirm-title"></h3>
            <p id="confirmMessage" class="confirm-message"></p>
            <div class="confirm-actions">
                <button class="btn btn-secondary" onclick="closeConfirmDialog()">取消</button>
                <button class="btn btn-primary" id="confirmBtn">确定</button>
            </div>
        </div>
    </div>

    <!-- 份额设置弹窗 -->
    <div class="sector-modal" id="sharesModal">
        <div class="sector-modal-content" style="max-width: 400px;">
            <div class="sector-modal-header">设置持仓份额</div>
            <div style="padding: 20px;">
                <div style="margin-bottom: 15px;">
                    <label style="display: block; margin-bottom: 8px; color: var(--text-main); font-weight: 500;">基金代码</label>
                    <div id="sharesModalFundCode" style="padding: 10px; background: rgba(59, 130, 246, 0.1); border-radius: 6px; color: #3b82f6; font-weight: 600; font-family: monospace;"></div>
                </div>
                <div style="margin-bottom: 15px;">
                    <label for="sharesModalInput" style="display: block; margin-bottom: 8px; color: var(--text-main); font-weight: 500;">持仓份额</label>
                    <input type="number" id="sharesModalInput" step="0.01" min="0" placeholder="请输入份额"
                           style="width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 6px; font-size: 14px; background: var(--card-bg); color: var(--text-main);">
                </div>
            </div>
            <div class="sector-modal-footer">
                <button class="btn btn-secondary" onclick="closeSharesModal()">取消</button>
                <button class="btn btn-primary" onclick="confirmShares()">确定</button>
            </div>
        </div>
    </div>

    <script src="/static/js/main.js?v=20260323a"></script>
    <script>
        document.addEventListener('DOMContentLoaded', function() {{
            // 自动颜色化
            const cells = document.querySelectorAll('.style-table td');
            const extractSignedNumber = (text) => {{
                // 优先提取百分号前的最后一个数字（适配“3/20 -1.23%”）
                const pctMatches = [...text.matchAll(/([+-]?\\d+(?:\\.\\d+)?)\\s*%/g)];
                if (pctMatches.length > 0) {{
                    return parseFloat(pctMatches[pctMatches.length - 1][1]);
                }}

                // 其次提取文本中最后一个带符号数字
                const signedMatches = text.match(/[+-]?\\d+(?:\\.\\d+)?/g);
                if (signedMatches && signedMatches.length > 0) {{
                    return parseFloat(signedMatches[signedMatches.length - 1]);
                }}

                return NaN;
            }};

            cells.forEach(cell => {{
                cell.classList.remove('positive', 'negative');

                // 跳过基金名称列（如 A100 等名称中的数字不应触发着色）
                if (cell.querySelector('.fund-name-cell')) {{
                    return;
                }}

                const text = cell.textContent.trim();
                if (!text || text === '-' || text === 'N/A' || text === '---') {{
                    return;
                }}

                // 仅对“像涨跌值”的文本进行着色，避免普通名称中的数字被误判
                const hasFinancialHint = text.includes('%') || /^[+-]/.test(text) || /[+-]\\d/.test(text);
                if (!hasFinancialHint) {{
                    return;
                }}

                const val = extractSignedNumber(text);

                if (!isNaN(val)) {{
                    if (val < 0) {{
                        cell.classList.add('negative');
                    }} else if (val > 0) {{
                        cell.classList.add('positive');
                    }}
                }}
            }});

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

            // 初始化基金估值趋势图
            initFundChartSelector();
            initFundChart();
        }});

        // 基金估值趋势数据和选择器
        let fundChartData = {fund_chart_data_json};
        let fundChartInfo = {fund_chart_info_json};

        function initFundChartSelector() {{
            const selector = document.getElementById('fundSelector');
            const datalist = document.getElementById('fundList');

            if (!selector || !datalist || !fundChartInfo || Object.keys(fundChartInfo).length === 0) {{
                // 如果没有基金数据，隐藏图表容器
                const container = document.getElementById('fundChartContainer');
                if (container) {{
                    container.style.display = 'none';
                }}
                return;
            }}

            // 填充datalist选项，value使用"code - name"格式
            Object.entries(fundChartInfo).forEach(([code, info]) => {{
                const option = document.createElement('option');
                option.value = `${{code}} - ${{info.name}}`;
                // 同时保存code作为data属性，方便解析
                option.dataset.code = code;
                datalist.appendChild(option);

                // 设置默认值
                if (info.is_default) {{
                    selector.value = `${{code}} - ${{info.name}}`;
                }}
            }});

            // 从输入值中提取基金代码
            const extractFundCode = (input) => {{
                const trimmed = input.trim();
                // 如果直接是基金代码（6位数字）
                if (/^\\d{{6}}$/.test(trimmed)) {{
                    return trimmed;
                }}
                // 如果是"code - name"格式，提取code部分
                const match = trimmed.match(/^(\\d{{6}})\\s*-\\s*/);
                if (match) {{
                    return match[1];
                }}
                return null;
            }};

            // 监听选择变化（用户从下拉列表选择或输入有效代码后按回车/失焦时触发）
            selector.addEventListener('change', function() {{
                const fundCode = extractFundCode(this.value);
                // 检查输入的是有效的基金代码
                if (fundCode && fundChartInfo[fundCode]) {{
                    // 更新输入框显示为完整格式
                    const info = fundChartInfo[fundCode];
                    this.value = `${{fundCode}} - ${{info.name}}`;
                    loadFundChartData(fundCode);
                }}
            }});

            // 清空按钮功能
            const clearBtn = document.getElementById('fundSelectorClear');
            const wrapper = document.getElementById('fundSelectorWrapper');
            if (clearBtn && wrapper) {{
                // 监听输入，控制清空按钮显示/隐藏
                const updateClearButtonVisibility = () => {{
                    if (selector.value.trim()) {{
                        wrapper.classList.add('has-value');
                    }} else {{
                        wrapper.classList.remove('has-value');
                    }}
                }};

                clearBtn.addEventListener('click', function(e) {{
                    e.preventDefault();
                    e.stopPropagation();
                    selector.value = '';
                    selector.focus();
                    updateClearButtonVisibility();
                    // 触发input事件以便其他监听器知道值已清空
                    selector.dispatchEvent(new Event('input', {{ bubbles: true }}));
                }});

                selector.addEventListener('input', updateClearButtonVisibility);
                selector.addEventListener('change', updateClearButtonVisibility);

                // 初始化时检查
                updateClearButtonVisibility();
            }}

        }}

        function initFundChart() {{
            if (!fundChartData.labels || fundChartData.labels.length === 0) {{
                return;
            }}

            const ctx = document.getElementById('fundChart');
            if (!ctx) return;

            const growthData = fundChartData.growth || [];
            const netValues = fundChartData.net_values || [];
            const lastGrowth = growthData.length > 0 ? growthData[growthData.length - 1] : 0;
            const lastNetValue = netValues.length > 0 ? netValues[netValues.length - 1] : 0;

            // 更新标题
            const titleEl = document.getElementById('fundChartTitle');
            if (titleEl) {{
                const color = lastGrowth > 0 ? '#f44336' : (lastGrowth < 0 ? '#4caf50' : '#9ca3af');
                titleEl.innerHTML = `📈 基金估值`;
            }}

            window.fundChartInstance = new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: fundChartData.labels,
                    datasets: [{{
                        label: '涨幅 (%)',
                        data: growthData,
                        borderColor: function(context) {{
                            const index = context.dataIndex;
                            if (index === undefined || index < 0) return '#9ca3af';
                            const pct = growthData[index];
                            return pct > 0 ? '#f44336' : (pct < 0 ? '#4caf50' : '#9ca3af');
                        }},
                        segment: {{
                            borderColor: function(context) {{
                                const pct = growthData[context.p1DataIndex];
                                return pct > 0 ? '#f44336' : (pct < 0 ? '#4caf50' : '#9ca3af');
                            }}
                        }},
                        backgroundColor: function(context) {{
                            const chart = context.chart;
                            const {{ctx, chartArea}} = chart;
                            if (!chartArea) return null;
                            const lastPct = growthData[growthData.length - 1];
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
                    layout: {{
                        padding: isPerformanceChart ? {{ left: 8, right: 20 }} : {{ left: 0, right: 0 }}
                    }},
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
                                    const lastPct = growthData[growthData.length - 1];
                                    const color = lastPct >= 0 ? '#ff4d4f' : '#52c41a';
                                    return [{{
                                        text: '涨幅: ' + (lastPct >= 0 ? '+' : '') + lastPct.toFixed(2) + '% | 净值: ' + lastNetValue.toFixed(4),
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
                                    const growth = growthData[index];
                                    const netValue = netValues[index];
                                    const color = growth > 0 ? '#f44336' : (growth < 0 ? '#4caf50' : '#9ca3af');
                                    return [
                                        '涨幅: ' + (growth >= 0 ? '+' : '') + growth.toFixed(2) + '%',
                                        '净值: ' + netValue.toFixed(4)
                                    ];
                                }}
                            }}
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
                                text: '涨幅 (%)',
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

        // ==================== 行内基金图：供 main.js 调用 ====================
        const FUND_PERFORMANCE_INTERVAL_OPTIONS = [
            ["ONE_MONTH", "近1月"],
            ["THREE_MONTH", "近3月"],
            ["SIX_MONTH", "近6月"],
            ["ONE_YEAR", "近1年"],
            ["THREE_YEAR", "近3年"]
        ];

        window.currentFundChartState = null;
        window.fundRowChartInstance = null;

        async function loadFundChartDataInline(fundCode, chartType = 'estimate', interval = 'ONE_YEAR') {{
            let url = '/api/fund/chart-data?code=' + encodeURIComponent(fundCode);
            if (chartType === 'performance') {{
                url = '/api/fund/performance-chart-data?code=' + encodeURIComponent(fundCode) + '&interval=' + encodeURIComponent(interval);
            }} else if (chartType === 'profit') {{
                url = '/api/fund/profit-chart-data?code=' + encodeURIComponent(fundCode) + '&interval=' + encodeURIComponent(interval);
            }}

            const response = await fetch(url);
            if (!response.ok) {{
                throw new Error('Failed to fetch chart data');
            }}
            const data = await response.json();
            if (!data || typeof data !== 'object') {{
                return {{ labels: [], growth: [], net_values: [] }};
            }}
            if (!data.chart_data || typeof data.chart_data !== 'object') {{
                return {{ labels: [], growth: [], net_values: [] }};
            }}
            return data.chart_data;
        }}

        function buildFundChartRowContent(chartType, fundCode, interval) {{
            if (chartType === 'estimate') {{
                return `
                    <div class="inline-fund-chart" style="height:260px; padding: 10px 20px;">
                        <canvas></canvas>
                    </div>
                `;
            }}

            if (chartType === 'profit') {{
                const buttonsHtml = FUND_PERFORMANCE_INTERVAL_OPTIONS.map(([value, label]) => `
                    <button
                        type="button"
                        class="fund-performance-range-btn${{value === interval ? ' active' : ''}}"
                        data-code="${{fundCode}}"
                        data-chart-type="profit"
                        data-interval="${{value}}"
                        style="padding:4px 10px;border-radius:999px;border:1px solid ${{value === interval ? 'var(--accent)' : 'var(--border)'}};background:${{value === interval ? 'rgba(59,130,246,0.16)' : 'transparent'}};color:${{value === interval ? 'var(--accent)' : 'var(--text-dim)'}};cursor:pointer;font-size:12px;">
                        ${{label}}
                    </button>
                `).join('');

                return `
                    <div class="inline-fund-chart" style="padding: 10px 20px;">
                        <div style="display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:12px;margin-bottom:10px;">
                            <div></div>
                            <div style="font-size:13px;font-weight:600;color:var(--text-main);text-align:center;">💹 累计收益曲线</div>
                            <div style="display:flex;gap:8px;flex-wrap:wrap;justify-self:end;">${{buttonsHtml}}</div>
                        </div>
                        <div style="height:260px;">
                            <canvas></canvas>
                        </div>
                    </div>
                `;
            }}

            const buttonsHtml = FUND_PERFORMANCE_INTERVAL_OPTIONS.map(([value, label]) => `
                <button
                    type="button"
                    class="fund-performance-range-btn${{value === interval ? ' active' : ''}}"
                    data-code="${{fundCode}}"
                    data-interval="${{value}}"
                    style="padding:4px 10px;border-radius:999px;border:1px solid ${{value === interval ? 'var(--accent)' : 'var(--border)'}};background:${{value === interval ? 'rgba(59,130,246,0.16)' : 'transparent'}};color:${{value === interval ? 'var(--accent)' : 'var(--text-dim)'}};cursor:pointer;font-size:12px;">
                    ${{label}}
                </button>
            `).join('');

            return `
                <div class="inline-fund-chart" style="padding: 10px 20px;">
                    <div style="display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:10px;">
                        <div class="fund-performance-latest-nav" style="font-size:12px;color:var(--text-dim);line-height:1.5;"></div>
                        <div style="font-size:13px;font-weight:600;color:var(--text-main);text-align:center;">📈 基金业绩曲线</div>
                        <div style="display:flex;gap:8px;flex-wrap:wrap;justify-self:end;">${{buttonsHtml}}</div>
                    </div>
                    <div class="fund-performance-legend" style="display:flex;justify-content:center;gap:16px;flex-wrap:wrap;margin-bottom:10px;font-size:12px;"></div>
                    <div style="height:260px;">
                        <canvas></canvas>
                    </div>
                </div>
            `;
        }}

        function renderFundRowChart(canvas, chartData, chartType = 'estimate') {{
            if (!canvas) return;
            if (!chartData || typeof chartData !== 'object') {{
                const wrapper = canvas.closest('.inline-fund-chart');
                if (wrapper) {{
                    wrapper.innerHTML = `<div style="height:100%;display:flex;align-items:center;justify-content:center;color:var(--text-dim);font-size:13px;">图表数据异常，请重试</div>`;
                }}
                return;
            }}
            const growthData = chartData.growth || [];
            const netValues = chartData.net_values || [];
            const isPerformanceChart = chartType === 'performance';
            const isProfitChart = chartType === 'profit';
            const profitValues = chartData.profit_values || [];
            const holdingGainValues = chartData.holding_gain_values || [];
            const cumulativeBuyValues = chartData.cumulative_buy_values || [];
            const cumulativeSellValues = chartData.cumulative_sell_values || [];
            const benchmarkGrowthData = chartData.benchmark_growth || [];
            const holdingReturnPctData = chartData.holding_return_pct || [];
            const benchmarkLabel = chartData.benchmark_label || '沪深300';
            const latestNetValue = chartData.latest_net_value;
            const latestNetValueDate = chartData.latest_net_value_date;
            const tradeMarkers = chartData.trade_markers || [];
            const fundCurveColor = '#3b82f6';
            const benchmarkColor = '#9ca3af';
            const buyMarkerColor = '#2563eb';
            const sellMarkerColor = '#ef4444';
            const clearMarkerColor = '#7f1d1d';

            if (isPerformanceChart) {{
                const wrapper = canvas.closest('.inline-fund-chart');
                const latestNavEl = wrapper ? wrapper.querySelector('.fund-performance-latest-nav') : null;
                const legendEl = wrapper ? wrapper.querySelector('.fund-performance-legend') : null;
                if (latestNavEl) {{
                    if (latestNetValue !== null && latestNetValue !== undefined && latestNetValue !== '') {{
                        const navValue = Number(latestNetValue);
                        const navDate = latestNetValueDate || '--';
                        latestNavEl.innerHTML = `最新净值：<span style="color:var(--text-main);font-weight:600;">${{Number.isFinite(navValue) ? navValue.toFixed(4) : latestNetValue}}</span><br><span style="font-size:11px;">净值日期：${{navDate}}</span>`;
                    }} else {{
                        latestNavEl.innerHTML = `<span style="font-size:11px;">最新净值：--<br>净值日期：--</span>`;
                    }}
                }}
                if (legendEl) {{
                    legendEl.innerHTML = `
                        <span style="display:inline-flex;align-items:center;gap:6px;color:${{fundCurveColor}};">
                            <span style="display:inline-block;width:18px;height:0;border-top:2px solid ${{fundCurveColor}};"></span>基金业绩
                        </span>
                        <span style="display:inline-flex;align-items:center;gap:6px;color:${{benchmarkColor}};">
                            <span style="display:inline-block;width:18px;height:0;border-top:2px solid ${{benchmarkColor}};"></span>${{benchmarkLabel}}
                        </span>
                        <span style="display:inline-flex;align-items:center;gap:6px;color:${{buyMarkerColor}};">
                            <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${{buyMarkerColor}};"></span>买入
                        </span>
                        <span style="display:inline-flex;align-items:center;gap:6px;color:${{sellMarkerColor}};">
                            <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${{sellMarkerColor}};"></span>卖出
                        </span>
                        <span style="display:inline-flex;align-items:center;gap:6px;color:${{clearMarkerColor}};">
                            <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${{clearMarkerColor}};"></span>清仓
                        </span>
                    `;
                }}
            }}

            if (!chartData.labels || chartData.labels.length === 0) {{
                const wrapper = canvas.closest('.inline-fund-chart');
                if (wrapper) {{
                    wrapper.innerHTML = `<div style="height:100%;display:flex;align-items:center;justify-content:center;color:var(--text-dim);font-size:13px;">${{isPerformanceChart ? '暂无可用业绩曲线数据' : (isProfitChart ? '暂无可用累计收益数据' : '暂无可用估值波形数据')}}</div>`;
                }}
                return;
            }}

            if (window.fundRowChartInstance) {{
                window.fundRowChartInstance.destroy();
            }}

            const datasets = [{{
                label: '基金业绩',
                data: growthData,
                order: 20,
                borderColor: fundCurveColor,
                segment: {{
                    borderColor: fundCurveColor
                }},
                backgroundColor: function(context) {{
                    const chart = context.chart;
                    const {{ctx, chartArea}} = chart;
                    if (!chartArea || isPerformanceChart) return null;
                    const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
                    gradient.addColorStop(0, 'rgba(59, 130, 246, 0.20)');
                    gradient.addColorStop(1, 'rgba(59, 130, 246, 0.00)');
                    return gradient;
                }},
                fill: !isPerformanceChart,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 4,
                borderWidth: 2,
                spanGaps: true
            }}];

            if (isProfitChart) {{
                datasets.length = 0;
                datasets.push({{
                    label: '累计收益',
                    data: profitValues,
                    order: 20,
                    borderColor: '#3b82f6',
                    backgroundColor: function(context) {{
                        const chart = context.chart;
                        const {{ctx, chartArea}} = chart;
                        if (!chartArea) return null;
                        const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
                        gradient.addColorStop(0, 'rgba(59, 130, 246, 0.20)');
                        gradient.addColorStop(1, 'rgba(59, 130, 246, 0.00)');
                        return gradient;
                    }},
                    fill: false,
                    tension: 0,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    borderWidth: 2,
                    spanGaps: true
                }});
            }}

            if (isPerformanceChart && benchmarkGrowthData.some(value => value !== null && value !== undefined)) {{
                datasets.push({{
                    label: benchmarkLabel,
                    data: benchmarkGrowthData,
                    order: 21,
                    borderColor: benchmarkColor,
                    backgroundColor: 'transparent',
                    fill: false,
                    tension: 0.25,
                    pointRadius: 0,
                    pointHoverRadius: 3,
                    borderWidth: 2,
                    spanGaps: true
                }});
            }}

            if (isPerformanceChart && tradeMarkers.length > 0) {{
                const buyMarkers = tradeMarkers.filter(item => (item.marker_type || item.type) === 'buy');
                const sellMarkers = tradeMarkers.filter(item => (item.marker_type || item.type) === 'sell');
                const clearMarkers = tradeMarkers.filter(item => (item.marker_type || item.type) === 'clear');

                if (buyMarkers.length > 0) {{
                    datasets.push({{
                        label: '买入',
                        data: buyMarkers,
                        type: 'line',
                        order: 0,
                        showLine: false,
                        pointRadius: 3,
                        pointHoverRadius: 4,
                        pointHitRadius: 10,
                        pointBackgroundColor: buyMarkerColor,
                        pointBorderColor: buyMarkerColor,
                        pointBorderWidth: 0,
                        borderColor: buyMarkerColor,
                        parsing: {{ xAxisKey: 'x', yAxisKey: 'y' }}
                    }});
                }}

                if (sellMarkers.length > 0) {{
                    datasets.push({{
                        label: '卖出',
                        data: sellMarkers,
                        type: 'line',
                        order: 0,
                        showLine: false,
                        pointRadius: 3,
                        pointHoverRadius: 4,
                        pointHitRadius: 10,
                        pointBackgroundColor: sellMarkerColor,
                        pointBorderColor: sellMarkerColor,
                        pointBorderWidth: 0,
                        borderColor: sellMarkerColor,
                        parsing: {{ xAxisKey: 'x', yAxisKey: 'y' }}
                    }});
                }}

                if (clearMarkers.length > 0) {{
                    datasets.push({{
                        label: '清仓',
                        data: clearMarkers,
                        type: 'line',
                        order: 0,
                        showLine: false,
                        pointRadius: 4,
                        pointHoverRadius: 5,
                        pointHitRadius: 10,
                        pointBackgroundColor: clearMarkerColor,
                        pointBorderColor: clearMarkerColor,
                        pointBorderWidth: 0,
                        borderColor: clearMarkerColor,
                        parsing: {{ xAxisKey: 'x', yAxisKey: 'y' }}
                    }});
                }}
            }}

            const clearCycleLabelPlugin = {{
                id: 'clearCycleLabelPlugin',
                afterDatasetsDraw(chart) {{
                    if (!isPerformanceChart || !tradeMarkers.length) return;
                    const clearDatasetIndex = chart.data.datasets.findIndex(ds => ds.label === '清仓');
                    if (clearDatasetIndex < 0) return;
                    const meta = chart.getDatasetMeta(clearDatasetIndex);
                    if (!meta || !meta.data || !meta.data.length) return;
                    const ctx = chart.ctx;
                    ctx.save();
                    ctx.font = '11px system-ui, -apple-system, Segoe UI, Roboto, sans-serif';
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'bottom';
                    ctx.fillStyle = clearMarkerColor;

                    const formatMoney = (value) => {{
                        const num = Number(value || 0);
                        return '¥' + num.toFixed(2);
                    }};
                    const formatPct = (value) => {{
                        if (value === null || value === undefined || Number.isNaN(Number(value))) return '--';
                        const num = Number(value);
                        return (num >= 0 ? '+' : '') + num.toFixed(2) + '%';
                    }};

                    meta.data.forEach((pointElement, index) => {{
                        const raw = chart.data.datasets[clearDatasetIndex].data[index] || {{}};
                        if (!raw.period_start || !raw.period_end) return;
                        const y = pointElement.y;
                        const x = pointElement.x;
                        const lines = [
                            `${{raw.period_start}} ~ ${{raw.period_end}}`,
                            `收益 ${{formatMoney(raw.cycle_profit)}}`,
                            `收益率 ${{formatPct(raw.cycle_return_pct)}}`,
                            `年化 ${{formatPct(raw.annual_return_pct)}}`
                        ];
                        const lineHeight = 13;
                        let textY = y - 10 - (lines.length - 1) * lineHeight;
                        const minTop = chart.chartArea.top + 4;
                        if (textY < minTop) textY = minTop;
                        lines.forEach((line, lineIndex) => {{
                            ctx.fillText(line, x, textY + lineIndex * lineHeight);
                        }});
                    }});
                    ctx.restore();
                }}
            }};

            const chartConfig = {{
                type: 'line',
                plugins: [clearCycleLabelPlugin],
                data: {{
                    labels: chartData.labels || [],
                    datasets: datasets
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {{
                        mode: isPerformanceChart ? 'nearest' : 'index',
                        intersect: isPerformanceChart,
                    }},
                    plugins: {{
                        legend: {{ display: false }},
                        tooltip: {{
                            callbacks: {{
                                title: function(context) {{
                                    return (isPerformanceChart ? '日期: ' : '时间: ') + context[0].label;
                                }},
                                label: function(context) {{
                                    const index = context.dataIndex;
                                    const datasetLabel = context.dataset.label || '涨幅';
                                    const dataValue = context.parsed.y;
                                    const raw = context.raw || {{}};
                                    if (isPerformanceChart) {{
                                        if ((datasetLabel === '买入' || datasetLabel === '卖出' || datasetLabel === '清仓') && raw.tx_time) {{
                                            const txDate = raw.x || String(raw.tx_time).split(' ')[0] || context.label;
                                            const dateIndex = (chartData.labels || []).indexOf(txDate);
                                            const fundPerf = dateIndex >= 0 ? Number(growthData[dateIndex]) : Number(dataValue);
                                            const benchmarkPerf = dateIndex >= 0 ? Number(benchmarkGrowthData[dateIndex]) : null;
                                            const holdingReturnPct = dateIndex >= 0 ? Number(holdingReturnPctData[dateIndex]) : null;
                                            const formatPct = function(value) {{
                                                if (value === null || value === undefined || !Number.isFinite(value)) return '--';
                                                return (value >= 0 ? '+' : '') + value.toFixed(2) + '%';
                                            }};
                                            const baseLines = [
                                                datasetLabel + '：' + raw.tx_time,
                                                '金额：¥' + Number(raw.amount || 0).toFixed(2),
                                                '份额：' + Number(raw.shares || 0).toFixed(2),
                                                '净值：' + Number(raw.net_value || 0).toFixed(4),
                                                '基金业绩：' + formatPct(fundPerf),
                                                benchmarkLabel + '：' + formatPct(benchmarkPerf),
                                                '持有收益率：' + formatPct(holdingReturnPct)
                                            ];
                                            if (datasetLabel === '清仓') {{
                                                baseLines.push('周期：' + (raw.period_start || '--') + ' ~ ' + (raw.period_end || '--'));
                                                baseLines.push('周期收益：¥' + Number(raw.cycle_profit || 0).toFixed(2));
                                                baseLines.push('周期收益率：' + ((raw.cycle_return_pct === null || raw.cycle_return_pct === undefined) ? '--' : ((Number(raw.cycle_return_pct) >= 0 ? '+' : '') + Number(raw.cycle_return_pct).toFixed(2) + '%')));
                                                baseLines.push('年化收益率：' + ((raw.annual_return_pct === null || raw.annual_return_pct === undefined) ? '--' : ((Number(raw.annual_return_pct) >= 0 ? '+' : '') + Number(raw.annual_return_pct).toFixed(2) + '%')));
                                            }}
                                            return baseLines;
                                        }}
                                        if (dataValue === null || dataValue === undefined) {{
                                            return datasetLabel + ': --';
                                        }}
                                        return datasetLabel + ': ' + (dataValue >= 0 ? '+' : '') + dataValue.toFixed(2) + '%';
                                    }}
                                    if (isProfitChart) {{
                                        const pointProfit = Number(profitValues[index] || 0);
                                        const pointHolding = Number(holdingGainValues[index] || 0);
                                        const pointBuy = Number(cumulativeBuyValues[index] || 0);
                                        const pointSell = Number(cumulativeSellValues[index] || 0);
                                        return [
                                            '累计收益：¥' + pointProfit.toFixed(2),
                                            '持有收益：¥' + pointHolding.toFixed(2),
                                            '累计买入：¥' + pointBuy.toFixed(2),
                                            '累计卖出：¥' + pointSell.toFixed(2)
                                        ];
                                    }}
                                    const growth = growthData[index];
                                    const netValue = netValues[index];
                                    return [
                                        '涨幅: ' + (growth >= 0 ? '+' : '') + growth.toFixed(2) + '%',
                                        '净值: ' + netValue.toFixed(4)
                                    ];
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{
                            offset: isPerformanceChart,
                            ticks: {{
                                color: '#9ca3af',
                                font: {{ size: 10 }},
                                align: isPerformanceChart ? 'inner' : 'center',
                                autoSkip: !isPerformanceChart,
                                maxTicksLimit: isPerformanceChart ? 8 : 6,
                                maxRotation: 0,
                                minRotation: 0,
                                callback: function(value, index, ticks) {{
                                    if (!isPerformanceChart) {{
                                        return this.getLabelForValue(value);
                                    }}
                                    const label = this.getLabelForValue(value);
                                    if (index === 0 || index === ticks.length - 1) {{
                                        return label;
                                    }}
                                    const targetCount = 8;
                                    const step = Math.max(1, Math.ceil((ticks.length - 1) / (targetCount - 1)));
                                    return index % step === 0 ? label : '';
                                }}
                            }},
                            grid: {{
                                color: 'rgba(148, 163, 184, 0.2)'
                            }}
                        }},
                        y: {{
                            border: {{
                                display: !isPerformanceChart
                            }},
                            title: {{
                                display: true,
                                text: isPerformanceChart ? '业绩涨幅 (%)' : (isProfitChart ? '累计收益 (元)' : '涨幅 (%)'),
                                color: '#9ca3af',
                                font: {{ size: 11 }}
                            }},
                            ticks: {{
                                color: '#9ca3af',
                                callback: function(value) {{
                                    if (isProfitChart) {{
                                        return '¥' + Number(value).toFixed(0);
                                    }}
                                    return (value >= 0 ? '+' : '') + value.toFixed(2) + '%';
                                }}
                            }},
                            grid: {{
                                color: 'rgba(148, 163, 184, 0.2)'
                            }}
                        }}
                    }}
                }}
            }};

            try {{
                window.fundRowChartInstance = new Chart(canvas.getContext('2d'), chartConfig);
            }} catch (chartErr) {{
                console.warn('fund row chart init failed, retrying without custom plugin', chartErr);
                chartConfig.plugins = [];
                window.fundRowChartInstance = new Chart(canvas.getContext('2d'), chartConfig);
            }}
        }}

        function bindChartRangeButtons(chartRow, fundCode) {{
            chartRow.querySelectorAll('.fund-performance-range-btn').forEach(button => {{
                button.addEventListener('click', function(e) {{
                    e.preventDefault();
                    e.stopPropagation();
                    const nextInterval = button.dataset.interval || 'ONE_YEAR';
                    const nextType = button.dataset.chartType || 'performance';
                    if (window.currentFundChartState &&
                        window.currentFundChartState.code === fundCode &&
                        window.currentFundChartState.type === nextType &&
                        window.currentFundChartState.interval === nextInterval) {{
                        return;
                    }}
                    window.toggleFundRowChart(fundCode, nextType, nextInterval, {{ forceOpen: true }});
                }});
            }});
        }}

        window.toggleFundRowChart = async function(fundCode, chartType = 'estimate', interval = 'ONE_YEAR', options = {{}}) {{
            try {{
                const tableBody = document.querySelector('.style-table tbody');
                if (!tableBody) return;

                const normalizedType = chartType === 'performance' ? 'performance' : (chartType === 'profit' ? 'profit' : 'estimate');
                const defaultInterval = normalizedType === 'profit' ? 'THREE_MONTH' : 'ONE_YEAR';
                const normalizedInterval = (normalizedType === 'performance' || normalizedType === 'profit') ? (interval || defaultInterval) : null;
                const currentState = window.currentFundChartState;

                // 如果当前已展开的是同一只基金、同一类型、同一区间，则收起
                if (!options.forceOpen &&
                    currentState &&
                    currentState.code === fundCode &&
                    currentState.type === normalizedType &&
                    currentState.interval === normalizedInterval) {{
                    const existingRow = tableBody.querySelector('tr.fund-chart-row');
                    if (existingRow) existingRow.remove();
                    window.currentFundChartState = null;
                    if (window.fundRowChartInstance) {{
                        window.fundRowChartInstance.destroy();
                        window.fundRowChartInstance = null;
                    }}
                    return;
                }}

                // 收起之前的行
                const oldRow = tableBody.querySelector('tr.fund-chart-row');
                if (oldRow) oldRow.remove();

                const codeCell = tableBody.querySelector(`.fund-code-cell[data-code="${{fundCode}}"]`);
                const nameCell = tableBody.querySelector(`.fund-name-cell[data-code="${{fundCode}}"]`);
                const estimateCell = tableBody.querySelector(`.fund-estimate-cell[data-code="${{fundCode}}"]`);
                const gainCell = tableBody.querySelector(`.fund-position-gain-cell[data-code="${{fundCode}}"]`);
                const targetAnchor = normalizedType === 'performance' ? (nameCell || codeCell) : (normalizedType === 'profit' ? gainCell : (estimateCell || nameCell || codeCell));
                const targetRow = targetAnchor ? targetAnchor.closest('tr') : null;
                if (!targetRow) return;

                const colCount = targetRow.cells.length;
                const chartRow = document.createElement('tr');
                chartRow.className = 'fund-chart-row';
                const chartCell = document.createElement('td');
                chartCell.colSpan = colCount;
                chartCell.innerHTML = buildFundChartRowContent(normalizedType, fundCode, normalizedInterval);
                chartRow.appendChild(chartCell);
                targetRow.parentNode.insertBefore(chartRow, targetRow.nextSibling);

                if (normalizedType === 'performance' || normalizedType === 'profit') {{
                    bindChartRangeButtons(chartRow, fundCode);
                }}

                const canvas = chartCell.querySelector('canvas');
                const chartData = await loadFundChartDataInline(fundCode, normalizedType, normalizedInterval || (normalizedType === 'profit' ? 'THREE_MONTH' : 'ONE_YEAR'));
                window.currentFundChartState = {{
                    code: fundCode,
                    type: normalizedType,
                    interval: normalizedInterval
                }};

                try {{
                    renderFundRowChart(canvas, chartData, normalizedType);
                }} catch (renderErr) {{
                    console.error('renderFundRowChart error:', renderErr);
                    if (chartCell) {{
                        chartCell.innerHTML = `<div style="padding:18px;color:var(--down-color);font-size:12px;">图表渲染失败，请稍后重试</div>`;
                    }}
                }}
            }} catch (e) {{
                console.error('toggleFundRowChart error:', e);
            }}
        }};
    </script>
</body>
</html>'''.format(css_style=css_style, username_display=username_display, fund_content=fund_content, fund_chart_data_json=fund_chart_data_json, fund_chart_info_json=fund_chart_info_json)
    return html


def get_market_icon(key):
    """获取市场数据的图标"""
    icons = {
        'kx': '📰',
        'marker': '🌍',
        'real_time_gold': '🥇',
        'gold': '📈',
        'seven_A': '📊',
        'A': '📉',
        'bk': '🏢',
        'select_fund': '🔍'
    }
    return icons.get(key, '📊')


def get_sectors_page_html(sectors_content, select_fund_content, fund_map, username=None):
    """生成行业板块基金查询页面"""
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
    <title>行业板块 - LanFund</title>
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
            margin-bottom: 30px;
        }}

        .page-header h1 {{
            font-size: 2rem;
            font-weight: 700;
            margin: 0;
            color: var(--text-main);
            border: none;
            text-decoration: none;
        }}

        .page-header p {{
            color: var(--text-dim);
            margin-top: 10px;
            border: none;
            text-decoration: none;
        }}

        /* Tab 内容 */
        .tab-content {{
            display: none;
        }}

        .tab-content.active {{
            display: block;
        }}

        .content-card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
        }}

        /* Tab 切换按钮 */
        .tab-button {{
            padding: 10px 20px;
            background: none;
            border: none;
            color: var(--text-dim);
            cursor: pointer;
            font-size: 1rem;
            font-weight: 500;
            transition: all 0.2s ease;
        }}

        .tab-button:hover {{
            color: var(--text-main);
        }}

        .tab-button.active {{
            color: var(--accent);
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
            <a href="/portfolio" class="sidebar-item">
                <span class="sidebar-icon">💼</span>
                <span>持仓基金</span>
            </a>
            <a href="/sectors" class="sidebar-item active">
                <span class="sidebar-icon">🏢</span>
                <span>行业板块</span>
            </a>
        </div>

        <!-- 内容区域 -->
        <div class="content-area">
            <!-- Tab 切换按钮 -->
            <div class="tab-buttons" style="display: flex; gap: 10px; margin-bottom: 20px;">
                <button class="tab-button active" onclick="switchTab('sectors')" id="tab-btn-sectors">
                    🏢 行业板块
                </button>
                <button class="tab-button" onclick="switchTab('query')" id="tab-btn-query">
                    🔍 板块基金查询
                </button>
            </div>

            <!-- 行业板块 Tab -->
            <div id="tab-sectors" class="tab-content active">
                <div class="page-header">
                    <h1 style="display: flex; align-items: center;">
                        🏢 行业板块
                        <div style="margin-left: 15px; display: flex; align-items: center; gap: 10px;">
                            <button id="refreshBtn-sectors" onclick="refreshCurrentPage()" class="refresh-button" style="padding: 8px 16px; background: var(--accent); color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem; font-weight: 500; transition: all 0.2s ease; display: inline-flex; align-items: center; gap: 5px;">🔄 刷新</button>
                            <span id="lastRefreshTime-sectors" style="font-size: 0.85rem; color: #666; min-width: 60px;"></span>
                        </div>
                    </h1>
                    <p>查看各行业板块的市场表现</p>
                </div>
                <div class="content-card">
                    {sectors_content}
                </div>
            </div>

            <!-- 板块基金查询 Tab -->
            <div id="tab-query" class="tab-content">
                <div class="page-header">
                    <h1 style="display: flex; align-items: center;">
                        🔍 板块基金查询
                        <div style="margin-left: 15px; display: flex; align-items: center; gap: 10px;">
                            <button id="refreshBtn-sectors-query" onclick="refreshCurrentPage()" class="refresh-button" style="padding: 8px 16px; background: var(--accent); color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem; font-weight: 500; transition: all 0.2s ease; display: inline-flex; align-items: center; gap: 5px;">🔄 刷新</button>
                            <span id="lastRefreshTime-sectors" style="font-size: 0.85rem; color: #666; min-width: 60px;"></span>
                        </div>
                    </h1>
                    <p>查询特定板块的基金产品</p>
                </div>
                <div class="content-card">
                    {select_fund_content}
                </div>
            </div>
        </div>
    </div>

    <script src="/static/js/main.js?v=20260323a"></script>
    <script src="/static/js/sidebar-nav.js"></script>
    <script>
        function switchTab(tabName) {{
            // 隐藏所有 tab 内容
            document.querySelectorAll('.tab-content').forEach(tab => {{
                tab.classList.remove('active');
            }});

            // 移除所有 tab 按钮的 active 状态
            document.querySelectorAll('.tab-button').forEach(btn => {{
                btn.classList.remove('active');
            }});

            // 显示选中的 tab
            document.getElementById('tab-' + tabName).classList.add('active');

            // 设置对应 tab 按钮为 active
            document.getElementById('tab-btn-' + tabName).classList.add('active');
        }}

        // 自动颜色化函数
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

        // 默认激活第一个 tab
        document.addEventListener('DOMContentLoaded', function() {{
            const firstTabBtn = document.querySelector('.tab-button');
            if (firstTabBtn) {{
                firstTabBtn.classList.add('active');
            }}

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

            // 自动颜色化延后到首帧之后，减少首屏阻塞
            requestAnimationFrame(function() {
                setTimeout(function() {
                    autoColorize();
                }, 0);
            });
        }});
    </script>
</body>
</html>'''.format(
        css_style=css_style,
        username_display=username_display,
        sectors_content=sectors_content,
        select_fund_content=select_fund_content
    )
    return html

