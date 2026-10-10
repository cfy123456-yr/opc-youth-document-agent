"use strict";

const TASKS = {
  auto: {
    name: "自动判断文书类型",
    folio: "NEW PROOF / AUTO",
    description: "粘贴内容或上传文件，路由器会先判断任务，再调用对应工作流。",
    placeholder: "粘贴简历、申请函、合同条款或票据文字，Agent 会先判断任务类型。",
    exampleTask: "contract",
    hint: "无需 API Key，默认使用本地规则。",
  },
  resume: {
    name: "优化求职简历",
    folio: "NEW PROOF / RESUME",
    description: "根据目标岗位检查匹配度、关键词缺口和缺少证据的经历表达。",
    placeholder: "粘贴完整简历，包括教育经历、项目、实习和技能。",
    exampleTask: "resume",
    hint: "补充目标岗位或 JD 后，匹配结果会更具体。",
  },
  letter: {
    name: "润色申请函",
    folio: "NEW PROOF / LETTER",
    description: "改善语气、结构和表达，同时保留你已提供的事实与承诺边界。",
    placeholder: "粘贴申请书、说明信或正式函件全文。",
    exampleTask: "letter",
    hint: "Agent 不会替你增加未提供的经历、奖项或保证。",
  },
  contract: {
    name: "审阅合同风险",
    folio: "NEW PROOF / CONTRACT",
    description: "标记押金、违约金、解除、续约和竞业等需要重点复核的条款。",
    placeholder: "粘贴租房合同、实习协议、劳动合同或服务协议全文。",
    exampleTask: "contract",
    hint: "合同结果只用于辅助理解，不构成法律意见。",
  },
  receipt: {
    name: "整理票据明细",
    folio: "NEW PROOF / RECEIPT",
    description: "提取商家、日期、金额和类别，计算合计并标记疑似重复项。",
    placeholder: "粘贴 OCR 文本、发票明细或一行一张票据的报销清单。",
    exampleTask: "receipt",
    hint: "导出后仍需使用原始票据逐项核对。",
  },
};

const TASK_LABELS = {
  auto: "自动识别",
  resume: "简历",
  letter: "申请函",
  contract: "合同",
  receipt: "票据",
  unknown: "未识别",
};

const SEVERITY_LABELS = {
  high: "高风险",
  medium: "需确认",
  low: "可优化",
};

const state = {
  task: "auto",
  mode: "paste",
  file: null,
  loading: false,
  result: null,
  maxUploadBytes: 15 * 1024 * 1024,
  maxInputChars: 0,
  publicDemo: false,
  onlineModel: false,
  requiresConsent: false,
};

const elements = {
  form: document.querySelector("#agent-form"),
  taskButtons: [...document.querySelectorAll(".task-tab")],
  sourceModes: [...document.querySelectorAll('input[name="source-mode"]')],
  pastePanel: document.querySelector("#paste-panel"),
  uploadPanel: document.querySelector("#upload-panel"),
  content: document.querySelector("#content"),
  charCount: document.querySelector("#char-count"),
  goalGroup: document.querySelector("#goal-group"),
  goal: document.querySelector("#goal"),
  fileInput: document.querySelector("#file"),
  fileMeta: document.querySelector("#file-meta"),
  fileName: document.querySelector("#file-name"),
  fileSize: document.querySelector("#file-size"),
  clearFile: document.querySelector("#clear-file"),
  exampleButton: document.querySelector("#example-button"),
  runButton: document.querySelector("#run-button"),
  formHint: document.querySelector("#form-hint"),
  formError: document.querySelector("#form-error"),
  statusRegion: document.querySelector("#status-region"),
  providerStatus: document.querySelector("#provider-status"),
  runtimeBadge: document.querySelector(".runtime-badge"),
  demoBanner: document.querySelector("#demo-banner"),
  demoNotice: document.querySelector("#demo-notice"),
  aiConsent: document.querySelector("#ai-consent"),
  aiConsentCopy: document.querySelector("#ai-consent-copy"),
  consentCheckbox: document.querySelector("#consent-checkbox"),
  privacyNoteTitle: document.querySelector("#privacy-note-title"),
  privacyNoteCopy: document.querySelector("#privacy-note-copy"),
  taskTitle: document.querySelector("#current-task-title"),
  taskDescription: document.querySelector("#task-description"),
  routeStamp: document.querySelector("#route-stamp"),
  routeStampLabel: document.querySelector("#route-stamp-label"),
  resultSection: document.querySelector("#result-section"),
  resultTitle: document.querySelector("#result-title"),
  resultSummary: document.querySelector("#result-summary"),
  resultConfidence: document.querySelector("#result-confidence"),
  metaTask: document.querySelector("#meta-task"),
  metaRouteConfidence: document.querySelector("#meta-route-confidence"),
  metaProvider: document.querySelector("#meta-provider"),
  warningsBlock: document.querySelector("#warnings-block"),
  warningsList: document.querySelector("#warnings-list"),
  findingCount: document.querySelector("#finding-count"),
  findingList: document.querySelector("#finding-list"),
  structuredResult: document.querySelector("#structured-result"),
  downloadList: document.querySelector("#download-list"),
  boundaryNote: document.querySelector("#boundary-note"),
  boundaryTitle: document.querySelector("#boundary-title"),
  boundaryCopy: document.querySelector("#boundary-copy"),
  latestNote: document.querySelector("#latest-note"),
  steps: [...document.querySelectorAll(".process-strip li")],
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setTask(task) {
  if (!TASKS[task] || state.loading) {
    return;
  }
  state.task = task;
  const config = TASKS[task];

  elements.taskButtons.forEach((button) => {
    button.setAttribute(
      "aria-pressed",
      String(button.dataset.task === task),
    );
  });

  elements.taskTitle.textContent = config.name;
  elements.taskDescription.textContent = config.description;
  elements.content.placeholder = config.placeholder;
  elements.formHint.textContent = config.hint;
  elements.goalGroup.hidden = task !== "resume";
  elements.routeStamp.className = "route-stamp is-idle";
  elements.routeStampLabel.textContent = "待处理";
  updateCharCount();
}

function setSourceMode(mode) {
  state.mode = mode;
  const isUpload = mode === "upload";
  elements.pastePanel.hidden = isUpload;
  elements.uploadPanel.hidden = !isUpload;
  elements.content.required = !isUpload;
  clearFormError();
}

function updateCharCount() {
  const count = elements.content.value.trim().length;
  const limit = state.maxInputChars
    ? ` / ${state.maxInputChars.toLocaleString("zh-CN")}`
    : "";
  elements.charCount.textContent = `${count.toLocaleString("zh-CN")}${limit} 字符`;
}

function updateRunAvailability() {
  elements.runButton.disabled =
    state.loading ||
    (state.requiresConsent && !elements.consentCheckbox.checked);
}

function formatBytes(bytes) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function showFile(file) {
  state.file = file || null;
  elements.fileMeta.hidden = !state.file;
  if (!state.file) {
    elements.fileInput.value = "";
    return;
  }
  elements.fileName.textContent = state.file.name;
  elements.fileSize.textContent = formatBytes(state.file.size);
}

function showFormError(message) {
  elements.formError.textContent = message;
  elements.formError.hidden = false;
  elements.formError.focus({ preventScroll: true });
}

function clearFormError() {
  elements.formError.textContent = "";
  elements.formError.hidden = true;
}

function setProcessStep(activeStep, allDone = false) {
  const order = ["read", "route", "review"];
  const activeIndex = order.indexOf(activeStep);
  elements.steps.forEach((step) => {
    const index = order.indexOf(step.dataset.step);
    step.classList.toggle("is-active", !allDone && index === activeIndex);
    step.classList.toggle(
      "is-done",
      allDone ? index <= activeIndex : index < activeIndex,
    );
  });
}

function renderProcessing() {
  elements.routeStamp.className = "route-stamp is-idle";
  elements.routeStampLabel.textContent = "处理中";
  elements.statusRegion.innerHTML = `
    <div class="processing-state">
      <div class="processing-copy">
        <strong>正在读取并校样</strong>
        <p id="processing-copy">本地解析文件，随后路由到 ${
          escapeHtml(TASKS[state.task].name)
        }。</p>
      </div>
      <div class="skeleton" aria-hidden="true">
        <span></span><span></span><span></span>
      </div>
    </div>
  `;
}

function renderError(message) {
  elements.routeStamp.className = "route-stamp is-review";
  elements.routeStampLabel.textContent = "处理失败";
  elements.statusRegion.innerHTML = `
    <div class="error-state">
      <strong>这次校样没有完成</strong>
      <p>${escapeHtml(message)}</p>
    </div>
  `;
  showFormError(message);
  setProcessStep("read");
}

function renderStatusSuccess(data) {
  const task = data.result.task;
  const routeConfidence = Math.round(data.decision.confidence * 100);
  elements.routeStamp.className = "route-stamp is-ready";
  elements.routeStampLabel.textContent = TASK_LABELS[task] || task;
  elements.statusRegion.innerHTML = `
    <div class="success-state">
      <div>
        <strong>校样已生成</strong>
        <p>路由判断为“${escapeHtml(
          TASK_LABELS[task] || task,
        )}”，置信度 ${routeConfidence}%。</p>
      </div>
      <a href="#result-section">查看批注与下载</a>
    </div>
  `;
}

function severityLabel(severity) {
  return SEVERITY_LABELS[String(severity).toLowerCase()] || "需确认";
}

function renderFindings(findings) {
  elements.findingCount.textContent = findings.length
    ? `${findings.length} 条`
    : "没有单独风险项";
  if (!findings.length) {
    elements.findingList.innerHTML = `
      <p class="no-findings">本地规则没有发现需要单独列出的风险项，仍请通读全文。</p>
    `;
    return;
  }
  elements.findingList.innerHTML = findings
    .map((finding) => {
      const severity = String(finding.severity || "medium").toLowerCase();
      const detailRows = [
        finding.evidence
          ? `<div><dt>证据</dt><dd>${escapeHtml(finding.evidence)}</dd></div>`
          : "",
        finding.suggestion
          ? `<div><dt>建议</dt><dd>${escapeHtml(finding.suggestion)}</dd></div>`
          : "",
      ]
        .filter(Boolean)
        .join("");
      return `
        <article class="finding" data-severity="${escapeHtml(severity)}">
          <div class="finding-head">
            <strong>${escapeHtml(finding.title || "待复核事项")}</strong>
            <span class="severity-label">${escapeHtml(
              severityLabel(severity),
            )}</span>
          </div>
          <p>${escapeHtml(finding.detail || "")}</p>
          ${detailRows ? `<dl>${detailRows}</dl>` : ""}
        </article>
      `;
    })
    .join("");
}

function metric(label, value) {
  return `
    <dl class="metric">
      <dt>${escapeHtml(label)}</dt>
      <dd>${escapeHtml(value)}</dd>
    </dl>
  `;
}

function tagList(items) {
  if (!Array.isArray(items) || !items.length) {
    return '<p class="field-help">没有识别到对应项目。</p>';
  }
  return `
    <ul class="tag-list">
      ${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
    </ul>
  `;
}

function renderResume(data) {
  const matched = data.matched_keywords || data.matched || [];
  const missing = data.missing_keywords || data.missing || [];
  return `
    <div class="metric-grid">
      ${metric("岗位匹配度", `${Math.round(Number(data.match_score || 0))}%`)}
      ${metric("命中关键词", matched.length)}
      ${metric("缺口关键词", missing.length)}
    </div>
    <section class="result-block">
      <h3>已匹配关键词</h3>
      ${tagList(matched)}
    </section>
    <section class="result-block">
      <h3>岗位关键词缺口</h3>
      ${tagList(missing)}
    </section>
    ${renderRawDetails(data)}
  `;
}

function renderLetter(data) {
  return `
    <div class="metric-grid">
      ${metric("润色版本", data.polished_text ? "已生成" : "未生成")}
      ${metric("结构建议", (data.structure_suggestions || []).length)}
      ${metric("语气调整", (data.tone_changes || []).length)}
    </div>
    ${
      data.polished_text
        ? `
          <section class="result-block">
            <h3>润色后的文本</h3>
            <pre class="document-preview">${escapeHtml(
              data.polished_text,
            )}</pre>
          </section>
        `
        : ""
    }
    ${
      data.structure_suggestions?.length
        ? `<section class="result-block"><h3>结构建议</h3>${tagList(
            data.structure_suggestions,
          )}</section>`
        : ""
    }
    ${renderRawDetails(data, true)}
  `;
}

function renderContract(data) {
  const counts = data.risk_counts || {};
  return `
    <div class="metric-grid">
      ${metric("风险等级", String(data.risk_level || "unknown").toUpperCase())}
      ${metric("风险分值", data.risk_score ?? 0)}
      ${metric("高风险", counts.high ?? 0)}
      ${metric("中风险", counts.medium ?? 0)}
      ${metric(
        "人工复核",
        data.requires_human_review ? "必须" : "建议",
      )}
    </div>
    ${renderRawDetails(data, true)}
  `;
}

function renderReceipt(data) {
  const items = Array.isArray(data.items) ? data.items : [];
  const totals = data.category_totals || {};
  const rows = items
    .map(
      (item, index) => `
        <tr>
          <td>${index + 1}</td>
          <td>${escapeHtml(item.merchant || "待确认")}</td>
          <td>${escapeHtml(item.date || "待确认")}</td>
          <td>${Number(item.amount || 0).toFixed(2)}</td>
          <td>${escapeHtml(item.category || "其他")}</td>
          <td>${item.needs_confirmation ? "是" : "否"}</td>
        </tr>
      `,
    )
    .join("");
  const totalRows = Object.entries(totals)
    .map(
      ([category, amount]) => `
        <tr>
          <td>${escapeHtml(category)}</td>
          <td>${Number(amount || 0).toFixed(2)}</td>
        </tr>
      `,
    )
    .join("");

  return `
    <div class="metric-grid">
      ${metric("票据数量", items.length)}
      ${metric("合计金额", `¥${Number(data.total || 0).toFixed(2)}`)}
      ${metric(
        "疑似重复",
        (data.duplicate_candidates || []).length,
      )}
      ${metric("币种", data.currency || "CNY")}
    </div>
    ${
      items.length
        ? `
          <section class="result-block">
            <table class="data-table">
              <caption>票据明细，导出前请逐条核对。</caption>
              <thead>
                <tr>
                  <th>#</th><th>商家</th><th>日期</th>
                  <th>金额</th><th>类别</th><th>待确认</th>
                </tr>
              </thead>
              <tbody>${rows}</tbody>
            </table>
          </section>
        `
        : '<p class="field-help">没有从文本中识别到票据。</p>'
    }
    ${
      totalRows
        ? `
          <section class="result-block">
            <h3>类别合计</h3>
            <table class="data-table">
              <thead><tr><th>类别</th><th>金额</th></tr></thead>
              <tbody>${totalRows}</tbody>
            </table>
          </section>
        `
        : ""
    }
    ${renderRawDetails(data, true)}
  `;
}

function renderRawDetails(data, readOnlySummary = false) {
  return `
    <details class="json-details">
      <summary>${readOnlySummary ? "查看完整 JSON" : "查看完整结构化数据"}</summary>
      <pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre>
    </details>
  `;
}

function renderStructured(task, data) {
  if (task === "resume") {
    elements.structuredResult.innerHTML = renderResume(data);
  } else if (task === "letter") {
    elements.structuredResult.innerHTML = renderLetter(data);
  } else if (task === "contract") {
    elements.structuredResult.innerHTML = renderContract(data);
  } else if (task === "receipt") {
    elements.structuredResult.innerHTML = renderReceipt(data);
  } else {
    elements.structuredResult.innerHTML = renderRawDetails(data);
  }
}

function renderDownloads(outputs) {
  if (!outputs?.length) {
    elements.downloadList.innerHTML = "<span>没有可下载文件。</span>";
    return;
  }
  elements.downloadList.innerHTML = outputs
    .map(
      (output) => `
        <a class="download-link" href="${escapeHtml(
          output.download_url,
        )}" download>
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 4v11M7 10l5 5 5-5M5 20h14"></path>
          </svg>
          ${escapeHtml(output.name)}
        </a>
      `,
    )
    .join("");
}

function renderBoundary(task, data) {
  let title = "";
  let copy = "";
  if (task === "contract") {
    title = "这份校样不是法律意见";
    copy =
      data.disclaimer ||
      "请结合合同原件和自身情况人工确认，重要决定应咨询律师或专业机构。";
  } else if (task === "receipt") {
    title = "金额和类别必须回到原票据核对";
    copy =
      "重复项、日期和商家可能存在 OCR 误差，本结果不能替代财务凭证审核。";
  } else if (task === "resume" || task === "letter") {
    title = "不要提交未经确认的新事实";
    copy =
      "请检查润色或建议是否引入未提供的经历、数字、证书、承诺或其他事实。";
  }
  elements.boundaryNote.hidden = !title;
  elements.boundaryTitle.textContent = title;
  elements.boundaryCopy.textContent = copy;
}

function renderResult(data) {
  state.result = data;
  const task = data.result.task;
  const result = data.result;
  const decision = data.decision;
  const reviewRequired =
    Boolean(result.data?.requires_human_review) ||
    task === "contract" ||
    task === "receipt";

  elements.resultSection.hidden = false;
  elements.resultSection.classList.toggle("has-review", reviewRequired);
  elements.resultTitle.textContent = `${TASK_LABELS[task] || task}校样`;
  elements.resultSummary.textContent = result.summary || "处理完成。";
  elements.resultConfidence.textContent = `${Math.round(
    Number(result.confidence || 0) * 100,
  )}%`;
  elements.metaTask.textContent =
    `${TASK_LABELS[task] || task} / ${decision.reason || "任务已确定"}`;
  elements.metaRouteConfidence.textContent = `${Math.round(
    Number(decision.confidence || 0) * 100,
  )}%`;
  elements.metaProvider.textContent =
    data.provider === "mock" ? "本地规则" : "在线处理";

  const warnings = result.warnings || [];
  elements.warningsBlock.hidden = !warnings.length;
  elements.warningsList.innerHTML = warnings
    .map((warning) => `<li>${escapeHtml(warning)}</li>`)
    .join("");

  renderFindings(result.findings || []);
  renderStructured(task, result.data || {});
  renderDownloads(data.outputs || []);
  renderBoundary(task, result.data || {});

  elements.latestNote.innerHTML = `
    <p class="section-label">最近校样</p>
    <strong>${escapeHtml(TASK_LABELS[task] || task)} · ${Math.round(
      Number(result.confidence || 0) * 100,
    )}%</strong>
    <p>${escapeHtml(result.summary || "处理完成。")}</p>
  `;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error(`服务返回了无法解析的内容（HTTP ${response.status}）。`);
  }
  if (!response.ok) {
    throw new Error(payload.error || `请求失败（HTTP ${response.status}）。`);
  }
  return payload;
}

async function loadExample() {
  if (state.loading) {
    return;
  }
  clearFormError();
  elements.exampleButton.disabled = true;
  const exampleTask = TASKS[state.task].exampleTask;
  const exampleLabel = TASK_LABELS[exampleTask] || exampleTask;
  elements.formHint.textContent = `正在载入${exampleLabel}示例...`;
  try {
    const data = await requestJson(
      `api/examples?task=${encodeURIComponent(exampleTask)}`,
    );
    if (state.task === "auto") {
      setSourceMode("paste");
      document.querySelector('input[name="source-mode"][value="paste"]').checked = true;
    }
    elements.content.value = data.content || "";
    elements.goal.value = data.goal || "";
    updateCharCount();
    elements.formHint.textContent =
      state.task === "auto"
        ? `已载入${exampleLabel}示例，可用于测试自动路由。`
        : `已载入${exampleLabel}示例。`;
  } catch (error) {
    elements.formHint.textContent = TASKS[state.task].hint;
    showFormError(error.message);
  } finally {
    elements.exampleButton.disabled = false;
  }
}

async function runAgent(event) {
  event.preventDefault();
  if (state.loading) {
    return;
  }
  clearFormError();

  if (state.mode === "paste" && !elements.content.value.trim()) {
    showFormError("请先粘贴文书内容，或载入一份示例。");
    elements.content.focus();
    return;
  }
  if (state.mode === "upload" && !state.file) {
    showFormError("请选择一份文件，或切换到粘贴文本。");
    elements.fileInput.focus();
    return;
  }
  if (state.file && state.file.size > state.maxUploadBytes) {
    const limitMb = Math.round(state.maxUploadBytes / 1024 / 1024);
    showFormError(`文件超过 ${limitMb} MB，请压缩或拆分后再试。`);
    return;
  }
  if (state.requiresConsent && !elements.consentCheckbox.checked) {
    showFormError("请先阅读并确认隐私安全提示。");
    elements.consentCheckbox.focus();
    return;
  }

  state.loading = true;
  let completed = false;
  updateRunAvailability();
  elements.runButton.classList.add("is-loading");
  elements.runButton.querySelector("span").textContent = "正在校样";
  setProcessStep("read");
  renderProcessing();

  const formData = new FormData();
  formData.append("task", state.task);
  formData.append("goal", elements.goal.value.trim());
  if (state.requiresConsent && elements.consentCheckbox.checked) {
    formData.append("consent", "accepted");
  }
  if (state.mode === "upload") {
    formData.append("file", state.file, state.file.name);
  } else {
    formData.append("content", elements.content.value);
  }

  try {
    setProcessStep("route");
    const data = await requestJson("api/run", {
      method: "POST",
      body: formData,
    });
    setProcessStep("review", true);
    renderResult(data);
    renderStatusSuccess(data);
    completed = true;
    requestAnimationFrame(() => {
      elements.resultSection.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  } catch (error) {
    renderError(error.message);
  } finally {
    state.loading = false;
    if (completed && state.requiresConsent) {
      elements.consentCheckbox.checked = false;
    }
    updateRunAvailability();
    elements.runButton.classList.remove("is-loading");
    elements.runButton.querySelector("span").textContent = "运行 Agent";
    if (completed) {
      setTimeout(() => {
        if (!state.loading) {
          setProcessStep("review", true);
        }
      }, 800);
    }
  }
}

async function checkHealth() {
  try {
    const data = await requestJson("api/health");
    if (Number.isFinite(Number(data.max_upload_bytes))) {
      state.maxUploadBytes = Number(data.max_upload_bytes);
    }
    if (Number.isFinite(Number(data.max_input_chars))) {
      state.maxInputChars = Number(data.max_input_chars);
      updateCharCount();
    }
    elements.runtimeBadge.classList.add("is-ready");
    state.publicDemo = Boolean(data.public_demo);
    state.onlineModel = Boolean(data.online_model);
    state.requiresConsent = state.publicDemo && state.onlineModel;
    elements.aiConsent.hidden = !state.requiresConsent;

    elements.aiConsentCopy.textContent = state.requiresConsent
      ? "请先确认文书已经脱敏；提交后正文会离开本站处理。"
      : "";

    if (data.public_demo) {
      const retentionMinutes = Math.max(
        1,
        Math.round(Number(data.retention_seconds || 0) / 60),
      );
      elements.demoBanner.hidden = false;
      if (state.onlineModel) {
        const perIpLimit = Number(data.max_runs_per_day || 0);
        const globalLimit = Number(data.global_runs_per_day || 0);
        const quotaParts = [];
        if (perIpLimit > 0) {
          quotaParts.push(`每 IP 每日 ${perIpLimit} 次`);
        }
        if (globalLimit > 0) {
          quotaParts.push(`全站每日 ${globalLimit} 次`);
        }
        const quotaText = quotaParts.length
          ? `限额：${quotaParts.join("，")}。`
          : "在线调用受额度限制。";
        elements.demoNotice.textContent =
          `请勿提交身份证件、联系方式、财务、医疗、未公开合同等敏感信息；` +
          `每次提交均需确认。` +
          `${quotaText}本站生成结果约 ${retentionMinutes} 分钟后自动删除。`;
        elements.providerStatus.textContent =
          "公网在线 · 请勿提交敏感信息";
        elements.privacyNoteTitle.textContent = "提交前请脱敏";
        elements.privacyNoteCopy.textContent =
          "请勿提交身份证件、联系方式或未公开合同。结果写入";
      } else {
        elements.demoNotice.textContent =
          `请勿上传真实证件、合同、简历或票据。` +
          `结果约 ${retentionMinutes} 分钟后自动删除。`;
        elements.providerStatus.textContent = "公开演示 · 本地规则";
        elements.privacyNoteTitle.textContent = "公开演示";
        elements.privacyNoteCopy.textContent =
          "当前仅运行本地规则，不上传云端。结果写入";
      }
    } else {
      elements.providerStatus.textContent =
        data.provider !== "mock"
          ? "在线处理 · 请勿提交敏感信息"
          : "本地规则 · 无需 API Key";
    }
    updateRunAvailability();
  } catch (error) {
    elements.runtimeBadge.classList.add("is-error");
    elements.providerStatus.textContent = "本地服务状态未知";
  }
}

function bindEvents() {
  elements.taskButtons.forEach((button, index) => {
    button.addEventListener("click", () => setTask(button.dataset.task));
    button.addEventListener("keydown", (event) => {
      const keys = ["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp", "Home", "End"];
      if (!keys.includes(event.key) || state.loading) {
        return;
      }
      event.preventDefault();
      let nextIndex = index;
      if (event.key === "Home") {
        nextIndex = 0;
      } else if (event.key === "End") {
        nextIndex = elements.taskButtons.length - 1;
      } else if (event.key === "ArrowRight" || event.key === "ArrowDown") {
        nextIndex = (index + 1) % elements.taskButtons.length;
      } else {
        nextIndex =
          (index - 1 + elements.taskButtons.length) %
          elements.taskButtons.length;
      }
      const nextButton = elements.taskButtons[nextIndex];
      nextButton.focus();
      setTask(nextButton.dataset.task);
    });
  });

  elements.sourceModes.forEach((input) => {
    input.addEventListener("change", () => {
      if (input.checked) {
        setSourceMode(input.value);
      }
    });
  });

  elements.content.addEventListener("input", updateCharCount);
  elements.fileInput.addEventListener("change", () => {
    showFile(elements.fileInput.files?.[0] || null);
    clearFormError();
  });
  elements.clearFile.addEventListener("click", () => {
    showFile(null);
    clearFormError();
  });
  elements.consentCheckbox.addEventListener("change", () => {
    clearFormError();
    updateRunAvailability();
  });
  elements.exampleButton.addEventListener("click", loadExample);
  elements.form.addEventListener("submit", runAgent);
}

function init() {
  bindEvents();
  setTask("auto");
  setSourceMode("paste");
  checkHealth();
}

init();
