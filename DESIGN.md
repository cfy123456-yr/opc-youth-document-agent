---
name: 青年文书智能助手
description: 本地优先的青年文书校样工作台
colors:
  desk: "#171a1c"
  desk-soft: "#202427"
  desk-rule: "#343a3d"
  desk-text: "#e8eceb"
  desk-muted: "#9aa5a7"
  paper: "#f6f5ef"
  paper-strong: "#fffefa"
  paper-muted: "#e9e9e2"
  ink: "#172024"
  ink-soft: "#536064"
  rule: "#c8cfce"
  rule-soft: "#dfe4e2"
  proof-red: "#c83e35"
  proof-red-deep: "#9e2f29"
  route-blue: "#2c6595"
  approval-green: "#2e7158"
  review-amber: "#aa6f18"
  focus-amber: "#f0b94a"
  scroll-thumb: "#667174"
typography:
  display:
    fontFamily: "Songti SC, STSong, Noto Serif CJK SC, serif"
    fontSize: "32px"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Microsoft YaHei UI, PingFang SC, Noto Sans CJK SC, Source Han Sans SC, sans-serif"
    fontSize: "24px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  body:
    fontFamily: "Microsoft YaHei UI, PingFang SC, Noto Sans CJK SC, Source Han Sans SC, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "normal"
  label:
    fontFamily: "Cascadia Mono, SFMono-Regular, Consolas, monospace"
    fontSize: "11px"
    fontWeight: 700
    lineHeight: 1.4
    letterSpacing: "0.12em"
  data:
    fontFamily: "Cascadia Mono, SFMono-Regular, Consolas, monospace"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
rounded:
  xs: "1px"
  control: "2px"
  status-dot: "50%"
spacing:
  xxs: "7px"
  xs: "10px"
  sm: "12px"
  md: "18px"
  lg: "28px"
  xl: "44px"
components:
  button-primary:
    backgroundColor: "{colors.proof-red}"
    textColor: "#ffffff"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "10px 15px"
    height: "46px"
  button-primary-active:
    backgroundColor: "#b9362f"
    textColor: "#ffffff"
    rounded: "{rounded.control}"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "10px 15px"
    height: "46px"
  task-tab:
    backgroundColor: "{colors.desk-soft}"
    textColor: "{colors.desk-muted}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "10px 12px"
    height: "62px"
  task-tab-active:
    backgroundColor: "{colors.paper-strong}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
  document-input:
    backgroundColor: "#fbfaf5"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.xs}"
    padding: "15px 16px"
  proof-sheet:
    backgroundColor: "{colors.paper-strong}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "0px"
    padding: "clamp(26px, 4vw, 48px)"
  result-stamp:
    backgroundColor: "transparent"
    textColor: "{colors.proof-red}"
    typography: "{typography.data}"
    size: "112px 76px"
  download-link:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper-strong}"
    typography: "{typography.body}"
    rounded: "0px"
    padding: "9px 12px"
    height: "44px"
---

# Design System: 青年文书智能助手

## Overview

**Creative North Star: "编辑校样桌"**

界面是一张局部照亮的编辑校样桌：石墨色工作台承托白色文书纸，文件标签负责建立任务秩序，红、蓝、绿、琥珀四种批注色只在证据、风险、导出和复核节点出现。它不追求营销页的戏剧感，也不伪装成通用聊天窗口；页面首先是一套可扫描、可核对、可导出的工作工具。

密度来自专业排版而不是堆叠卡片。分隔线、页码式标签、印章和纸张边缘建立层级，所有操作仍然服从普通网页控件：文本输入、文件上传、单选切换、按钮与下载链接。风险信息以连续批注行呈现，避免把每条结果装进独立卡片而打断阅读。

视觉世界明确拒绝大面积渐变、玻璃模糊、装饰性光斑、悬浮营销卡片和没有依据的确定性。颜色承担语义，纸张承担内容，桌面承担结构。

**Key Characteristics:**

- 石墨色工作台与冷白校样纸形成明确明暗层级。
- 红、蓝、绿、琥珀四色分别承担批注、简历、通过和复核语义。
- 1px 规则线、2px 控件圆角和方形印章构成克制的印刷语言。
- 中文字体负责阅读，等宽字体只用于标签、路由、数值和结构化数据。
- 桌面端三栏并列，移动端转成单列并让文件标签横向滚动。

## Colors

整体采用石墨中性色承托纸面，以暖红作为唯一主动作和主要批注色，其余颜色按文书语义分配。

### Primary

- **校样红** (`#c83e35`): 主运行按钮、高风险批注、合同印章、键盘选择与需要立即注意的边界。
- **深校样红** (`#9e2f29`): 按钮压边、红色正文和浅红背景上的高对比文字。

### Secondary

- **档案蓝** (`#2c6595`): 简历文件标签、文件上传悬停、低风险提示和数据型标记。
- **通过绿** (`#2e7158`): 正常完成状态、结果纸边、可优化或已通过标记。
- **复核琥珀** (`#aa6f18`): 人工确认、运行中状态和侧栏校样边注。

### Neutral

- **石墨工作台** (`#171a1c`): 页面主背景、页脚、下载区和深色文字底层。
- **石墨面板** (`#202427`): 未选中的任务标签和右侧校样边注面板。
- **桌面分隔线** (`#343a3d`): 深色背景上的结构和分隔线。
- **桌面文字** (`#e8eceb`): 深色背景上的主要文字。
- **桌面弱文字** (`#9aa5a7`): 深色背景上的说明、图例和次要状态。
- **校样纸** (`#f6f5ef`): 分段控件、文件信息和表格的次要纸面。
- **高白纸面** (`#fffefa`): 主处理纸、结果纸和当前任务标签。
- **纸张灰** (`#e9e9e2`): 纸张分层、低对比底纹和结构化结果空位。
- **墨色** (`#172024`): 纸面主文字和深色下载容器。
- **次级墨色** (`#536064`): 正文说明、字段提示和证据解释。
- **纸面规则线** (`#c8cfce`): 输入框、表格、批注行和组件边缘。
- **浅规则线** (`#dfe4e2`): 纸张输入区的横线纹理。

### Named Rules

**The One Proof Color Rule.** 校样红只用于主动作、高风险和必须复核的内容；不要用它装饰普通容器。

**The Semantic Ink Rule.** 蓝、绿、琥珀必须继续代表各自任务或状态，同一语义不得随页面位置换色。

## Typography

**Display Font:** Songti SC（含 STSong、Noto Serif CJK SC 回退）

**Body Font:** Microsoft YaHei UI（含 PingFang SC、Noto Sans CJK SC 回退）

**Label/Mono Font:** Cascadia Mono（含 SFMono-Regular、Consolas 回退）

**Character:** 宋体只负责标题和文书摘录，让结果像排好的校样；无衬线负责操作和正文，保持工具感；等宽字体承担路由、字段、百分比和代码数据。

### Hierarchy

- **Display** (700, 32px, 1.15): 当前输入任务和结果标题；移动端降至 26px。
- **Headline** (700, 24px, 1.2): 文件处理台和桌面分栏标题；移动端降至 20px。
- **Title** (700, 18px 到 21px, 1.3): 结果区块、上传提示和侧栏标题。
- **Body** (400, 15px, 1.55): 页面正文、说明和按钮；移动端基准降至 14px。
- **Label** (700, 11px, 0.12em): 少量结构化标签、字段名和严重度文字。
- **Data** (400 到 800, 12px 到 22px, 1.5): 路由置信度、指标、JSON、日期和金额。

### Named Rules

**The Proof Sheet Type Rule.** 只有文书标题、结果标题和文档预览使用宋体；普通控件不使用展示字体。

**The Data Gets Mono Rule.** 数字、路由、代码和结构化字段使用等宽字体和 `tabular-nums`，不要让正文承担数据排版。

## Layout

桌面端使用 `min(1560px, 100%)` 工作台，三栏比例为 `210px 到 250px | 流式主纸面 | 210px 到 260px`，列间距在 18px 到 34px 之间。主任务纸面最小高度 720px，内部边距在 26px 到 48px 之间；表单内容相对纸张左侧缩进最多 26px，形成装订边。

1180px 时右侧校样边注下移到主纸面下方，并拆成三列说明。760px 时整个工作台转成单列，主纸面边距收至 `26px 18px 28px`，文件标签变成横向滚动轨道。430px 时隐藏品牌文字，压缩运行区，并把路由印章绝对定位到纸面右上角。390px 是已验收的最小宽度。

节奏使用 7px、10px、12px、18px、28px、44px 六档。紧密信息内部保持 7px 到 12px，区块之间使用 18px，纸张与结果之间使用 26px 到 28px，主纸面使用 44px 级别留白。

## Elevation & Depth

系统以平面纸张和边缘分层为主，不使用悬浮卡片式大阴影。主纸面和结果纸通过色值分离、1px 顶部语义边和底部纸叠伪元素建立厚度；底部纸叠使用 `0 5px 12px rgb(0 0 0 / 16%)` 的单层柔和阴影，表达纸张而不是浮起控件。

路由和结果置信度使用 2px 边框与轻微旋转的印章表达注意力。主按钮不使用外部硬偏移阴影，而是使用 3px 深红底边和按下时的位移形成机械按压感。运行状态点保持纯色，不使用零偏移色环。

### Named Rules

**The One Edge Rule.** 控件在描边和柔和抬升之间只选一种；纸张叠层是唯一允许的常规阴影来源。

**The Stamp Not Card Rule.** 需要强调状态时使用印章、规则线和语义色，不要把结果重新包装成悬浮卡片。

## Shapes

整体是直角印刷语言。输入框使用 1px 圆角，按钮和文件标签使用 2px 圆角，纸张和下载块保持直角。只有状态圆点和装订孔使用圆形。所有分隔使用 1px 实线或虚线，不使用粗侧边强调条。

纸张左侧保留三个装订孔，底部用错位浅灰纸层形成叠页轮廓。任务标签使用 7px 彩色右缘作为可翻动的文件索引，这是系统中唯一明确的厚色边，只允许用于任务标签。

## Components

### Buttons

- **Shape:** 最小高度 46px，2px 圆角，1px 透明或规则色边。
- **Primary:** 校样红底、白字、深红 3px 底边，最小宽度 150px；悬停变深，按下收薄底边并下移 3px。
- **Hover / Focus:** 悬停上移 1px；焦点使用 3px 琥珀色轮廓和 3px 偏移。
- **Secondary / Ghost:** 透明底、规则色边、墨色文字；悬停时使用纸张底色并加深边框。

### Tabs and Segments

- **Task tabs:** 62px 最小高度，石墨面板底色，右缘按任务使用蓝、绿、红或琥珀。
- **Selected task:** 切换为高白纸面、墨色文字和白边，不使用宽阴影。
- **Source switch:** 同一 1px 外框内并列两个 44px 高选项；选中项使用墨色底和纸白文字。

### Inputs and Fields

- **Textarea:** 180px 最小高度，1px 规则边、1px 圆角、暖白底和 32px 间距的浅横线，模拟文书纸行。
- **File drop:** 158px 最小高度，虚线边、纸张底色；悬停时边框转为档案蓝并轻微改变底色。
- **File metadata:** 58px 最小高度，纸张底色和 1px 边缘，文件名允许任意位置换行。

### Proof Sheet

主工作纸使用高白纸面、装订孔、左上装订边缩进和红色 1px 顶部校样线。内容按“标题与路由印章 -> 输入 -> 操作 -> 处理状态 -> 结果”排列，一个视口内只能存在一个主运行动作。

### Findings and Structured Results

批注行使用上下 1px 分隔线，不使用卡片。风险菱形标记按严重度使用红、琥珀或蓝；每条批注依次显示结论、证据和行动建议。指标使用共享边框的网格，JSON 使用可展开的等宽代码块。

### Result Stamp

112px 宽、76px 高、2px 当前语义色边框，上右轻微旋转 2deg。百分比使用 22px 等宽粗体，标签使用 10px 小字；合同等必须复核的任务使用校样红。

### Download and Review Boundary

下载区使用墨色整块底板和反白链接，和纸面形成明确结束点。高风险任务在结果末尾保留完整宽度红色边界说明，说明当前结果不是最终法律或财务结论。

## Do's and Don'ts

### Do:

- **Do** 让每个任务只有一个主运行动作，并保持 150px 以上的稳定宽度。
- **Do** 用 1px 规则线、18px 区块间距和 2px 控件圆角建立秩序。
- **Do** 在批注中同时保留结论、证据和可执行建议。
- **Do** 让合同和票据结果显式显示人工复核边界。
- **Do** 在移动端把文件标签变成横向滚动轨道，而不是压缩文字或堆叠成两行。
- **Do** 保持键盘焦点为 3px 琥珀色轮廓，并保留跳转到处理台的链接。

### Don't:

- **Don't** 把结果区块重新包装成彼此分离的圆角卡片。
- **Don't** 使用粗侧边、彩色左线或 3px 以上顶部强调条。
- **Don't** 在标题上方添加小号眉题或“PROOF / TYPE”式标签。
- **Don't** 对普通控件使用宽而弥散的悬浮阴影或硬偏移块阴影。
- **Don't** 把宋体、等宽字体或印章语言扩展到普通按钮和正文。
- **Don't** 用渐变色、玻璃模糊、光斑或装饰动画替代任务状态。
- **Don't** 使用“正式法律意见”“保证通过”“自动提交”等超出产品能力的文案。
