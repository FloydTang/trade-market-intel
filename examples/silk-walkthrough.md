# 真丝工厂流程验证（合成案例）

此例验证方法与交接，不是任何真实客户的市场报告。公司、国家标签、能力与金额均为合成；不引用客户内部资料。运行输入为 `silk-synthetic-input.json`，输出见 `silk-output/`。

## 先分产品路线

假设一家工厂准备推真丝面料，并考虑枕套、眼罩、睡衣、围巾。不能用一个真丝总额判断所有SKU。面料路线用500720作分类候选；须按实际成分、织法及HS版本核实，原料和制成品另线。WITS的[公开500720进口展示页](https://wits.worldbank.org/trade/comtrade/en/country/ALL/year/2024/tradeflow/Imports/partner/WLD/product/500720)可用于理解统计入口，不代表合成值来自该页。页面摘要可能混列欧盟与成员国，国家榜必须剔除集团。

枕套/眼罩的六位码未必能隔离纯真丝，必须取得SKU规格与报关建议；不能用面料进口额推算枕套消费或品牌销量。此例只开放面料路线，其余标为待分类。

## 统计与判断分开

合成进口系列中Alpha规模为300万美元，比200万美元增加100万美元，增速50%；Missing缺基年，Zero基年明确为0，Decline负增长，Bloc不入国家榜。中国出口合成系列Beta高于Alpha，说明两个流向可得不同顺序；不能将其相除称真实市占率。

同一Alpha市场的四角色判断如下，全部只是示范假设：

|角色|此例等级|适配路径|风险和下一步|
|---|---|---|---|
|OEM|B|面料进口商、当地成衣厂|先核规格、MOQ、批量稳定性、到岸成本和买方证据|
|ODM|B|需要开发印花/系列的品牌与渠道|先核开发样、设计权属、测试；无开发证据不能沿用OEM判断|
|纯贸易|B|需要混单、多供应商采购的进口商|先核整合采购价值、验货和履约；规模不能证明服务溢价|
|品牌商|hold|本地零售/分销/消费者|缺获客、退货、渠道毛利和品牌能力证据；不将工厂优势等同品牌适配|

这里三种B级只演示证据门槛，不证明市场同样适合三种角色。真实分析应分别补角色证据、竞争及准入判断。顶层实际角色为OEM，所以只导出OEM路线。改成brand将没有可导出的路线。

## 研究仍须补齐的部分

- 供应来源：目标国进口伙伴表、主要供应国变化、当地加工链和替代材料；此例未提供，标missing。
- 趋势：需3–5年可比序列，本例仅一年同比，不能叫长期趋势。
- 准入：按SKU、原产地、最终税号、交易角色和日期查税费、纤维/护理标签、测试与进口责任；此例未核，不填税率。
- 企业能力：产能、MOQ、工序自有/外协、有效证书、开发样和报价均需实际授权资料；此例不提供任何认证或利润承诺。

## 复算与交接

```bash
python3 scripts/build_market_report.py --input-json examples/silk-synthetic-input.json --output-dir /tmp/silk-market
python3 scripts/export_handoff.py --input-json examples/silk-synthetic-input.json --series-id fabric-import --market 'Market Alpha' --selected-by 'demo operator' --output-dir /tmp/silk-handoff
```

搜索词是silk fabric importer / silk garment manufacturer；排除招聘、工厂同行与无采购主体的零售页面。搜索后先整理候选，再做公司级背调。市场规模与新闻不能写成“贵司正在采购”的开发信事实。
