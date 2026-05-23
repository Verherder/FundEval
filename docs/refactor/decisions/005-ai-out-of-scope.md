# ADR-005：AI 分析不在本次重构范围

## 状态

已接受（2026-05-22）

## 背景

`src/ai_analyzer.py`（约 1510 行）通过 `fund.py` 的 `LanFund.run(with_ai=True)` / `ai_analysis()` 调用。

审计结论：

- **Web 主流程**（`fund_server.py` 52 个路由）**无任何** `AIAnalyzer` 引用
- 仅 CLI：`python src/fund.py` 且显式传入 `--with-ai` 时执行

## 决策

1. **不** 新增 `ai_service` 或迁移 `ai_analyzer` 逻辑
2. **不** 修改 `ai_analyzer.py` 与 `fund.ai_analysis()` 行为（除非修复无关 bug）
3. 重构 checklist **不包含** AI 分析路径

## 后果

- 重构工期与风险降低
- 未来若 Web 需要 AI，可单独立项，再引入 `ai_service` + API 路由
