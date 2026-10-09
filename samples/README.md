# 样本目录

这个目录同时保存真实样本验收入口和公开回归集。正式真实用户样本正文、目标文件和
人工基线放在 `samples/private/`，该目录不会进入 Git；公开许可与项目合成样本放在
`samples/public/`，可以随代码分发，但不得冒充真实用户证据。

## 目标

- 每类任务 5 份，共 20 份脱敏文档。
- 每份样本都有明确的人工基线和事实边界。
- 批量运行后只保存汇总报告，不把正文写入报告。

## 目录

```text
samples/
├─ manifest.csv          # Git 跟踪的空清单模板
├─ manifest.local.csv    # 本机真实样本登记表，不提交
├─ private/              # 真实脱敏样本和人工基线，不提交
├─ public/              # 20 份公开许可与合成回归样本
└─ templates/            # 可复制的清单与基线格式
```

## 公开回归集

`samples/public/` 包含简历、申请函、合同、票据各 5 份。其中 15 份来自公开许可
数据或模板，5 份申请函为项目合成；当前 20/20 通过解析、路由和基线检查。来源、
许可证和派生方式见 `samples/public/README.md`。

公开回归集用于发现代码回归，不能计入决策门 C。正式验收仍需要 20 份
`evidence_type=real` 的真实用户脱敏样本。

## 添加一份样本

1. 将脱敏正文放入 `samples/private/`。
2. 如有目标岗位或处理目标，创建独立的 `*-goal.txt`。
3. 按 `samples/templates/baseline.example.json` 创建人工基线。
4. 将一行记录写入 `samples/manifest.local.csv`。
5. 运行：

```powershell
python -m opc_agent samples validate
python -m opc_agent samples eval
```

清单里的路径统一相对于项目根目录。`evidence_type` 可填 `real`、`public` 或
`synthetic`，但只有 `real` 计入决策门 C。`consent_confirmed` 只有在确认样本可
合法用于测试后才能填写 `yes`。`task` 写 `auto` 才会实际验证路由；显式指定
`resume`、`letter`、`contract` 或 `receipt` 时必须与 `expected_task` 一致。
正式样本验收建议使用 `auto`，否则报告会把路由列为“未验证”。`expected_task`
始终填写人工预期任务。

`samples/manifest.local.csv` 不存在时，命令行会回退读取空模板
`samples/manifest.csv`。真实样本登记后，本机命令会自动使用本地清单。

## 基线字段

| 字段 | 用途 |
| --- | --- |
| `goal` | 可选的处理目标；有 `goal_path` 时以目标文件为准 |
| `required_terms` | 预期结果必须出现的关键词或字段 |
| `forbidden_terms` | 一旦出现就视为事实编造或越界风险 |
| `expected_finding_titles` | 人工认为必须发现的标题 |
| `min_findings` | 至少应出现的发现数量 |
| `human_notes` | 人工核对结论，不参与自动判定 |
