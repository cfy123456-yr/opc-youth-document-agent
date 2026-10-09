# 公开许可与合成回归样本

本目录提供 20 份四类任务回归样本，用于在没有真实用户文档时验证解析、自动路由、
规则发现和报告链路。这些样本不是真实用户证据，不能用于宣称决策门 C 已通过。

| 类型 | 数量 | 证据等级 |
| --- | ---: | --- |
| 简历 | 5 | `public` |
| 申请函 | 5 | `synthetic` |
| 合同 | 5 | `public` |
| 票据 | 5 | `public` |

## 来源与脱敏

| 任务 | 来源 | 许可证 | 派生方式 |
| --- | --- | --- | --- |
| 简历 | [dotin-inc/resume-dataset-NER-annotations](https://github.com/dotin-inc/resume-dataset-NER-annotations) | CC0-1.0 | 从 NER XML 提取，替换姓名、邮箱和链接，移除来源平台标识，重写为通用合成事实 |
| 合同 | [hjfl888/legal-docs-cn](https://github.com/hjfl888/legal-docs-cn) | MIT | 从合同模板提取结构，机构、人员、账户和地址全部泛化，补充用于规则回归的典型风险表述 |
| 房屋租赁合同 | [xialugui/community-urban-housing-lease-contract](https://github.com/xialugui/community-urban-housing-lease-contract) | MIT | 参考公开租赁合同结构，所有主体和履行信息泛化后重写 |
| 票据 | [zzzDavid/ICDAR-2019-SROIE](https://github.com/zzzDavid/ICDAR-2019-SROIE) | 仓库 MIT；原始数据许可边界见仓库说明 | 仅派生日期、金额和业务类别，删除商户名称、地址、电话、税号、人员和原始图像 |
| 申请函 | 项目依据全国学生资助管理中心、学职平台公开办理要求合成 | 项目原创 | 不复制个人材料；统一使用占位主体，代码和文字均为项目生成 |

原始数据或许可证发生变化时，以对应上游仓库当前版本为准。第三方版权和许可证文本见
`THIRD_PARTY_NOTICES.md`。

## 运行

```powershell
python -m opc_agent samples validate `
  --manifest samples/public/manifest.csv
python -m opc_agent samples eval `
  --manifest samples/public/manifest.csv `
  --reports-dir reports/public
```

报告中的 `evidence_type=real` 才计入决策门 C。本目录的 `public` 和 `synthetic`
样本只代表公开来源或项目自建覆盖，不得改写为真实用户样本。
