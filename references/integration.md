# AI外贸通与主动开发交接契约

核验日期：2026-11-04。本仓库实现的是文件交接与资讯只读适配，不是线上全自动客户开发服务。

## 已核实的系统边界

已只读检查 AI外贸通实际部署工程的 `apps/api/src/routes/v1.ts`、`routes/mcp.ts`、`routes/jiuliang.ts`、`packages/backend/src/jiuliang/service.ts` 及 `database/migrations/0039_jiuliang.sql`。

- 公开资讯：`GET https://news.tang92.com/api/v1/items`，参数 `q`（2–200字）、`window=24h|7d`、`mode=selected|all`、`limit=1..100`。返回 `schemaVersion`、`query`、`items`、`page`；每项有title、summary、source、publishedAt/discoveredAt和links.aihot/original。分页不等于全球数据覆盖。
- MCP：`/api/mcp`，匿名只读，提供资讯、搜索、热点、事件、日报；没有执行市场Skill、导入客户或触达工具。
- 助手：`/api/site/jiuliang/chat` 需要站点Origin及签名会话；message最多2000字，context只接受item/report标识。它不是文件上传或Skill执行接口。
- `jiuliang_leads` 是访客同意后的顾问留资，不是搜客清单或研究档案表。不能将市场报告塞进留资字段。
- 本次检查未发现市场研究导入契约、客户开发工作流执行器或可复用的市场研究数据库表；不据此推断其他系统不存在这些能力。

## 已实现

1. `collect_news_context.py` 使用公开GET接口读取近7日趋势线索，保存 `market-news.json`。不带cookie、不读环境凭据、不调用助手或模型。`ok / no_matches / unavailable` 明确区分。失败保留错误；无结果不能转译成零需求。
2. `build_market_report.py` 输出市场排名、来源、角色判断及draft桥接候选。
3. 选定路线后 `export_handoff.py` 输出现有客户搜索契约接受的 `lead-discovery-input.json`，并保留 `market-context.json`。可附 `--news-context`；新闻一直是未核原文的侧车数据，不混进贸易统计。
4. 真实客户搜索脚本的 `normalize_input` 已离线验收字段与 `notes` 保留；未调用搜索引擎、生成真实线索或发送邮件。现有各仓库未改动。

## 字段与接入位置

|上游输出|实际接收位置|用途与边界|
|---|---|---|
|product_or_offer、target_market、customer_type、industry_lens、seller_context、search_keywords、exclude_terms|trade-lead-discovery 的 normalize_input|产品×国家×买方搜索约束；多产品不得串线|
|notes|搜索输出内 lead_screening_input.operator_notes 和候选notes|保留研究侧车引用；现有normalizer会丢弃未知字段，不能只添加market_research字段就声称自动传递|
|market-context.json|宿主私有任务目录/企业已有资料容器|保留完整口径、来源、限制和研究判断；宿主需伴随任务保存|
|客户搜索输出的lead_screening_input|现有线索整理入口|只有真实公司候选进入；不能从市场报告捏造公司|
|整理后的customer_intel_input|现有客户背调入口|country_or_market、product_or_offer、seller_context及notes；市场新闻可作待复核信号，不证明该客户采购|
|客户背调的证据与proposed销售角度|现有开发信入口|仅依背调放行与角度审批规则写草稿，不继承市场A级作为发信授权|
|市场侧车+已核客户记录+人工回复/行动记录|企业现有跟进表/CRM人工承接|建议记录研究引用、公司ID、下一动作、负责人、复核日期；本仓库无CRM适配器或自动跟进服务|

## 使用

```bash
python3 scripts/collect_news_context.py --query silk --output /tmp/market-demo/market-news.json
python3 scripts/export_handoff.py \
  --input-json examples/silk-synthetic-input.json \
  --series-id fabric-import --market 'Market Alpha' \
  --selected-by 'demo operator' \
  --news-context /tmp/market-demo/market-news.json --output-dir /tmp/market-handoff
```

真实研究时换成私有输入，并如实记录已完成的选择。CLI参数是操作记录，不是身份认证或权限系统。合成结果仅作演示。

## 尚未打通与下一步

- 资讯站UI没有新增市场背调入口或报告上传；线上助手没有加载本Skill。若要接入，应先设计独立私有研究任务入口、持久化与ACL，再注册异步执行器；不要扩大现有chat body限制冒充接入。
- 搜索以后的侧车自动透传、真实买方搜索、背调、开发信及CRM跟进尚未端到端验收。现阶段宿主将侧车伴随任务保存，继续使用已有下游桥接。
- 没有新增数据库迁移、生产写入、模型调用或部署。将来上线需在测试环境验证失败回退、权限和真实任务，再部署。

核验结果仅证明读取和契约兼容；资讯不是Comtrade统计数据库，不提供海关明细权限。
