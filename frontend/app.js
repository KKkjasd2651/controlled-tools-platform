const API_BASE = "";

const $ = (sel) => document.querySelector(sel);
const fileInput = $("#file");
const projectInput = $("#project");
const usernameInput = $("#username");
const submitBtn = $("#submitBtn");
const statusEl = $("#status");
const batchPreview = $("#batchPreview");
const batchTbody = $("#batchTable tbody");
const batchCount = $("#batchCount");
const dmlTbody = $("#dmlTable tbody");
const filesTbody = $("#filesTable tbody");
const fsInfo = $("#fsInfo");
const projectSelect = $("#projectSelect");
const dmlDownload = $("#dmlDownload");
const modal = $("#confirmModal");
const modalBody = $("#modalBody");
const modalTitle = $("#modalTitle");
const modalCancel = $("#modalCancel");
const modalConfirm = $("#modalConfirm");

function setStatus(kind, text) {
  statusEl.className = `status show ${kind}`;
  statusEl.textContent = text;
}
function clearStatus() {
  statusEl.className = "status";
  statusEl.textContent = "";
}

/**
 * 按 SBPC 规则解析文件名: <图号>_<版本> <图纸标题>.<后缀>
 * 解析失败返回 { error, identifier, partial }
 */
function parseFilename(name) {
  if (!name) return { error: "文件名为空" };
  const dotIdx = name.lastIndexOf(".");
  if (dotIdx <= 0) return { error: "扩展名缺失", identifier: name };
  const stem = name.slice(0, dotIdx);
  const ext = name.slice(dotIdx + 1).toLowerCase();
  if (!stem) return { error: "图号、版本、图纸标题均缺失", identifier: name };

  const spIdx = stem.indexOf(" ");
  const hasSpace = spIdx >= 0;
  const head = hasSpace ? stem.slice(0, spIdx) : stem;
  const title = hasSpace ? stem.slice(spIdx + 1).trim() : "";

  const usIdx = head.lastIndexOf("_");
  const hasUnderscore = usIdx >= 0;
  const code = hasUnderscore ? head.slice(0, usIdx).trim() : head.trim();
  const fver = hasUnderscore ? head.slice(usIdx + 1).trim() : "";

  const missing = [];
  if (!code)  missing.push("图号");
  if (!fver)  missing.push("版本号");
  if (!title) missing.push("图纸标题");

  if (missing.length) {
    const identifier = (hasSpace ? stem.slice(0, spIdx) : stem) || name;
    return {
      error: `${missing.join("、")}缺失`,
      identifier,
      partial: { code, fver, title, ext },
    };
  }
  return { code, fver, title, ext };
}

/** 渲染批量表 —— 5 列解析 + 1 列提交状态 */
function renderBatchPreview(files) {
  batchTbody.innerHTML = "";
  if (!files || files.length === 0) {
    batchPreview.hidden = true;
    return;
  }
  batchPreview.hidden = false;
  batchCount.textContent = files.length;
  files.forEach((f, i) => {
    const parsed = parseFilename(f.name);
    const tr = document.createElement("tr");
    tr.dataset.index = i;
    const idxTd  = document.createElement("td"); idxTd.textContent = i + 1;
    const nameTd = document.createElement("td"); nameTd.textContent = f.name; nameTd.title = f.name;
    const codeTd = document.createElement("td");
    const fverTd = document.createElement("td");
    const titleTd= document.createElement("td");
    const statusTd = document.createElement("td"); statusTd.className = "status-cell";

    if (parsed.error) {
      codeTd.textContent  = parsed.partial?.code  || "—";
      fverTd.textContent  = parsed.partial?.fver  || "—";
      titleTd.textContent = parsed.partial?.title || "—";
      statusTd.textContent = `未提交 / 格式错误：${parsed.error}`;
      statusTd.classList.add("err");
      tr.classList.add("row-bad");
      tr.dataset.bad = "1";
    } else {
      codeTd.textContent  = parsed.code;
      fverTd.textContent  = parsed.fver;
      titleTd.textContent = parsed.title;
      statusTd.textContent = "待上传";
      statusTd.classList.add("pending");
      tr.dataset.bad = "0";
    }
    tr.append(idxTd, nameTd, codeTd, fverTd, titleTd, statusTd);
    batchTbody.appendChild(tr);
  });
}

function updateRowStatus(index, text, kind) {
  const tr = batchTbody.querySelector(`tr[data-index="${index}"]`);
  if (!tr) return;
  const cell = tr.querySelector(".status-cell");
  cell.textContent = text;
  cell.className = `status-cell ${kind || ""}`;
}

function onFormInput() {
  renderBatchPreview(Array.from(fileInput.files || []));
  if (fileInput.files.length && projectInput.value.trim() && usernameInput.value.trim()) {
    clearStatus();
  }
}

function escapeHtml(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

/** 点 [提交] → 弹出确认弹窗，展示合规/不合规 + 待上传清单 */
function openConfirmModal() {
  const files = Array.from(fileInput.files || []);
  const project = projectInput.value.trim();
  const username = usernameInput.value.trim();

  const missing = [];
  if (!project)  missing.push("工令号");
  if (!username) missing.push("用户名");
  if (!files.length) missing.push("受控文件");
  if (missing.length) {
    setStatus("err", `请先填写：${missing.join(" / ")}`);
    return;
  }

  const ok = [];
  const bad = [];
  files.forEach((f, i) => {
    const p = parseFilename(f.name);
    if (p.error) bad.push({ index: i, name: f.name, identifier: p.identifier, error: p.error });
    else ok.push({ index: i, name: f.name, ...p });
  });

  modalConfirm.disabled = ok.length === 0;

  let html = "";
  if (bad.length === 0) {
    modalTitle.textContent = "提交前校验";
    html = `<div class="modal-summary modal-ok">
      ✅ 全部 <b>${files.length}</b> 个文件命名无误，将全部上传。
    </div>`;
  } else if (ok.length === 0) {
    modalTitle.textContent = "提交前校验";
    html = `<div class="modal-summary modal-warn">
      ⚠ 全部 <b>${files.length}</b> 个文件命名均不合规，
      <b>无法上传</b>。请修改文件名后重选。
    </div>`;
  } else {
    modalTitle.textContent = "提交前校验";
    html = `<div class="modal-summary modal-warn">
      共 <b>${files.length}</b> 个文件 ：合规 <b>${ok.length}</b> 个、
      <span class="err">不合规 <b>${bad.length}</b> 个</span>。
      点击「确认提交」后将<strong>仅上传合规文件</strong>，不合规的保留在列表中提示。
    </div>`;
  }

  if (bad.length) {
    html += `<div class="modal-section"><b>❌ 不合规文件 (${bad.length})</b><ul class="modal-list err">`;
    bad.forEach((it) => {
      html += `<li><code>${escapeHtml(it.name)}</code><br>→ <b>${escapeHtml(it.identifier)}</b> ${escapeHtml(it.error)}</li>`;
    });
    html += `</ul></div>`;
  }

  if (ok.length) {
    html += `<div class="modal-section"><b>✅ 待上传 (${ok.length})</b>`;
    html += `<table class="modal-table"><thead><tr><th>#</th><th>图号</th><th>版本</th><th>图纸标题</th></tr></thead><tbody>`;
    ok.forEach((it, i) => {
      html += `<tr><td>${i+1}</td><td>${escapeHtml(it.code)}</td><td>${escapeHtml(it.fver)}</td><td>${escapeHtml(it.title)}</td></tr>`;
    });
    html += `</tbody></table></div>`;
  }
  modalBody.innerHTML = html;
  modal.hidden = false;
}

function closeModal() { modal.hidden = true; }

async function loadConfig() {
  try {
    const health = await fetch(`${API_BASE}/api/health`).then((r) => r.json());
    if (fsInfo && health.fs_root) fsInfo.textContent = `📁 ${health.fs_root}`;
  } catch (e) {
    setStatus("err", `加载后端配置失败：${e.message}`);
  }
}

async function loadProjects(preferred) {
  try {
    const data = await fetch(`${API_BASE}/api/projects`).then((r) => r.json());
    const projects = data.projects || [];
    projectSelect.innerHTML = "";
    if (projects.length === 0) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "(暂无工令)";
      projectSelect.appendChild(opt);
      dmlTbody.innerHTML = "";
      filesTbody.innerHTML = "";
      dmlDownload.hidden = true;
      return;
    }
    for (const p of projects) {
      const opt = document.createElement("option");
      opt.value = p;
      opt.textContent = p;
      projectSelect.appendChild(opt);
    }
    if (preferred && projects.includes(preferred)) projectSelect.value = preferred;
    await loadDml(projectSelect.value);
  } catch (e) { console.error("加载工令列表失败", e); }
}

async function loadDml(project) {
  if (!project) return;
  try {
    const url = `${API_BASE}/api/dml?project=${encodeURIComponent(project)}`;
    const data = await fetch(url).then((r) => r.json());

    dmlTbody.innerHTML = "";
    for (const row of data.log || []) {
      const tr = document.createElement("tr");
      [row["日期"], row["文档编码"], row["版本"]].forEach((v) => {
        const td = document.createElement("td"); td.textContent = v ?? "";
        tr.appendChild(td);
      });
      dmlTbody.appendChild(tr);
    }
    if (!(data.log || []).length) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = 3; td.style.color = "#94a3b8"; td.textContent = "(尚无受控记录)";
      tr.appendChild(td); dmlTbody.appendChild(tr);
    }

    filesTbody.innerHTML = "";
    (data.files || []).forEach((name, i) => {
      const tr = document.createElement("tr");
      const idxTd = document.createElement("td"); idxTd.textContent = i + 1;
      const nameTd = document.createElement("td"); nameTd.textContent = name;
      tr.append(idxTd, nameTd);
      filesTbody.appendChild(tr);
    });
    if (!(data.files || []).length) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = 2; td.style.color = "#94a3b8"; td.textContent = "(暂无落盘文件)";
      tr.appendChild(td); filesTbody.appendChild(tr);
    }

    if (data.dml_download) {
      dmlDownload.href = data.dml_download;
      dmlDownload.hidden = false;
      dmlDownload.textContent = "下载 文件清单.xlsx";
    } else {
      dmlDownload.hidden = true;
    }
  } catch (e) { console.error("加载 DML 失败", e); }
}

async function uploadOne(file, project, username) {
  const form = new FormData();
  form.append("file", file);
  form.append("project", project);
  form.append("username", username);
  try {
    const resp = await fetch(`${API_BASE}/api/upload`, { method: "POST", body: form });
    const data = await resp.json();
    return { ok: resp.ok, status: resp.status, data };
  } catch (e) {
    return { ok: false, status: 0, data: { detail: e.message } };
  }
}

/** 弹窗里点 [确认提交] → 关闭弹窗 → 真正串行上传 */
async function startUpload() {
  closeModal();
  const files = Array.from(fileInput.files || []);
  const project = projectInput.value.trim();
  const username = usernameInput.value.trim();

  submitBtn.disabled = true;

  let ok = 0, fail = 0, skipped = 0;
  for (let i = 0; i < files.length; i++) {
    const f = files[i];
    const parsed = parseFilename(f.name);
    if (parsed.error) {
      // 表格状态已经写了"未提交 / 格式错误"，跳过
      skipped++;
      continue;
    }
    updateRowStatus(i, "上传中…", "pending");
    setStatus("warn", `上传中 ${ok + fail + 1}/${files.length - skipped} … ${f.name}`);
    const r = await uploadOne(f, project, username);
    if (r.ok) {
      ok++;
      const meta = r.data.meta || {};
      updateRowStatus(i, `✓ V${meta.version || ""}`, "ok");
    } else {
      fail++;
      const detail = r.data?.detail || `HTTP ${r.status}`;
      updateRowStatus(i, `失败：${detail}`, "err");
    }
  }

  const tip = `完成：成功 ${ok}，失败 ${fail}${skipped ? `，跳过 ${skipped}（格式错误）` : ""}`;
  setStatus(fail === 0 && skipped === 0 ? "ok" : (ok > 0 ? "warn" : "err"), tip);

  if (ok > 0) await loadProjects(project);
  submitBtn.disabled = false;
}

function bindHandlersImmediately() {
  // 点提交按钮 → 弹窗（不直接上传）
  $("#uploadForm").addEventListener("submit", (ev) => { ev.preventDefault(); openConfirmModal(); });
  submitBtn.addEventListener("click", (ev) => { ev.preventDefault(); openConfirmModal(); });

  // 弹窗按钮
  modalCancel.addEventListener("click", closeModal);
  modalConfirm.addEventListener("click", startUpload);
  modal.addEventListener("click", (ev) => {
    if (ev.target.classList.contains("modal-overlay")) closeModal();
  });

  [fileInput, projectInput, usernameInput].forEach((el) => {
    el.addEventListener("input", onFormInput);
    el.addEventListener("change", onFormInput);
  });
  $("#refreshDml").addEventListener("click", () => loadDml(projectSelect.value));
  projectSelect.addEventListener("change", () => loadDml(projectSelect.value));
}
bindHandlersImmediately();

document.addEventListener("DOMContentLoaded", async () => {
  await loadConfig();
  await loadProjects();
});
