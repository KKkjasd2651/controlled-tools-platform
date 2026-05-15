# 受控文件工具平台 · 使用手册 (SOP)

把工程师手里的图纸、规格书、计算书等技术文件，按 SBPC 受控规范**安全归档到工令文件服务器**，并自动维护 `文件清单.xlsx`（即 DML，Technical Document Master List）。

> **当前阶段**：核心上传与 DML 维护功能已完整通过本地测试。Seatable 钣金件清单同步与邮件通知模块代码已写好，**暂时注释停用**，后续运维就绪时取消注释即可启用。

---

## 目录

**Part A — 业务 SOP**

- [A1. 这个工具帮你做什么](#a1-这个工具帮你做什么)
- [A2. 涉及的角色](#a2-涉及的角色)
- [A3. 上传约定](#a3-上传约定)
- [A4. 完整业务流程图](#a4-完整业务流程图)
- [A5. 操作场景 ① 工程师：首次上传](#a5-操作场景--工程师首次上传)
- [A6. 操作场景 ② 工程师：升版本（同编码再上传）](#a6-操作场景--工程师升版本同编码再上传)
- [A7. 操作场景 ③ 查看工令资料](#a7-操作场景--查看工令资料)
- [A8. 操作场景 ④ 下载受控图纸](#a8-操作场景--下载受控图纸)
- [A9. 撤回 / 删除（特殊处理）](#a9-撤回--删除特殊处理)
- [A10. DML 两张表说明](#a10-dml-两张表说明)

**Part B — 技术 SOP**

- [B1. 首次安装](#b1-首次安装)
- [B2. 每次启动服务](#b2-每次启动服务)
- [B3. 关闭服务](#b3-关闭服务)
- [B4. 故障排查](#b4-故障排查)
- [B4.5 并发与扩容](#b45-并发与扩容)
- [B4.6 PDF 印章与加密策略](#b46-pdf-印章与加密策略)
- [B5. 启用 Seatable / 邮件（后续）](#b5-启用-seatable--邮件后续)
- [B6. 配置项总表](#b6-配置项总表)
- [B7. API 速查](#b7-api-速查)

**附录**

- [附录 C — 项目实施技术难点（领导汇报版）](#附录-c--项目实施技术难点领导汇报版)
- [附录 D — 代码结构与函数调用关系（精细到函数）](#附录-d--代码结构与函数调用关系精细到函数)
- [附录 E — 技术栈与架构选型解读](#附录-e--技术栈与架构选型解读)

---

# Part A — 业务 SOP

## A1. 这个工具帮你做什么

| 痛点 | 工具如何处理 |
|---|---|
| 文件名千奇百怪，不知道哪个是最新版 | 同名直接覆盖，DML 自动记录所有版本历史 |
| 找不到某文件历史版本 | 所有版本记录在该工令的 `文件清单.xlsx` Log 表 |
| DML 要手填，容易漏 | 自动维护：每次上传只追加 (日期/编码/版本) 三列，其余列由模板内公式自动算 |
| 担心文件被外传 | 上传时 PDF 自动加水印 + 128 位口令加密 |
| 受控状态混乱 | List 表"首版受控/末版受控"通过模板公式从 Log 反算，永远是事实 |

## A2. 涉及的角色

| 角色 | 干什么 |
|---|---|
| **工程师 / 设计师** | 在 WebUI 提交受控文件 |
| **审核人 / 项目经理** | 打开 WebUI 查看任意工令的受控履历、下载 DML |
| **其他人员**（钣金 / 采购 / 生产）| 从共享盘 / 后续邮件链接拿到最新图纸 |
| **平台维护者** | 装/启动平台、改配置 — 看 Part B |

## A3. 上传约定

### 文件名规范（强制）

```
<图号>_<版本> <图纸标题>.<后缀>
```

例：`D45H8-BF-03_A01 底横梁1-单页.pdf`
- **图号** = `D45H8-BF-03`
- **文件版本** = `A01`（A01/A02/B01… 直接来自文件名，**平台不自动递增**）
- **图纸标题** = `底横梁1-单页`

### 表单填写

**必填**：工令号、用户名（作者）、文件（**支持多选**）

### 落盘策略

- **落盘文件名 = 上传时的原文件名**（中文 / 空格都允许）
- **重名判定**：同名文件 → 直接覆盖；DML.Log 追加一条新版本记录
- **(图号, 图纸标题) 复合主键**：同图号不同标题 → DML.List 各起一行（不算同一份图）

### PDF 处理

- 上传 PDF 时**每页右下角**自动打一个蓝色圆角印章（"CONTROLLED" + "By <用户名> at <时间>"）
- 整个 PDF 用 128 位 AES 加密：**只允许打印**，禁止编辑/复制/注释/拼装/填表
- owner_password（解除限制用）由平台 32 字节随机生成存在 `.env`，对工程师不可见

详见 [B4.6 PDF 印章与加密策略](#b46-pdf-印章与加密策略)。

## A4. 完整业务流程图

```
┌─────────────┐   ① 选文件 + 填表单    ┌──────────────┐
│  工程师      │ ────────────────────▶ │   WebUI       │
│             │   ② 工令号 + 用户名    │ /ui/          │
└─────────────┘                       └──────┬───────┘
                                              │ POST /api/upload
                                       ┌──────▼────────┐
                                       │  FastAPI       │
                                       └──────┬─────────┘
                                              │
              ┌───────────────────────────────┼───────────────────────┐
              ▼                               ▼                       ▼
       ┌──────────────┐               ┌──────────────────┐    ┌──────────────┐
       │ 收元数据      │               │ PDF 水印+加密     │    │ 工令锁串行    │
       │ (编码/版本/   │               │ (受控文件)        │    │ DML 写入       │
       │  标题/上传人) │               └──────────────────┘    └──────┬───────┘
       └──────────────┘                                              │
                            ┌────────────────────────────────────────┘
                            ▼
                  ┌─────────────────────┐
                  │ 文件清单.xlsx        │
                  │ - Log 表追加新行     │ ──→ List 表 公式自动重算
                  └─────────────────────┘                "版本/末版受控"
```

## A5. 操作场景 ① 工程师：首次上传（一份或多份）

### 步骤

1. 浏览器打开 <http://localhost:8000/ui/>
2. 填工令号 + 用户名
3. 点 **[选择文件]** —— **可一次性选多份 PDF**
4. 表格自动渲染"批量解析"：每行显示 序号 / 原文件名 / 图号 / 文件版本 / 图纸标题 / 提交状态
   - 文件名**合规** → 状态显示"待上传"（灰色）
   - 文件名**不合规** → 状态显示"未提交 / 格式错误：版本号缺失"等（红色）
5. 点 **[提交]** → 弹出确认窗口：
   - 汇总：合规 X 个 / 不合规 Y 个
   - 不合规清单（详细原因）
   - 待上传清单（合规的）
6. 在弹窗里点 **[确认提交]** → 关闭弹窗 → 开始串行上传
   - 表格状态列实时刷新：上传中 → ✓ V*xxx* / 失败：xxx
   - 不合规文件**自动跳过**（不阻断其他文件）

### 预期结果

| 检查项 | 应该看到 |
|---|---|
| WebUI 状态条 | `完成：成功 N 失败 0` 或带跳过统计 |
| 工令文件夹 | 多出 `<工令号>\文件清单.xlsx`（首次自动创建）+ 所有合规 PDF（**已加印章和加密**） |
| 文件清单.xlsx 的 Log 表 | 每个上传新增一行：(日期, 文档编码, 版本, 文档标题, 完整文件名) |
| 文件清单.xlsx 的 List 表 | 命中预设 47 条 → 在对应行 update；非预设 → 自动 append 新行（公式自动复制） |

## A6. 操作场景 ② 工程师：升版本（同图升新版）

### 步骤

完全同 A5，**改用新版本号**重命名文件再上传。例：

- 旧：`D45H8-BF-03_A01 底横梁1-单页.pdf`
- 新：`D45H8-BF-03_A02 底横梁1-单页.pdf`（版本号 A01 → A02）

### 预期结果

| 检查项 | 应该看到 |
|---|---|
| WebUI 状态条 | `✓ V A02` |
| 工令文件夹 | 两个文件共存（A01 + A02），因为**原文件名不同** |
| 文件清单.xlsx 的 Log 表 | 新增一行 V A02 |
| 文件清单.xlsx 的 List 表 | 对应 (D45H8-BF-03, 底横梁1-单页) 行 update，**版本列自动变 A02**（LOOKUP "最后匹配"公式），末版受控更新为今天日期 |

> ⚠ **同名文件**（图号、版本、标题、扩展名都一样）才会触发"覆盖旧文件"。
> 版本号不同 → 算不同文件 → 共存。这是 SBPC 现场约定（保留所有版本历史）。
| 文件清单.xlsx 的 Log 表 | **新增一行**（旧版本那一行保留作为历史） |
| 文件清单.xlsx 的 List 表 | "末版受控"自动更新为今天日期，"版本"列自动变成新版本号 |

## A7. 操作场景 ③ 查看工令资料

WebUI 下半部分"工令资料 (DML · Log)"区块：

1. **下拉框**选工令号
2. **下载 文件清单.xlsx** 按钮：拿到完整 Excel（含所有公式）
3. 三张表实时展示：
   - **现存受控文件**：工令文件夹下实际存在的文件
   - **DML.Log 受控履历**：所有上传记录按时间顺序
   - **DML.List 应受控文档清单**：预设 47 项标准文档编码

## A8. 操作场景 ④ 下载受控图纸

三种方式拿文件：

1. **WebUI**：底部"工令资料 (DML · Log)" → 切到对应工令 → 点 **下载 文件清单.xlsx**；Excel 打开后 List 表 H 列每行都是可点击的链接，点开就是该图纸的最新版 PDF
2. **资源管理器**：直接访问 `\\sbpc-dc.com\sbpc\项目\ceshi\<工令号>\` 拿文件
3. **WebUI 表格里的"现存受控文件"** —— 列出该工令文件夹下所有文件

**打开 PDF**：当前**不需要任何口令**（user_password 留空）。打开后会看到右下角的蓝色 `CONTROLLED` 印章 + 上传人 + 时间。**编辑/复制/注释按钮置灰**（详见 [B4.6](#b46-pdf-印章与加密策略)）。

> 邮件自动通知功能代码已写好但暂时停用，启用后会自动给团队邮件组发上传摘要 + 下载链接。

## A9. 撤回 / 删除（特殊处理）

**平台不提供"撤回/删除"功能** —— 受控文件不能轻易消失。如确实需要：

| 需求 | 怎么做 |
|---|---|
| 撤回错误上传 | 立即上传**正确版本**（同编码新版本号）覆盖；错误版本仍在 Log 里 |
| 永久删除 | 联系平台维护者手动到共享目录删除该 PDF + 在 Log 表删对应行 |
| 整个工令作废 | 联系维护者，把 `<工令号>\` 整个文件夹移到归档区 |

## A10. DML 两张表说明

### List 表 — "该工令的受控文档"

由 SBPC 提供的 `TDML.xlsx` 模板预设 **47 项标准文档**，覆盖技术 / 结构 / 集成 / 电气等专业。**非预设编码**会自动 append 到表底部（公式自动复制）。

**唯一键 = (文档编码, 文档标题) 复合主键** —— 同图号不同标题各占一行。

| 列名 | 含义 | 数据来源 |
|---|---|---|
| 文档编码 | 完整编码 | 模板公式 `=$F$1&"-TE-SP-0001"` 自动从工令号拼出；非预设编码 append 时直接写字符串 |
| 文档标题 | 例如"技术规格书"、"结构总图"、"底横梁1-单页" | 上传时从文件名解析后写入 |
| 版本 | 最新版本号（如 A02、B01）| **LOOKUP 最后匹配**公式：按 (编码, 标题) 复合键找 Log 表最后一条记录的版本 |
| 首版受控 / 末版受控 | 受控日期 | 数组公式 `MIN/MAX(IF(复合键匹配, Log[日期]))`；格式 `yyyy/mm/dd` |
| 链接 | 跳转到该文档**真实文件名** | 公式：`=HYPERLINK($H$1 & LOOKUP(2, 1/((Log[编码]=...)*(Log[标题]=...)), Log[完整文件名]))` |
| 作者 | 上传人 | 平台从前端"用户名"字段写入 |
| 备注 / MKT/PUR/PDE/PMD/TQM | 业务字段 | 工程师手填（可选） |

### Log 表 — "每次上传都追加一行"

| 列名 | 含义 | 怎么填 |
|---|---|---|
| 日期 / 文档编码 / 版本 / 文档标题 / 完整文件名 | 实际入库元数据 | **平台自动写入字符串**（覆盖原模板里的反查公式）|
| C1 / C2 / 链接 / 创建文件夹 / 复制文件 | 派生信息 | 模板自动公式延伸 |

平台**写 5 列**（日期、编码、版本、标题、完整文件名）；其余 5 列由模板表格公式自动延伸 —— 这是为什么我们坚持用 TDML 模板而不是自己造表。

> **关键设计**：标题和完整文件名直接存字符串而不是公式 —— 让 List 表的 C / D / E / H 列能按 (编码, 标题) 精确反查，且 H 列链接能拼出真实文件路径（含 `_<版本> <标题>.pdf` 完整后缀）。

---

# Part B — 技术 SOP

## B1. 首次安装

### 前置条件

- Windows 10/11
- Python 3.10+（<https://www.python.org/downloads/>，勾选 "Add to PATH"）
- 当前 Windows 账号能访问 `\\sbpc-dc.com\sbpc\项目\ceshi`

### 装依赖

打开 **Windows PowerShell** 运行：

```powershell
cd C:\Users\longkang.lin\Desktop\受控工具平台\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

> `Activate.ps1` 报"禁止运行脚本"时执行一次：
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```

### 检查 .env

确认 `backend\.env` 内容：

```ini
FILE_SERVER_ROOT=\\sbpc-dc.com\sbpc\项目\ceshi
DML_FILENAME=文件清单.xlsx
CONTROLLED_DIR=
REQUIRE_WRITABLE_FS=true
APP_PORT=8000
```

### 确认模板

`backend\templates\DML_template.xlsx` 存在（SBPC 的 TDML.xlsx）。

## B2. 每次启动服务

### ⚠ 必做的前置步骤：先访问一次 SMB 共享

**重启电脑后第一次启动前必做**：在文件资源管理器地址栏粘贴 `\\sbpc-dc.com\sbpc\项目\ceshi` 回车，确认能看到工令号文件夹。

> 这步让 Windows 把 SMB 会话凭据缓存到 LSA，后面 Python 子进程才能复用。
> 跳过 → 启动时卡 8 秒后报"SMB 路径无响应"。

### 启动命令

**Windows PowerShell**（不是 cmd / 不是 IDE 集成终端 / 不要双击 BAT）：

```powershell
cd C:\Users\longkang.lin\Desktop\受控工具平台\backend
.\.venv\Scripts\Activate.ps1
python -u -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 成功标志

```
[startup] FILE_SERVER_ROOT = \\sbpc-dc.com\sbpc\项目\ceshi
[startup] REQUIRE_WRITABLE_FS = True
[startup] 开始自检文件服务器可写性 (最长 8 秒) ...
[startup] [OK] 文件服务器可读写: \\sbpc-dc.com\sbpc\项目\ceshi
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

浏览器访问 <http://localhost:8000/ui/>，顶栏右上应显示 `📁 \\sbpc-dc.com\sbpc\项目\ceshi`。

启动窗口必须保持打开，关掉服务就停。

## B3. 关闭服务

PowerShell 窗口按 **Ctrl + C**。

## B4. 故障排查

### 🔴 `RuntimeError: 自检超时 (8s) — SMB 路径 ... 无响应`

当前 PowerShell 进程没有该 SMB 共享的凭据。  
**修复**：文件资源管理器访问一次 `\\sbpc-dc.com\sbpc\项目\ceshi` → 回到**同一个** PowerShell 窗口（不要新开）重新启动。

### 🔴 `OSError: [WinError 64] 指定的网络名不再可用`

同上，SMB 凭据问题。

### 🔴 `无法将"run"项识别为 cmdlet`

PowerShell 安全策略问题。改用 `.\run.bat`，或直接双击。  
（但优先用桌面 PowerShell 启动方式，更稳。）

### 🔴 端口 8000 被占用

```powershell
netstat -ano | findstr ":8000 " | findstr "LISTENING"
taskkill /F /PID <显示的 PID>
```

或改 `.env` 里 `APP_PORT=8001`。

### 🔴 上传时 502 `写入文件服务器失败`

SMB 会话失效。Ctrl+C 停服务 → 资源管理器再访问一次共享 → 重启 uvicorn。

### 🔴 上传时 409 `DML 写入失败 (可能 Excel 占用)`

某用户在 Excel 里打开了 `文件清单.xlsx`。让他关闭后重试。

### 🔴 浏览器 `ERR_CONNECTION_REFUSED`

uvicorn 没起来。看 PowerShell 终端错误信息。

### 🟡 完全本地演示（脱网测试）

```ini
# backend\.env
FILE_SERVER_ROOT=./fileserver
```

文件落到 `backend\fileserver\<工令号>\`，不依赖 SBPC 共享。

### 🟡 临时绕过 SMB 自检

```ini
REQUIRE_WRITABLE_FS=false
```

跳过启动自检，但上传时仍可能 502。仅诊断用。

## B4.5 并发与扩容

### 当前并发能力

平台跑在 **单 uvicorn worker + 1 个 event loop + 40 线程的 threadpool**：

| 场景 | 行为 |
|---|---|
| 不同工令的多人并发上传 | **完全并行** |
| 同一工令的多人并发上传 | **自动串行**（每工令一把锁，DML 不会丢更新） |
| 多人并发刷新页面 | 完全并行 |

并发冒烟测试（5 个上传同时打到同一工令）实测：**5 个全部成功，Log 行号 2/3/4/5/6 各占一行，零丢更新**。

### 原理

- **每工令一把 `asyncio.Lock`**（`app/concurrency.py`），保护"读 DML → 找空行 → 写 DML"
- **所有 SMB / openpyxl / PDF 加密**都包在 `asyncio.to_thread`，event loop 不被阻塞
- 每个请求带 **`X-Request-ID`**，方便高并发下排查

### 扩容路线

| 阶段 | 改动 | 容量 |
|---|---|---|
| **当前** | 单 uvicorn worker | 约 30–40 个不同工令并发；同工令串行 |
| **多 worker** | `uvicorn --workers 4` + `filelock` 跨进程锁 | 容量 × worker 数 |
| **任务队列** | 用户提交即返回；后台 worker 处理 | 几乎无上限 |
| **DB 托管** | DML 数据主存放 Postgres，xlsx 仅作快照导出 | 上千并发 |

## B4.6 PDF 印章与加密策略

上传 PDF 时，平台对每页做两件事：

### 1. 右下角打蓝色印章

```
┌────────────────────────────────┐
│      CONTROLLED                │  ← 大字（由 .env 的 WATERMARK_TEXT 控制）
│  By 林龙康 at 16:04:28, 2026-05-14 │  ← 小字（自动填上传人 + 时间）
└────────────────────────────────┘
   65×22mm 圆角矩形双线边框 / 蓝紫色 / 整体 50% 透明
```

- 中文字体：自动注册 `msyhbd.ttc` (微软雅黑 Bold)；缺失时回退黑体 / 宋体 / Helvetica
- 实现：`backend/app/services/pdf_security.py` 的 `_build_stamp_pdf()` 用 reportlab 画戳，再 pypdf merge 到每页

### 2. 128-bit 加密 + 权限位

| 操作 | 是否允许 |
|---|---|
| 打开 PDF（不输口令） | ✅ 允许 |
| 打印 / 高质量打印 | ✅ 允许 |
| 编辑文档内容 | ❌ 禁止 |
| 复制文字 / 选择文本 | ❌ 禁止 |
| 添加注释 / 高亮 / 签名 | ❌ 禁止 |
| 插页 / 旋转 / 删页 | ❌ 禁止 |
| 填表单 | ❌ 禁止 |
| 屏幕阅读器辅助 | ❌ 禁止（连带禁了文本提取） |

权限位（`permissions_flag`）= `PRINT (4) | PRINT_TO_REPRESENTATION (2048) = 2052`

### 3. 口令策略

| 口令字段 | 含义 | 当前值 |
|---|---|---|
| `PDF_USER_PASSWORD` | 打开 PDF 需要的口令 | **空** —— 任何人都能打开查看 |
| `PDF_OWNER_PASSWORD` | 解除"禁止编辑"限制需要的口令 | **32 字节随机串**，存在 `backend/.env` 中 |

⚠ **owner_password 必须保密**。它存在 `.env` 文件里，`.gitignore` 已排除该文件不入 Git。

#### 如果需要换 owner_password

```powershell
# 生成新的随机口令
python -c "import secrets; print(secrets.token_urlsafe(32))"
# 把输出粘贴到 .env 里 PDF_OWNER_PASSWORD= 后面，重启 uvicorn
```

> 注意：**已上传的 PDF 仍用旧 owner_password**（加密参数已嵌入到 PDF 内）；只对之后上传的生效。建议把旧 owner_password 保留备查。

#### 如果想让"打开 PDF 也需要口令"

`.env` 改：

```ini
PDF_USER_PASSWORD=您要给团队的统一口令
```

重启 uvicorn 即可。打开时阅读器会提示输入此口令。

### 4. 实际效果（Adobe Acrobat / Nitro）

在 Acrobat：菜单 → 文件 → 属性 → 安全性 标签页 应显示：

```
安全性方法： 口令保护
                                打开文档: 不需要口令
打印:        允许
更改文档:    不允许
文档拼装:    不允许
内容复制:    不允许
辅助工具复制:不允许
表单填充:    不允许
签名:        不允许
模板页面创建:不允许
```

如果工程师误操作（例如想编辑），Acrobat 会弹出"此命令受文档限制保护，需要 owner_password"。

---

## B5. 启用 Seatable / 邮件（后续）

代码已写好但默认停用。启用步骤：

### 1. 取消 `backend/app/main.py` 里的注释

搜两段 `=== Seatable` 和 `=== 邮件通知` —— 取消三处注释：

| 位置 | 注释内容 |
|---|---|
| 顶部 `from .services.notifier import Notifier` / `from .services.seatable_client import SeatableClient` |
| 全局实例化 `seatable = SeatableClient(...)` / `notifier = Notifier(...)` |
| upload() 里的 `await asyncio.to_thread(seatable.upsert_sheet_metal_row, record)` + `await asyncio.to_thread(notifier.send_upload_notice, ...)` |

### 2. 在 `backend/.env` 加上真实配置（去掉 `#`）

```ini
# Seatable
SEATABLE_SERVER_URL=https://cloud.seatable.io
SEATABLE_API_TOKEN=<您的 Seatable API Token>
SEATABLE_TABLE_NAME=钣金件清单

# SMTP（示例：腾讯企业邮箱 SSL）
SMTP_HOST=smtp.exmail.qq.com
SMTP_PORT=465
SMTP_USE_SSL=true
SMTP_USER=noreply@sbpc.com
SMTP_PASSWORD=<授权码>
MAIL_FROM=noreply@sbpc.com
MAIL_TO=engineering@sbpc.com,boss@sbpc.com
```

### 3. 重启 uvicorn 即生效

## B6. 配置项总表

| 配置项 | 含义 | 默认 |
|---|---|---|
| `FILE_SERVER_ROOT` | 工令服务器根目录（UNC 或本地路径） | `\\sbpc-dc.com\sbpc\项目\ceshi` |
| `DML_TEMPLATE` | TDML 模板路径 | `./templates/DML_template.xlsx` |
| `DML_FILENAME` | DML 文件名 | `文件清单.xlsx` |
| `CONTROLLED_DIR` | 受控文件子目录；留空 = 平铺工令根 | 空 |
| `REQUIRE_WRITABLE_FS` | 启动期是否自检 | `true` |
| `FILENAME_REGEX` | 文件名正则（备用；当前强制 `<图号>_<版本> <标题>.<ext>` 由 `parse_filename()` 实现） | TDML 风格 |
| `PDF_OWNER_PASSWORD` | PDF 加密 owner 口令（解除"禁止编辑"用，必须保密）。**已用 `secrets.token_urlsafe(32)` 生成** | 32 字节随机串 |
| `PDF_USER_PASSWORD` | PDF 加密 user 口令（留空 = 任何人都能打开） | 空 |
| `WATERMARK_TEXT` | PDF 印章大字 | `CONTROLLED` |
| `APP_HOST` / `APP_PORT` | 监听 | `0.0.0.0:8000` |
| `PUBLIC_BASE_URL` | 生成下载链接的基地址 | `http://localhost:8000` |
| `SEATABLE_*` | Seatable 凭据（当前停用） | 空 |
| `SMTP_*` / `MAIL_*` | 邮件凭据（当前停用） | 空 |

### 生成 / 更换 PDF owner_password

```powershell
# 在 backend 目录下
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
# 把输出粘贴到 .env 里 PDF_OWNER_PASSWORD= 后面，重启 uvicorn
```

详见 [B4.6 PDF 印章与加密策略](#b46-pdf-印章与加密策略)。

## B7. API 速查

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET  | `/api/health`   | 健康检查（含 `fs_root` 和 `concurrency` 锁状态） |
| GET  | `/api/config`   | 前端用配置 |
| POST | `/api/validate` | 仅校验文件名（备用） |
| POST | `/api/upload`   | 主上传；form: `file` + `project` + `username` + 可选 `code/version/title` |
| GET  | `/api/projects` | 列已建过 DML 的工令号 |
| GET  | `/api/dml?project=260455` | 该工令的 codes/log/files + DML 下载链接 |
| GET  | `/files/...`    | 文件服务器静态下载 |

---

# 附录 C — 项目实施技术难点（领导汇报版）

> 面向**不写代码的同事和领导**。所有问题用日常比喻。

## 一、项目本身的复杂度（天然存在）

### 难点 1：DML 不是普通表格

**比喻**：DML 像一本带"自动计算"的会计账本 —— 47 行预设条目，每行的"末版受控/版本/链接"都靠**几十个隐藏公式**自动算。程序必须能**只动其中几个格子**而不破坏其他公式。

**解决**：严格使用 SBPC 原始 TDML 模板做底座，首次上传时复制模板，之后**只追加 Log 表**。实测 30+ 次读写公式仍完好。

### 难点 2：图纸命名规范几次反复

| 阶段 | 规则 | 为什么改 |
|---|---|---|
| v1（最初）| 强制正则 `编码-标题-V版本-作者-项目号.pdf` | 我自己设计 |
| v2 | `<编码>_V<版本> <标题>.pdf` 落盘改名 `<编码>.<ext>` | 按 SBPC TDML 模板推导 |
| **v3（最终）** | **不强制文件名**，表单填编码/版本/标题（可空），按**原文件名落盘 + 同名覆盖** | 您要求"图纸命名规则统一，只需判重名" |

## 二、SBPC 文件服务器的"权限玄学"（耗时 70%）

### 难点 3：SMB 凭据"按楼层发"

**比喻**：访问 `\\sbpc-dc.com\sbpc\项目\ceshi` 像刷工牌进 SBPC 大楼。工牌按"楼层"发，不是按"人"：
- 桌面 → PowerShell → Python：**同一张工牌，能进** ✅
- 双击 BAT → cmd → Python：cmd 是"新到访的"，门禁系统（Zscaler/SASE）不给办新卡，**进不去** ❌

**解决**：强制约定**用桌面 PowerShell 启动**。

### 难点 4：八秒钟卡死

Python 程序去查"能不能写共享"时如果没工牌，Windows 会等门禁系统响应，但**门禁不会拒绝也不会通过**。  
**解决**：给可写性自检加 **8 秒超时** + 提供 `REQUIRE_WRITABLE_FS=false` 紧急绕过。

### 难点 5：现有"文件清单.xlsx"不兼容

SBPC 共享上已经有一个 13KB 的 `文件清单.xlsx`，但**不是 TDML 格式**。  
**解决**：检测到不兼容时**自动改名为 `文件清单_备份_<时间戳>.xlsx`**，再用 TDML 模板复制新的。

### 难点 6：Excel 锁文件

工程师在 Excel 里打开 DML 时，任何其他程序都写不进去（WinError 32）。  
**解决**：清晰错误提示 + a→b→c→d 处理步骤（关 Excel → 关 Explorer → 重启 explorer.exe → 重启电脑）。

## 三、Windows 古老坑（一次性修过）

### 难点 7：BAT 行尾问题

cmd 解析 LF（Unix）行尾的 BAT 时，会**吃掉每行前 1-2 个字符**：`echo` 变 `ho`、`set` 变 `t`、`cd` 直接消失。  
**解决**：强制 CRLF 行尾 + 纯 ASCII。

### 难点 8：中文路径 + 中文 Windows 的编码内战

GBK vs UTF-8 不一致导致：BAT 中读 `.env` 显示乱码；PowerShell 5 读含中文 ps1 解析失败。  
**解决**：所有脚本纯英文 ASCII；Python 内部全程 UTF-8（`PYTHONIOENCODING=utf-8`）。

## 四、并发与高负载

### 难点 9：200 人同时使用怎么办

**比喻**：DML.xlsx 像**一本物理账本**，多个人同时翻到同一页写字会互相涂掉。  
**解决**：每工令一把锁（同工令串行，不同工令并行）。本地实测 5 并发零丢更新。

### 难点 10：外部服务卡住整个系统

把外部调用（Seatable / 邮件）放进**单独的工作线程池**，主流程不受影响。

## 五、给领导的关键结论

### ✅ 当前可用范围

| 维度 | 现状 |
|---|---|
| **功能完整度** | 上传 + 加密水印 + DML 维护全链路通；Seatable / 邮件代码就绪、暂停用 |
| **并发能力** | 30–40 个工令同时操作 OK；200 人散到不同工令完全没问题 |
| **稳定性** | 所有异常路径都有清晰报错 + 兜底 |
| **运行方式** | 当前需专人用桌面 PowerShell 启动 |

### ⚠ 三件用户教育的事

| 必须做到 | 否则会 |
|---|---|
| **启动前先在 Explorer 访问一次 SBPC 共享** | 启动 8 秒后报错 |
| **上传时不要在 Excel 打开 DML** | 上传返回 409 错误 |
| **不要用 cmd / 双击 bat 启动平台** | 90% 概率 SMB 不通 |

### 🚀 接下来三阶段扩容路线

| 阶段 | 投入 | 容量 | 规模 |
|---|---|---|---|
| **当前** | 一台机器 + 桌面 PowerShell | 30–40 工令并发 | 工程部 30–50 人 |
| **生产部署** | Windows 服务 + 域账号自动连接共享 | 同上但 24×7 可用 | 工程部 50–200 人 |
| **架构升级** | 任务队列 + Postgres 主存储 | 1000+ 并发 | 集团多工厂 |

### 💰 后续维护工作量预估

- **小修改**（加字段 / 调界面 / 改邮件模板）：< 1 人日
- **接入新工厂 / 新文件服务器**：1–2 人日
- **生产部署**：2–3 人日
- **架构升级**：2–3 人周

---

# 附录 D — 代码结构与函数调用关系（精细到函数）

## D.1 全景图：一次上传发生了什么

```
┌─ 工程师电脑（浏览器）─────────────────────────────────────┐
│  index.html (UI 骨架)                                  │
│      └─ app.js                                          │
│           ├─ validateForm()   实时检查必填项              │
│           ├─ handleSubmit()   提交时触发                  │
│           └─ loadDml()        刷新工令资料表格             │
└──────────────────────┬─────────────────────────────────┘
                       │ POST /api/upload (multipart)
                       ▼
┌─ FastAPI 服务（Python 进程）──────────────────────────────┐
│  main.py upload()                                       │
│      ├─[1] await pdf_security.protect_file()           │
│      │                                                  │
│      ├─[2] async with concurrency.project_lock(prj):   │
│      │       ├─ dml.ensure_project_dml()  首次复制 TDML │
│      │       ├─ dml.list_codes()                       │
│      │       ├─ storage.write_with_name()  落盘 SMB     │
│      │       └─ dml.append_log_entry()    DML.Log 追加  │
│      │                                                  │
│      └─ [3/4] Seatable + 邮件（当前注释停用）             │
└──────────────────────┬─────────────────────────────────┘
                       │ HTTP 200 + JSON
                       ▼
                  SBPC SMB 共享：
        \\sbpc-dc.com\sbpc\项目\ceshi\<工令号>\
            ├─ 文件清单.xlsx
            └─ <原文件名>.pdf  (加密+水印)
```

## D.2 文件结构详解

### 顶层

| 文件 | 作用 |
|---|---|
| `README.md` | 本文档 |
| `run.bat` | Windows 双击启动（备用，推荐 PowerShell） |
| `check.bat` | 环境诊断（只读） |
| `start.ps1` | PowerShell 启动器 |

### `backend/`

| 文件 / 目录 | 作用 |
|---|---|
| `.env` | 运行配置 |
| `.env.example` | 配置模板 |
| `requirements.txt` | Python 依赖 |
| `run_uvicorn.ps1` | run.bat 调用的 PS 中转启动器；预热 SMB |
| `templates/DML_template.xlsx` | **核心**：SBPC TDML 模板 |
| `app/main.py` | FastAPI 入口；所有 `/api/*` 端点 |
| `app/config.py` | pydantic-settings 配置加载 |
| `app/concurrency.py` | 每工令 asyncio.Lock |
| `app/schemas.py` | Pydantic 响应模型 |
| `app/services/filename.py` | 文件名正则解析（备用） |
| `app/services/pdf_security.py` | PDF 水印 + 128 位加密 |
| `app/services/storage.py` | SMB 文件读写抽象 |
| `app/services/dml.py` | DML.xlsx 维护 |
| `app/services/seatable_client.py` | Seatable upsert（**当前停用**） |
| `app/services/notifier.py` | SMTP 邮件（**当前停用**） |

### `frontend/`

| 文件 | 作用 |
|---|---|
| `index.html` | UI 骨架 |
| `app.js` | 原生 JS 交互逻辑 |
| `style.css` | 样式 |

## D.3 文件间调用矩阵

| 调用方 ↓ | main | config | concur | dml | storage | pdf_sec | seatable | notifier |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **main.py** | | ● | ● | ● | ● | ● | (停) | (停) |
| 所有 service 之间 | | | | 无 | 无 | 无 | 无 | 无 |

**关键观察**：所有 service 模块**只被 main.py 调用**，service 之间零交叉依赖。任意一个 service 可以独立替换不影响其他模块（例如把 `seatable_client.py` 换成"钉钉机器人"只改 main.py 两行）。

## D.4 一次上传的函数级时序

```
T+0ms  app.js handleSubmit()           读表单 → fetch POST
T+2    main.request_id_middleware       生成 8 字符请求 ID
T+3    main.upload() 开始               读 file / project / username / ...
T+5    file.read()                     读上传字节
T+10   asyncio.to_thread(protect_file) 线程池跑 PDF 加水印+加密
T+200  返回 protected_bytes

T+201  async with project_lock("260455"): ← 进锁
T+202  ensure_project_dml()             首次复制 TDML 模板
T+300  返回 dml_path

T+301  list_codes(dml)                  读 List 表 47 编码
T+400  返回 declared

T+401  storage.write_with_name()        删旧 + 写 SMB
T+700  返回 saved_path

T+701  dml.append_log_entry()           Log 表写一行 (日期/编码/版本)
T+1000 返回 row 号

T+1001 释放工令锁
T+1002 [Seatable - 当前停用]
T+1003 [邮件 - 当前停用]
T+1010 main.upload() 返回 JSON
```

**总耗时**：通常 ~1 秒。

## D.5 修改指引（给后续维护者）

| 想做的事 | 改哪 |
|---|---|
| 加表单字段（如"密级"） | `frontend/index.html` 加 input + `app.js` handleSubmit append + `main.py upload()` 加 `Form()` 参数 |
| 启用 Seatable / 邮件 | 见 [B5. 启用 Seatable / 邮件](#b5-启用-seatable--邮件后续) |
| 改 PDF 水印 / 加密口令 | `.env` 改 `WATERMARK_TEXT` / `PDF_OWNER_PASSWORD` |
| 接钉钉机器人 | 新建 `services/dingtalk.py` 抄 `notifier.py` 结构，main.py 引入并调用 |
| 加权限校验（登录） | `main.py` 加 FastAPI dependency 或 middleware |
| 多 worker 部署 | `concurrency.py` 的 `asyncio.Lock` 换 `filelock.FileLock` 给 DML 文件加跨进程锁 |

---

# 附录 E — 技术栈与架构选型解读

## E.1 整体形态：为什么是"浏览器 + 服务器"？

| 方案 | 为什么没选 |
|---|---|
| Excel VBA / 宏 | 每台电脑要单独装，并发会撞车 |
| 桌面客户端 | 部署成本高、改版本要重新分发 |
| **Web 应用 ✅** | **零安装，浏览器访问；改后端立即生效** |
| 公网 SaaS | 受控文件不能跑公网 |

## E.2 网络与文件层

### SMB = Server Message Block

**Windows 系统自 1990 年代内置的"文件共享协议"**。`\\sbpc-dc.com\sbpc\项目\ceshi` 共享盘背后就是 SMB。

| 概念 | 解释 |
|---|---|
| SMB 端口 445 | 防火墙必须放行 |
| SMB 凭据 | Windows 登录时拿到的"工牌"，访问共享时自动出示 |
| SMB 锁 | Excel 等程序打开文件时给文件加锁，别人不能改（WinError 32 来源） |

### UNC 路径

`\\服务器\共享名\子目录\文件`。本地是 `C:\`，网络共享是 `\\...`。

### Zscaler / SASE

零信任安全代理。让所有网络流量都先去 Zscaler 云端绕一圈鉴权再放行。SBPC 这台机器装了 Zscaler，导致**双击 BAT 启动的 cmd 子进程没法访问 SMB**（只有桌面 PowerShell 行）。

## E.3 后端用了什么

| 组件 | 是什么 | 为什么用 |
|---|---|---|
| **Python 3.10+** | 编程语言 | 写起来快、生态强、跨平台 |
| **FastAPI** | Python Web 框架 | 自带异步、文档、类型校验 |
| **uvicorn** | ASGI 服务器（"运行引擎"） | 跑 FastAPI 用的 |
| **asyncio** | 异步框架 | 让 30 人并发只占一份资源 |
| **openpyxl** | Excel 读写库 | 能保留 DML 复杂公式 |
| **pypdf + reportlab** | PDF 读写 + 生成 | PDF 加密 + 水印页 |
| **pydantic-settings** | 配置加载 | 把 `.env` 自动转 Python 对象 |
| **seatable-api**（停用）| Seatable SDK | 接 SBPC 钣金件清单 |
| **smtplib**（停用）| Python 内置 SMTP | 邮件通知 |

## E.4 前端用了什么

**HTML5 + CSS3 + 原生 JavaScript + Fetch API**，**无任何框架**。

为什么不用 React / Vue：
- 这个项目只有一个上传页 + 几个表格，杀鸡用牛刀
- 原生 JS 200 行就够；任何工程师打开能看懂
- 不引入构建链，部署零成本

## E.5 关键架构模式

| 模式 | 比喻 |
|---|---|
| **前后端分离** | 前端管"长啥样"，后端管"做啥事"，HTTP+JSON 通讯 |
| **RESTful API** | 用 HTTP 动词约定行为：GET 看 / POST 创建 |
| **单 worker + asyncio.Lock** | 一个收银员，不同工令并行，同工令排队 |
| **配置外置（.env）**| 凭据不混入代码仓库 |
| **线程池（threadpool）**| 大堂经理只接客，洗碗派给 40 个服务员 |

## E.6 架构图：技术栈各管哪一块

```
┌─ 工程师电脑（浏览器）──────────────────┐
│  HTML5 + CSS3 + 原生 JS + Fetch API   │
│  PowerShell（启动用）                   │
└──────────────┬───────────────────────┘
               │ HTTP + JSON
┌──────────────▼ Python 服务进程 ────────────┐
│  uvicorn ← HTTP 服务器                     │
│  FastAPI ← Web 框架                        │
│      ├ pydantic-settings ← 读 .env         │
│      ├ asyncio (event loop)               │
│      │    ├ asyncio.Lock ← 同工令串行       │
│      │    └ asyncio.to_thread → threadpool│
│      ├ openpyxl    ← DML.xlsx              │
│      ├ pypdf       ← PDF 加密              │
│      ├ reportlab   ← 水印页                 │
│      ├ seatable-api（停用）                 │
│      └ smtplib（停用）                      │
└──────────────┬───────────────────────────┘
       ┌───────┼───────────────┐
       ▼ SMB   ▼ HTTPS         ▼ SMTP
   SBPC共享  Seatable        企业邮箱
   (启用)   (代码就绪/停用)  (代码就绪/停用)
```

## E.7 关键术语速查表

| 术语 | 一句话 |
|---|---|
| **SMB** | Windows 文件共享协议 |
| **UNC** | `\\server\share` 形式的网络路径 |
| **HTTP / REST API / JSON** | 前后端对话约定 |
| **Zscaler / SASE** | 零信任安全代理 |
| **Python 虚拟环境 (.venv)** | 项目独立的 Python 环境 |
| **pip / PyPI / 清华镜像** | Python 包管理 / 仓库 / 国内加速 |
| **FastAPI / uvicorn / asyncio** | Python Web 三件套 |
| **Event Loop / threadpool / Lock** | 并发三要素 |
| **openpyxl / pypdf / reportlab** | Excel/PDF 处理库 |
| **pydantic / .env** | 配置 & 数据校验 |
| **CRLF / LF / ASCII / UTF-8 / GBK** | 编码相关 |
| **WinError 32 / 64** | "文件被占" / "网络名不可用" |

## E.8 项目交付物

| 类别 | 大小 |
|---|---|
| 后端代码（8 个 .py） | ~30 KB |
| 前端代码（HTML/JS/CSS） | ~14 KB |
| 配置 / 模板 | ~30 KB |
| 启动脚本 | ~10 KB |
| 文档（本 README） | ~80 KB |
| 第三方包 | ~80 MB |

总代码 ~2000 行 (Python + JS + HTML + CSS)，文档 ~3000 行。
