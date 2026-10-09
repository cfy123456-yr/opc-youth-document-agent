# 青年文书智能助手 - GitHub 类似项目调研

> 调研日期：2026-10-01  
> 调研方式：GitHub Search API、仓库元数据核验、README 与功能范围检查  
> 说明：Star 数只能反映热度，不代表代码质量、许可证安全或适合直接复用。

## 1. 调研结论

目前没有发现一个完全对应的开源项目，能够同时覆盖：

- 求职简历优化
- 申请书函润色
- 合同风险审阅
- 票据 OCR 和报销整理

但四个方面都已有成熟或可参考的项目，最合理的做法不是重新造全部轮子，而是：

1. 参考成熟项目确定功能边界。
2. 复用许可证允许的底层库。
3. 自己建设统一的用户流程、数据模型、Agent 路由和安全边界。
4. 先做一个模块，再逐步接入其他模块。

## 2. 最值得优先看的项目

| 优先级 | 项目 | 对应模块 | 推荐原因 |
| --- | --- | --- | --- |
| 1 | [srbhr/Resume-Matcher](https://github.com/srbhr/Resume-Matcher) | 简历、求职信 | 功能完整、活跃、Apache-2.0，适合作为求职文书产品基准 |
| 2 | [liangdabiao/resume-matcher-agent-cn](https://github.com/liangdabiao/resume-matcher-agent-cn) | 中文简历 | 中文 Web 应用，Flask + JSON 存储，适合轻量部署和二次开发 |
| 3 | [coinluu/resume-jd-optimizer-cn](https://github.com/coinluu/resume-jd-optimizer-cn) | 中文简历 | MIT，聚焦 JD 驱动、事实追问和 ATS 输出，适合借鉴工作流 |
| 4 | [xiaodingfeng/contract-review](https://github.com/xiaodingfeng/contract-review) | 合同审阅 | MIT，中文合同 Web 应用，包含 OnlyOffice、知识库、法条引用和报告导出 |
| 5 | [EthanYoQ/Invoice-Downloader](https://github.com/EthanYoQ/Invoice-Downloader) | 票据报销 | Apache-2.0，活跃，覆盖邮件收票、PDF/OFD/XML、OCR、分类和 Excel 汇总 |
| 6 | [PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) | OCR 底座 | 中文 OCR 成熟，Apache-2.0，适合票据和合同扫描件识别 |
| 7 | [microsoft/markitdown](https://github.com/microsoft/markitdown) | 文档解析 | MIT，适合把 PDF、DOCX、Office 文件转成 Markdown |
| 8 | [Unstructured-IO/unstructured](https://github.com/Unstructured-IO/unstructured) | 文档解析 | Apache-2.0，适合复杂文档解析、切块和结构化处理 |

## 3. 简历与求职文书

### 3.1 Resume-Matcher

- 仓库：[srbhr/Resume-Matcher](https://github.com/srbhr/Resume-Matcher)
- Star：约 28,550
- 语言：Python
- 许可证：Apache-2.0
- 最近代码推送：2026-09-29
- 功能：简历定制、PDF、求职信、多种 LLM 接入
- 可复用程度：高
- 适合借鉴：
  - 简历与岗位描述匹配流程
  - 多模型接入方式
  - 本地部署思路
  - 简历、PDF、求职信的完整产品结构
- 注意：
  - 功能较多，完整照搬会增加维护成本。
  - 应先核对其最新代码结构和外部服务依赖。

### 3.2 中文简历匹配器

- 仓库：[liangdabiao/resume-matcher-agent-cn](https://github.com/liangdabiao/resume-matcher-agent-cn)
- Star：约 163
- 语言：HTML
- 许可证：Apache-2.0
- 最近代码推送：2026-06-16
- 功能：上传简历、粘贴 JD、岗位匹配分析、HR 视角报告、简历修改建议
- 技术特征：Flask + JSON 文件存储，无数据库依赖
- 可复用程度：高
- 适合借鉴：
  - 中文简历和 JD 流程
  - 轻量级部署方式
  - 页面和结果结构
  - a4cv 简历编辑器整合方式

### 3.3 JD 驱动中文简历优化 Skill

- 仓库：[coinluu/resume-jd-optimizer-cn](https://github.com/coinluu/resume-jd-optimizer-cn)
- Star：约 189
- 许可证：MIT
- 最近代码推送：2026-07-21
- 功能：解析 JD、诊断差距、追问遗漏素材、生成中文定制简历、ATS 纯文本版和面试追问
- 可复用程度：高
- 适合借鉴：
  - 不编造经历的事实追问机制
  - 岗位差距分析
  - ATS 输出格式
  - 测试用例和失败模式设计

### 3.4 中文简历生成 Skill

- 仓库：[Jichengyuuuuu/resume-builder-skill](https://github.com/Jichengyuuuuu/resume-builder-skill)
- Star：约 162
- 最近代码推送：2026-09-23
- 许可证：GitHub 未检测到许可证
- 功能：模糊背景素材生成中文简历，支持 HTML、DOCX、ATS 优化
- 可复用程度：中
- 注意：没有明确许可证时，默认不应直接复制代码或大段内容。

### 简历模块建议

优先参考 `Resume-Matcher` 的功能完整度，结合 `resume-matcher-agent-cn` 的中文场景，再借鉴 `resume-jd-optimizer-cn` 的事实约束和评测方法。

## 4. 合同审阅

### 4.1 中文合同审查 Web 应用

- 仓库：[xiaodingfeng/contract-review](https://github.com/xiaodingfeng/contract-review)
- Star：约 151
- 语言：JavaScript
- 许可证：MIT
- 最近代码推送：2026-08-05
- 功能：
  - DOCX、PDF 上传
  - 扫描件检测
  - AI 预分析
  - 风险分级
  - 法条和审查理由
  - OnlyOffice 在线预览和编辑
  - 知识库、裁判文书增强
  - HTML、PDF、Word 报告导出
- 可复用程度：高
- 适合借鉴：
  - 中文合同审查的完整产品结构
  - 文件上传到风险报告的流程
  - 审阅结果与在线编辑器的结合方式
  - 报告导出设计

### 4.2 专业合同审核 Skill

- 仓库：[CSlawyer1985/contract-review-pro](https://github.com/CSlawyer1985/contract-review-pro)
- Star：约 273
- 语言：Python
- 许可证：GitHub 未检测到许可证，README 标注 MIT
- 最近代码推送：2026-08-14
- 功能：7 步工作流、风险标签、多维评分、HTML 报告、Track Changes 和批注
- 可复用程度：中
- 适合借鉴：
  - 中文合同审查方法论
  - 风险分类和评分维度
  - 修改痕迹和批注输出
- 注意：README 许可证和仓库实际许可证文件不一致，使用前必须确认。

### 4.3 AI Legal Claude

- 仓库：[zubair-trabzada/ai-legal-claude](https://github.com/zubair-trabzada/ai-legal-claude)
- Star：约 1,763
- 语言：Python
- 许可证：GitHub 未检测到许可证
- 最近代码推送：2026-03-27
- 功能：合同审阅、风险分析、NDA 生成、合规检查和 PDF 报告
- 可复用程度：中
- 适合借鉴：
  - 多能力组织方式
  - 风险分析输出
  - 面向客户的可交付报告
- 注意：英文和普通法语境较强，不能直接套用到中国法律场景。

### 4.4 智能合同审查系统

- 仓库：[qingyun1022/smart_contract_reviewer](https://github.com/qingyun1022/smart_contract_reviewer)
- Star：约 93
- 语言：Python
- 许可证：GitHub 未检测到许可证
- 最近代码推送：2025-05-14
- 技术特征：Streamlit、RabbitMQ、MySQL、ChromaDB、RAG
- 可复用程度：中低
- 适合借鉴：法律 RAG 和审查报告生成架构
- 注意：对 MVP 来说组件偏多，且较久未更新。

### 合同模块建议

优先研究 `xiaodingfeng/contract-review` 的产品和技术流程。合同方法论可以参考 `CSlawyer1985/contract-review-pro`，但必须解决许可证和内容来源问题。不要去复制没有明确许可证的 Skill 内容。

## 5. 票据、发票和报销

### 5.1 Invoice-Downloader

- 仓库：[EthanYoQ/Invoice-Downloader](https://github.com/EthanYoQ/Invoice-Downloader)
- Star：约 477
- 语言：Python
- 许可证：Apache-2.0
- 最近代码推送：2026-09-25
- 功能：
  - 从 QQ 或 163 邮箱批量收集发票
  - 支持 PDF、OFD、XML
  - OCR 识别和分类归档
  - 低置信度人工检查
  - 生成 Excel 报销汇总
  - Windows、macOS 桌面版
- 可复用程度：高
- 这是目前最接近票据模块的完整项目。

### 5.2 中国市场混合票据 OCR

- 仓库：[384863451/invoice_ocr](https://github.com/384863451/invoice_ocr)
- Star：约 172
- 语言：Python
- 许可证：GitHub 未检测到许可证
- 最近代码推送：2022-03-20
- 功能：识别增值税发票、火车票、飞机票、出租车票、过路费发票等
- 技术：YOLOv5 + CRNN + CTC
- 可复用程度：中低
- 适合借鉴：中文票据类型和字段设计
- 注意：Python 版本较旧，长期未更新，不建议作为新项目主干。

### 5.3 PaddleOCR

- 仓库：[PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
- Star：约 90,458
- 语言：Python
- 许可证：Apache-2.0
- 最近代码推送：2026-09-16
- 可复用程度：高
- 适合作为合同扫描件、票据和图片的基础 OCR 方案。

## 6. 通用文档解析底座

### MarkItDown

- 仓库：[microsoft/markitdown](https://github.com/microsoft/markitdown)
- Star：约 187,738
- 许可证：MIT
- 最近代码推送：2026-09-21
- 用途：PDF、Office、图片等文件转 Markdown
- 优点：轻量，适合作为文档进入 LLM 前的预处理层

### Unstructured

- 仓库：[Unstructured-IO/unstructured](https://github.com/Unstructured-IO/unstructured)
- Star：约 15,520
- 许可证：Apache-2.0
- 最近代码推送：2026-09-29
- 用途：复杂文档解析、切块、增强和结构化
- 优点：适合合同、PDF 和复杂文档
- 缺点：比 MarkItDown 更重，部署复杂度更高

## 7. 名称相近但不直接对应的一人公司项目

以下项目与本项目主题相关，但不直接解决青年文书问题：

| 项目 | Star | 相关性 |
| --- | ---: | --- |
| [cyfyifanchen/one-person-company](https://github.com/cyfyifanchen/one-person-company) | 约 2,736 | 一人公司 AI 工具和效率资源 |
| [h4dex/opc-nexus](https://github.com/h4dex/opc-nexus) | 约 241 | 本地面向一人公司的数字员工工作台 |
| [Fangx-AI/one-person-company-journal](https://github.com/Fangx-AI/one-person-company-journal) | 约 201 | 一人公司实践记录 |
| [jiangye1314/opc-skill](https://github.com/jiangye1314/opc-skill) | 约 34 | 面向一人公司新手的执行型 Skill 包 |

这些项目可以用于研究一人公司的 Agent 工作方式，但不应替代青年文书项目的产品设计。

## 8. 市场空白

现有开源项目通常按单一能力划分，缺少以下组合能力：

1. 面向青年阶段的统一用户旅程。
2. 求职、签约和在岗三个阶段的数据连续性。
3. 简历、申请书、合同和票据共享的统一文件处理底座。
4. 不编造事实的全局约束。
5. 合同辅助理解而非正式法律意见的边界。
6. 个人隐私、文件保存和删除机制。
7. 将结果导出为 Word、Excel 和风险报告的完整闭环。
8. 中文青年场景、低成本部署和轻量级 Agent 路由。

因此，项目仍有机会，但不适合从“大而全平台”开始。

## 9. 推荐复用方案

| 项目能力 | 推荐参考或依赖 | 使用方式 |
| --- | --- | --- |
| 文档转 Markdown | MarkItDown | 直接作为基础库 |
| 复杂文档结构化 | Unstructured | 按需引入 |
| OCR | PaddleOCR | 作为票据和扫描件底座 |
| 简历与求职信 | Resume-Matcher | 参考产品流程和技术架构 |
| 中文简历 | resume-matcher-agent-cn | 参考轻量 Web 架构 |
| 中文 JD 和事实约束 | resume-jd-optimizer-cn | 参考工作流、测试和失败模式 |
| 合同 Web 应用 | contract-review | 参考产品结构、OnlyOffice 和报告导出 |
| 合同方法论 | contract-review-pro | 先确认许可证，再决定是否参考 |
| 票据与报销 | Invoice-Downloader | 重点研究邮件收票、OCR 和 Excel 导出 |

## 10. 许可证风险

| 许可证状态 | 项目示例 | 使用建议 |
| --- | --- | --- |
| Apache-2.0 | Resume-Matcher、Invoice-Downloader、PaddleOCR | 可复用，但需保留版权和许可证说明 |
| MIT | markitdown、contract-review、resume-jd-optimizer-cn | 可复用，需保留许可证 |
| 未检测到许可证 | ai-legal-claude、contract-review-pro、invoice_ocr | 默认不要直接复制代码或内容 |
| README 声明与仓库不一致 | contract-review-pro | 使用前联系作者或取得明确授权 |

许可证不应只看 README 徽章，应以仓库根目录的 `LICENSE` 文件和法律条款为准。

## 11. 最终建议

第一轮不建议直接 Fork 一个大项目。更合适的顺序是：

1. 运行并体验 `Resume-Matcher`。
2. 查看 `resume-matcher-agent-cn` 的中文实现。
3. 抽出 `resume-jd-optimizer-cn` 的事实约束和评测设计。
4. 研究 `contract-review` 的合同上传、风险报告和在线编辑流程。
5. 研究 `Invoice-Downloader` 的票据收集、OCR 和 Excel 导出。
6. 自己搭建统一的任务、文件和 Agent 流程。
7. 第一版只落地求职文书，不同时启动四个模块。

项目最值得差异化的部分不是 OCR 或基础文档解析，而是：

> 面向中国青年的一体化文书流程、事实可信度、隐私边界和清晰的责任提示。
