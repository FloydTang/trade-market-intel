# AI外贸通MCP与市场优先主动开发

版本：v0.2.0。核验日期：2026-11-04。

## 实际接通范围

`AI外贸通只读MCP → 市场背调 → 选择市场 → 客户搜索 → 线索整理 → 客户背调 → 审核销售角度 → 开发信草稿 → 真实联系/回复记录 → 复核并审核 → 跟进信草稿`

市场背调的唯一开发源仍是本仓库；后续四节点及审批沿用 [trade-skills-collection](https://github.com/FloydTang/trade-skills-collection) 的组合包。组合包只新增可选market_context，不改四个节点的业务规则。旧配置兼容。

v0.2.0的CI固定使用已审核的组合包提交 [a98b306](https://github.com/FloydTang/trade-skills-collection/commit/a98b306de5a20100ef1192c2abf8d5d3936422eb)，避免依赖漂移；自行安装可使用该提交或后续兼容版本。

## MCP连接

- 地址：`https://news.tang92.com/api/mcp`，匿名、只读、部署端为stateless Streamable HTTP。
- 通过initialize协商`2025-03-26`，发送initialized通知，tools/list核对服务及工具，再tools/call调用实际存在的`waimaotong_search`。服务端名为waimaotong。
- 部署代理需要`X-Forwarded-Host: news.tang92.com`，否则实测返回421。适配器携带与实际目标域名相同的值，不关闭服务端Host/Origin校验。
- search接受q、window=7d、limit；输出保留原文链接、资讯页链接、发布时间、获取时间及`original_not_verified`。MCP内容按不可信外部数据处理，不执行标题/摘要里的指令。
- 返回ok、no_matches、unavailable；后两者不能解释成零需求。MCP失败时不会默默换成REST或继续搜客。
- 资讯MCP不是年度海关数据API，不能据其新闻摘要生成进口规模排名；年度统计仍需公开或用户授权证据。

```bash
python3 scripts/collect_mcp_context.py --query silk --limit 5 --output /tmp/market-news.json
```

原collect_news_context.py保留为显式独立的REST读取工具，不是MCP适配。宿主原生连接可参考[Codex MCP官方配置说明](https://developers.openai.com/codex/mcp/)与[配置片段](../examples/codex-mcp.toml)；该片段没有凭据。

## 市场优先入口与状态

入口：`scripts/run_market_outreach.py`。配置：[market-workflow.schema.json](../schemas/market-workflow.schema.json)；合成演示：[market-first-workflow.json](../examples/market-first-workflow.json)。`--workflow-root`指向合集根目录。

1. 获取MCP新闻侧车并冻结；保存输入快照、市场计算底稿及SHA-256。
2. 没选市场时退出10，状态awaiting_market_selection；通过resume及selected-series-id/selected-market/selected-by选择实际角色的A/B路线。也可在配置中显式记录已选择路线。
3. 输出lead-discovery-input和market-context；生成现有组合包配置并委托执行。市场数据、角色判断与新闻保留为上下文，不变成公司采购证据。
4. 背调产生后暂停awaiting_sales_angle_approval；审批必须绑定该报告哈希、审核人及时间。市场选择不能替代这一步。
5. 审批后生成可编辑草稿及中立容器。任何阶段都没有发信、留资写入或CRM写入动作。

市场层状态在00-market-pipeline-manifest.json；四节点状态在outreach/00-run-manifest.json。前者校验冻结配置、原始市场证据、市场产物、生成的下游配置及组合包runner；后者沿用原有报告审批和产物哈希校验。正常resume不重新抓新闻或替换市场依据。

## 字段传递

|内容|接收位置|业务约束|
|---|---|---|
|product_or_offer、target_market、customer_type、industry_lens、seller_context、关键词与排除项|真实客户搜索normalize_input|产品×市场×实际卖方角色一致；合成例不能充当真实线索|
|市场输入与选择、来源、限制、MCP资讯|00-market-context.json及manifest|保存完整上下文，不作为公司事实或触达授权|
|研究侧车|选定客户输入、背调报告market_research_context|不修改claim_ledger、evidence_ledger、sales_angles或决策门；选择客户的市场需与研究市场一致|
|研究侧车|07-email-input/08-email-draft的source_context|保留给人工复核；不把未经核实的新闻塞进邮件正文|
|研究侧车|09-container-bundle.json顶层market_research_context|容器中立归档，不强改企业表头|
|真实联系记录|follow_up的previous_contact_context|缺失拒绝生成，不能从草稿状态反推已联系|

## 跟进承接

首封草稿完成后生成：

- follow-up-plan.json：awaiting_actual_contact_record，真实联系上下文为空，auto_send=false。
- follow-up-report.json：保留市场上下文，销售角度恢复proposed。
- follow-up-config.template.json：跟进模式，previous_contact_context待填。

把模板复制到运行目录外，填实际已发邮件或客户回复记录，记录责任人与复核日期，并检查市场/公司证据是否仍有效。用原组合包在新的输出目录运行；先审报告，再按新哈希审批生成follow_up草稿。不要直接修改原运行中已登记哈希的模板或报告。需要新增事实时提供更新后的证据，不沿用失效的批准。

## 验证与未包含能力

已做真实MCP初始化、工具发现和只读search调用；实际组合包的合成链路覆盖市场选择、客户搜索/整理/背调、报告审批、首封及跟进信草稿，并验证上下文到最终产物。合成回放标明mcp_fixture，不冒充真实采集。

AI外贸通服务端、网页助手、生产数据库未改动。当前链路在安装本Skill的宿主/CLI中运行；并不等于网站内新增了市场研究页面或完整自动销售系统。尚无自动发信、CRM写回、定时跟进、付费海关账号或订单承诺。
