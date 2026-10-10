# 第三方项目参考

本项目没有复制下列仓库的代码。调研结果只用于确定需求、边界和架构，当前实现为独立代码。

| 项目 | 许可证 | 参考内容 |
| --- | --- | --- |
| `srbhr/Resume-Matcher` | Apache-2.0 | 简历、求职信和多模型产品结构 |
| `liangdabiao/resume-matcher-agent-cn` | Apache-2.0 | 中文简历 Web 流程和轻量部署 |
| `coinluu/resume-jd-optimizer-cn` | MIT | JD 分析、事实追问和评测思路 |
| `xiaodingfeng/contract-review` | MIT | 合同上传、风险报告和在线编辑流程 |
| `CSlawyer1985/contract-review-pro` | 仓库未检测到许可证 | 合同审查方法论方向，未复制内容 |
| `EthanYoQ/Invoice-Downloader` | Apache-2.0 | 收票、OCR、分类和 Excel 汇总需求 |
| `PaddlePaddle/PaddleOCR` | Apache-2.0 | 可选 OCR 依赖 |
| `microsoft/markitdown` | MIT | 可选文档转 Markdown 依赖 |
| `pypdfium2-team/pypdfium2` | BSD-3-Clause / Apache-2.0 | 扫描版 PDF 页面渲染，配合 OCR 使用 |
| `Unstructured-IO/unstructured` | Apache-2.0 | 复杂文档解析方向 |

## 公开回归样本来源

以下来源用于派生 `samples/public/` 中的技术回归样本，不代表真实用户样本。
派生范围、删除字段和许可证文本见 `samples/public/README.md` 和
`samples/public/THIRD_PARTY_NOTICES.md`。

| 来源 | 许可证 | 使用方式 |
| --- | --- | --- |
| `dotin-inc/resume-dataset-NER-annotations` | CC0-1.0 | 派生并再次替换姓名、联系方式等字段 |
| `hjfl888/legal-docs-cn` | MIT | 派生合同模板结构并泛化主体和履行信息 |
| `xialugui/community-urban-housing-lease-contract` | MIT | 参考公开租赁合同结构并重写 |
| `zzzDavid/ICDAR-2019-SROIE` | 仓库 MIT；原始数据许可另见上游说明 | 仅派生日期、金额和类别，删除标识和图像 |

## 引入第三方代码前必须做

1. 检查根目录 `LICENSE`，不能只看 README 徽章。
2. 保留版权、许可证和 NOTICE 文件。
3. 禁止直接复制无许可证仓库的提示词、规则或代码。
4. 对合同规则和法律文本确认来源和可核验性。
5. 把第三方依赖记录到依赖清单和发布说明中。
