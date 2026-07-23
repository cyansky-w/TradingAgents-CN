# 加密永续三模式下单输入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 USDT 本位永续开仓提供按数量、按订单金额、按初始保证金三种互相换算的下单输入方式，并让后端以订单名义金额计入持仓成本。

**Architecture:** 前端维护一个主输入模式并实时用 Decimal.js 计算三个值；提交时发送最终 `quantity`、`price`、`order_notional`、`initial_margin` 和 `leverage`。后端在 Pydantic 模型中重新计算并校验这些字段，账本保留显式订单名义金额，PositionCalculator 对旧记录回退到 `price × quantity`，对新记录使用 `order_notional`。

**Tech Stack:** Python/Pydantic/FastAPI、Vue 3、TypeScript、Decimal/decimal.js、Vitest、Docker Compose。

---

## Task 1: 后端模型与账本字段

**Files:** `app/models/real_trades.py`, `app/services/portfolio/ledger_service.py`, `tests/unit/portfolio/test_models.py`

- [ ] 添加 `order_notional: Optional[Decimal] = Field(default=None, ge=0)`，仅永续开仓需要；模型校验三种模式的输入完整性和 `order_notional = quantity × price`、`initial_margin = order_notional ÷ leverage` 的一致性。
- [ ] 对旧记录保留兼容：缺失 `order_notional` 时不报错；由持仓计算回退到 `price × quantity`。
- [ ] 先写并运行失败测试，覆盖三种输入结果、零/负杠杆、金额不一致、非永续记录不受影响。
- [ ] 实现模型字段和校验，运行 `python -m pytest tests/unit/portfolio/test_models.py -q`。

## Task 2: 持仓成本使用订单名义金额

**Files:** `app/services/portfolio/position_calculator.py`, `tests/unit/portfolio/test_position_calculator.py`

- [ ] 先写失败测试：永续多头和空头开仓含 `order_notional` 时，`cost_value` 使用该值；无该字段的旧记录仍使用 `price × quantity`；平仓按平均成本释放并计算盈亏。
- [ ] 增加集中读取逻辑：`notional = item.get("order_notional")`，为空时回退 `price × quantity`；多头加仓、空头开仓分别纳入现有手续费规则。
- [ ] 运行持仓计算相关测试，确认 A 股、港股、美股和现货行为不变。

## Task 3: 前端三种输入模式

**Files:** `frontend/src/api/realTrades.ts`, `frontend/src/views/RealTrading/components/TradeRecordForm.vue`, `frontend/src/views/RealTrading/__tests__/TradeRecordForm.test.ts`

- [ ] 先写失败测试：加密永续开仓显示“按数量/按订单金额/按初始保证金”三选一；价格 100000、杠杆 10、数量 0.01 时得到订单金额 1000 和保证金 100；另外两种模式反算数量；切换到平仓隐藏计算模式；全仓/逐仓控件不再显示。
- [ ] 在 `CreateLedgerRecordPayload` 添加 `order_notional?: DecimalString`，增加表单字段和 `calculation_mode` 本地状态。
- [ ] 使用 Decimal.js 计算并格式化数量、订单金额、保证金；主输入可编辑，派生字段只读；提交前发送最终四个字段。
- [ ] 运行目标 Vitest 和 `npm run type-check`。

## Task 4: API 与联调验收

**Files:** `tests/unit/portfolio/test_portfolio_service.py`（如需）、Docker 配置不变

- [ ] 运行前端全量目标测试、后端模型/持仓测试和生产构建。
- [ ] `docker compose -p tradingagents-cn up -d --build backend frontend`。
- [ ] 浏览器录入 BTC/USDT:USDT 开仓，分别验证三种模式最终数量、订单金额、初始保证金一致；验证做多/做空绝对值一致。
- [ ] 检查 API 保存记录返回字段，刷新后持仓平均成本和数量不变。
- [ ] 运行 `git diff --check` 与 `npx gitnexus detect-changes --scope staged --repo "TradingAgents-CN"`，提交前报告风险。
