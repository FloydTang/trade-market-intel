# Trade Market Intel · 市场背调 Skill

**半斤九两科技 · EVENBETTER TECH 出品** · 维护：汤九两 / [FloydTang](https://github.com/FloydTang)

[![Offline checks](https://github.com/FloydTang/trade-market-intel/actions/workflows/check.yml/badge.svg)](https://github.com/FloydTang/trade-market-intel/actions/workflows/check.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/FloydTang/trade-market-intel)](https://github.com/FloydTang/trade-market-intel/releases/latest)

[公司官网](https://tang92.com) · [AI 外贸通](https://news.tang92.com) · [外贸 Skill 合集](https://github.com/FloydTang/trade-skills-collection)

在搜客户之前，先判断产品应该进入哪些市场、面向什么买方，以及是否适合我方角色。跨行业、证据驱动的开源 Codex Skill，也可由其他代理宿主按同一契约执行。

**链路：市场背调 → 客户搜索 → 线索整理 → 客户背调 → 开发信草稿。**

当前版本：**v0.1.0**（2026-11-04）。通用 Skill、离线计算和文件交接已可使用；AI 外贸通线上自动执行仍按下文接入状态理解。

## 能力与边界

- 产品/HS版本、原料与成品、代理篮子及统计边界。
- 全球进口与中国出口目的地分表；规模前10/20、正绝对增量、带基数门槛的正增速。
- 来源、单位、缺报、修订、转口、低基数与异常检查。
- OEM / ODM / 纯贸易 / 品牌商适配，A/B/hold/watch分级与证据。
- JSON、Markdown、CSV与draft客户发现brief；不自动搜客、联系客户或生成获批销售角度。

它不是全球实时数据API。代理负责取得公开或用户授权数据并做业务解释，Python脚本只标准化和复算。没有资料就标缺失，不给伪精确排名或利润分数。仅列头部的来源输出“子集内排名”，不包装成全球全集。

## 安装与运行

```bash
git clone https://github.com/FloydTang/trade-market-intel.git
# Codex: 将此目录放入自己的skills目录，或显式提供SKILL.md路径。
cd trade-market-intel
python3 scripts/build_market_report.py --input-json examples/synthetic-input.json --output-dir /tmp/market-demo
python3 scripts/run_regression_checks.py
```

Python 3.10+，标准库即可。示例全部合成，不能作为实际市场结论。真实运行参考 [SKILL.md](SKILL.md)、[输入契约](references/input-contract.md)及[JSON Schema](schemas/market-input.schema.json)。统计和交接脚本不联网、不读取凭证；可选资讯适配脚本只读取AI外贸通公开GET接口。生成目录可含企业私有上下文，请存放仓库外。

## 输出

`rankings.json`保留口径、覆盖、来源与分级；`records.csv`保留原单位和值及归一化USD；`report.md`是计算底稿；`input-snapshot.json`和`manifest.json`供复算；`discovery-bridge.json`对接客户搜索。分析员需按[报告模板](references/report-template.md)补齐策略、准入、竞争和未知项。

绝对增量不等于增速；缺基数不补零；基期零的增速为null；不足10/20不凑榜。集团不与成员国混排，产品篮子不自动叠加。不同年份、币种、HS版本、流向或不齐时期不直接合并。行业同比反推基数只可另列估算，不冒充直接观测。

## 与既有Skill的关系

沿用 [trade-lead-discovery](https://github.com/FloydTang/trade-lead-discovery) 的seller_context / target_market / customer_type等输入方式；公司级判断交给 [trade-customer-intel](https://github.com/FloydTang/trade-customer-intel)。本仓库是独立首版开发源，尚未接入集合仓库发行同步；未修改其他仓库。不宣称完整自动流水线或已有OpenClaw专用适配器。

## 公开范围与许可证

MIT，与现有对外Skill惯例一致。只发布通用方法、自有脚本、合成例和公共来源链接；不包含客户身份、联系人、内部资料、真实客户报告、第三方原始数据库导出或凭证。MIT仅覆盖本仓库自有内容，不改变外部来源许可。企业原表头优先，容器中立，无需购买特定服务。

## 真丝工厂示例与AI外贸通

[真丝合成案例](examples/silk-walkthrough.md)区分面料/成品、两个贸易流向和四种卖方角色；[完整合成输出](examples/silk-output/report.md)与[搜索交接示例](examples/silk-handoff/lead-discovery-input.json)可直接查看。

```bash
python3 scripts/build_market_report.py --input-json examples/silk-synthetic-input.json --output-dir /tmp/silk-market
python3 scripts/collect_news_context.py --query silk --output /tmp/silk-market/market-news.json
python3 scripts/export_handoff.py --input-json examples/silk-synthetic-input.json --series-id fabric-import --market 'Market Alpha' --selected-by 'demo operator' --news-context /tmp/silk-market/market-news.json --output-dir /tmp/silk-handoff
```

在Codex中可直接说：`使用 $trade-market-intel，先界定我的产品与HS统计口径，再比较全球进口、中国出口及增长，按我的OEM能力选择2–3个市场并生成客户搜索输入。缺失资料请标明。` 首次请提供产品规格、卖方角色与可授权使用的能力资料；未确认的HS不直接报总市场。

2026-11-04已检查AI外贸通部署工程：现有资讯API/MCP可供只读采集；助手chat和顾问留资不是Skill执行/市场报告导入接口。本次实现资讯读取适配和客户搜索文件交接，未更改线上工程、数据库或现有Skill，未部署线上自动开发流程。市场上下文由宿主保存给后续背调、开发信和跟进；详情见[接入契约及待办](references/integration.md)。

## 验证

```bash
python3 scripts/run_regression_checks.py
# 可选：有真实客户搜索仓库时，离线核验字段及整理桥接；不会调用搜索引擎
python3 scripts/check_discovery_compatibility.py --discovery-root /path/to/trade-lead-discovery
```

11组回归覆盖：单位换算、集团排除、缺报/零基数/下降、无效及重复输入、证据门槛、异常拦截、可复算清单、完整候选集的Top10/20、四角色与双流向、人工选定交接、资讯空结果/失败/返回契约。CI在Python3.10和3.14执行离线测试。来源真实性、企业能力和实时准入需逐次核查，单元测试不替代市场调研。

真实新闻原文及企业研究不纳入公开示例。贡献及敏感问题处理见[CONTRIBUTING.md](CONTRIBUTING.md)、[SECURITY.md](SECURITY.md)。

## 关于半斤九两与增强权益

本项目是半斤九两科技的外贸 Skill 系列之一，服务主动开发中“先判断市场，再搜索客户”的业务节点。与客户搜索、线索整理、客户背调和开发信 Skill 配合使用，各节点保持明确输入、来源和审核边界。

通用方法、计算脚本和合成示例按MIT开放。如需数据留存、统一编排、多代理协作或飞书落地，沿用现有外贸 Skill 的[增强权益说明入口](https://evenbetter.feishu.cn/wiki/W6GnwTZGFiUdJ0kXZv6cV4PSnpf)。具体服务范围以该入口及双方确认内容为准，不把开源仓库描述成已上线的完整自动化服务。

品牌及业务信息：[tang92.com](https://tang92.com)。Copyright © 2026 半斤九两科技。
