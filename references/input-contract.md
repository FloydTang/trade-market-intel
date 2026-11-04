# 输入契约

使用examples/synthetic-input.json作为最小可运行形状。仅支持年度、USD金额（USD/thousand_usd/million_usd）。不同币种先按有依据的汇率转换并保留转换账本，不由脚本猜汇率。

seller_context原样私有保留；seller_role为OEM/ODM/trader/brand；product_or_offer、industry_lens供下游使用。scopes每项须有id、description、hs_version、codes、limitations；代理篮子在limitations注明。脚本不自动合并编码。

series每项绑定id、scope_id、flow（global_import/china_export）、base_year、year、valuation、coverage（reported_available/listed_subset）、coverage_note。每条records有market、market_kind（country/group/world/unspecified）、year、value、unit、source_id，可有quantity、quantity_unit、anomaly。来源sources须含id、url、retrieved_at（ISO日期/时刻）、quality、redistribution。完整HS清单与源表只有获得许可才可共享。

assessments每项指定market、series_id、role_fit/buyer_evidence/landed_cost（各含status和evidence_ids）、customer_type、search_keywords、exclude_terms，可含anomaly。证据ID指sources，不把联系人当必要输入。claims中每项type=observation/inference/missing，text和evidence_ids；missing可无来源。

缺/不合法字段拒绝而不是默默补齐。可选assessments/claims为空表示未完成业务判断，输出不会自动给推荐或搜客任务。脚本不读取个人凭证、不联网。

同一市场允许分别评估四种角色：assessments可指定seller_role；未指定沿用顶层角色。唯一键是series_id+market+seller_role。只输出与顶层实际角色相同的A/B路线。scopes可指定product_or_offer（多产品时应指定），用于确保下游搜索与统计产品一致。

`scripts/export_handoff.py` 只输出明确选定的一条合格路线；选定不是批准销售角度或联系客户。新闻接口适配输出单独存放，不能作为series.records直接输入。
