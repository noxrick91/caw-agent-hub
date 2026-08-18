# caw-agent 使用手册

caw-agent 是跑在你终端里的编程助手：读代码、改文件、跑测试，都在你打开的这个项目里完成。每次写盘或执行命令前，它会停下来等你确认。界面提供权限经纪、沙箱、MCP、会话与记忆。

预编译包从本站 [GitHub Releases](https://github.com/noxrick91/caw-agent-hub/releases) 装到 `~/.caw-agent/bin`。源码仓私有，不对外。

### 它做什么

- 只碰你打开的工作区；读、改、跑的每一步都显示在终端里
- 写文件和跑命令默认先征求同意，权限可以按项目收紧或放宽
- 记住跨会话的项目习惯；需要时接 MCP 服务器和技能
- 官方 API、本地 Ollama，以及第三方 OpenAI 兼容中转，都可以用

### 模型从哪来

官方供应商用 `/model add <预设>`，例如 `openai`、`anthropic`、`deepseek`、`qwen`。本地模型用 `/model add ollama`，不需要云端密钥。

中转站（NewAPI、OneAPI 等「OpenAI 兼容」网关）**不要改官方预设的地址**。单独加一个供应商，用控制台里的 Base URL、密钥和模型名。步骤见 [模型与密钥](#/models)。

### 怎么读这份手册

从 [安装](#/install) 和 [快速开始](#/quick-start) 上手。斜杠命令、权限、会话、MCP 在后面几章。右上角 **中文 / EN** 切换整本手册；换语言会停在同一页。

---

## What's new

This page lists changes in the **current public release**.

**What's new in v0.1.13** — 2026-08-18

- Added native Windows ARM64 release builds, installers, self-upgrades, and website downloads alongside Linux x86_64/ARM64 and Windows x86_64.
- Removed unavailable macOS binaries from the public download matrix while retaining source-level macOS support.

Full history: [CHANGELOG.md](./CHANGELOG.md).

## 安装

### 一键安装

Linux / macOS / Git Bash：

```bash
curl -fsS https://agent.noxcaw.com/install | bash
```

指定版本：

```bash
curl -fsS https://agent.noxcaw.com/install | bash -s -- v0.1.1
# 或
CAW_TAG=v0.1.1 curl -fsS https://agent.noxcaw.com/install | bash
```

Windows PowerShell：

```powershell
irm https://agent.noxcaw.com/install.txt | iex
```

不要用 `irm …/install.ps1`：GitHub Pages 把 `.ps1` 标成 `application/octet-stream`，Windows PowerShell 5.1 的 `irm` 读不成脚本。`.txt` 是 `text/plain`。若必须拉 `.ps1`：

```powershell
iex ((New-Object Net.WebClient).DownloadString('https://agent.noxcaw.com/install.ps1'))
```

脚本按本机 OS/ARCH 选择资产（Linux x64/arm64、Windows x64/ARM64），下载后核对同 Release 的 `SHA256SUMS`，装到 `~/.caw-agent/bin`。Windows ARM64 优先安装原生版本；旧版 Release 没有 ARM64 资产时回退到 x64 系统模拟。macOS 预编译包暂不提供。再跑一次安装器会重新下载并覆盖当前文件（Windows 先把正在用的 exe 改名为 `.bak` 再写入新文件）。安装脚本会写入 `~/.caw-agent/env`，并在 `.bashrc` / `.zshrc` / `.bash_profile` / fish `config.fish` 里加上 hook，然后 `source` 该 env。`curl | bash` 改不了你当前已经打开的 shell，新开终端即可，或执行 `source ~/.caw-agent/env`。不想改 rc 时设 `CAW_NO_PATH=1`。

Pages 尚未生效时可用：

```bash
curl -fsS https://raw.githubusercontent.com/noxrick91/caw-agent-hub/master/install | bash
```

```powershell
irm https://raw.githubusercontent.com/noxrick91/caw-agent-hub/master/install.ps1 | iex
```

### 官网 / 手动下载

打开本站首页，按平台下载最新资产，放到 `~/.caw-agent/bin`（Windows 为 `%USERPROFILE%\.caw-agent\bin\caw-agent.exe`），并对照 `SHA256SUMS`。首页表格的「本版 / 累计」来自 GitHub Release 每个资产的 `download_count`：一键安装、`caw-agent upgrade`、浏览器手动下载都会加一。拉 Pages 上的 `install` 脚本本身不计入；`SHA256SUMS` 单独计数（每次安装会先下校验文件）。`upgrade --check` 只打 API，不增加下载量。

| 平台 | 资产 |
|------|------|
| Linux x86_64 | `caw-agent-x86_64-unknown-linux-gnu` |
| Linux aarch64 | `caw-agent-aarch64-unknown-linux-gnu` |
| Windows x64 | `caw-agent-x86_64-pc-windows-gnu.exe` |
| Windows ARM64 | `caw-agent-aarch64-pc-windows-msvc.exe` |

不支持的组合（如 Linux musl、32 位 Windows）没有预编译包，需从源码构建。

### 已安装后升级

空命令**只检查**，不下载：

```text
/upgrade
caw-agent upgrade
caw-agent upgrade --check
```

安装最新版（仅当比当前新）：

```text
/upgrade now
caw-agent upgrade now
```

指定标签（可装旧版）：

```text
/upgrade v0.1.1
caw-agent upgrade v0.1.1
```

下载时显示字节与百分比；校验 SHA256；装完跑 `--version`，对不上会恢复 `.bak`。默认读公开仓 `noxrick91/caw-agent-hub`。可用 `CAW_GITHUB=owner/name` 覆盖。

Windows 会先把正在运行的 `caw-agent.exe` 改名为 `.bak` 再写入新文件。若改名失败，再旁路写入并提示关掉所有窗口。装完请新开终端，用 `caw-agent --version` 确认；若 PATH 上还有另一份旧程序，以 `%USERPROFILE%\.caw-agent\bin\caw-agent.exe` 为准。

### 卸载

没有单独的卸载器。删掉安装目录即可，配置、密钥和 MCP 包会一起去掉：

```bash
rm -rf ~/.caw-agent
```

```powershell
Remove-Item -Recurse -Force $HOME\.caw-agent
```

再手工清 PATH：Linux / macOS 删掉 `.bashrc` / `.zshrc` / `.bash_profile` / fish `config.fish` 里 `# >>> caw-agent >>>` 到 `# <<< caw-agent <<<` 那几行；Windows 从用户 PATH 去掉 `%USERPROFILE%\.caw-agent\bin`。项目目录里的 `.caw-agent/` 不会动。

### 从源码安装

源码仓不公开。有权限的开发者在私有 `caw-agent` 仓库里：

```bash
./scripts/install.sh          # cargo install → ~/.caw-agent/bin
cargo run -p caw-agent -- --workdir .
```

**Linux 编译依赖：** `pkg-config`、`libxcb1-dev`、`libxrandr-dev`（X11 截图）。Wayland 截图优先 `grim`；computer-use 优先 `ydotool`。

**Windows：** 需要 MSVC。原生 Windows **没有** exec OS jail，沙箱 `run` 请用 WSL2。

**macOS：** 截图 / computer-use 需要屏幕录制与辅助功能；推荐 `cliclick`。

---

## 快速开始

```bash
caw-agent --workdir .
# 简写
caw-agent -w .
```

首次进入未完成引导的工作区会打开向导：选主题，确认工作区。之后可用 `/theme` 再改。

配置模型（任选其一）：

```text
/model add openai
/model key openai sk-...

/model add anthropic
/model key anthropic sk-ant-...

/model add ollama
```

或环境变量：`OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `CAW_API_KEY`。Ollama 本机模型**不需要** API 密钥。

没有云端密钥时仍可用演示启发式（如 `read Cargo.toml`、`grep fn `、`git status`）。

多模型时可用 `/router`：简单回合走 fast，难的走 default / strong。`/help` 列出全部斜杠命令。

---

## 命令行

```text
caw-agent [选项] [--print 提示词…]
caw-agent upgrade [--check] [now|latest|vX.Y.Z]
caw-agent rewind
caw-agent serve [--listen 127.0.0.1:4150] [--token TOKEN] [--workdir DIR]
```

| 选项 | 说明 |
|------|------|
| `-w, --workdir` | 工作区根目录，默认当前目录 |
| `--add-dir` | 额外工作目录（可重复） |
| `--no-mcp` | 不自动启动 MCP |
| `--base-url` / `CAW_BASE_URL` | OpenAI 兼容 API |
| `--model` / `CAW_MODEL` | 模型 id |
| `--api-key` / `CAW_API_KEY` | 本次进程密钥 |
| `-c, --continue` | 恢复本工作区上次会话（跳过异常退出询问） |
| `-r, --resume <id>` | 按完整 UUID 或唯一前缀恢复（跳过异常退出询问） |
| `--permission-mode` | `default` \| `acceptEdits` \| `plan` \| `auto` \| `bypassPermissions` |
| `--dangerously-skip-permissions` | 进入 full access |
| `-p, --print` | 无 TUI，助手回复打到 stdout |
| `--output-format` | `text`（默认）\| `json` \| `stream-json` |
| `--on-approval` | 权限提示：`fail`（默认，退出 2）\| `deny` \| `allow` |
| `--on-ask` | `AskUserQuestion`：`fail` \| `skip` \| `first` \| `all` |
| `--on-plan` | `ExitPlanMode`：`fail` \| `approve` \| `revise` |
| `--allowed-tools` / `--allowed-tools-file` | `--print` 自动批准的工具 glob |
| `--deny-tools` | 始终拒绝的工具 glob |
| `--max-turns` | `--print` 最大 LLM 轮数 |
| `-V, --version` | 打印 `caw-agent x.y.z` |

`--print` 默认权限模式是 **auto**，避免无人值守卡在每次写入。需要闸门时显式传 `--permission-mode default`。网络、屏幕、MCP 仍默认失败，除非 `--dangerously-skip-permissions`。

```bash
caw-agent --print -w . "summarize this repo"
caw-agent --print --output-format stream-json --on-approval deny -w . "list public API"
caw-agent --print --on-ask first --on-plan approve -w . "propose a plan then implement"
caw-agent --print --continue -w . "keep going"
```

`--print` 会把会话写到 `.caw-agent/sessions/`（含 `/cost` 用的 token 合计），并在 stderr 打印 resume id。Ctrl+C / SIGTERM 先保存再退出（130）。本工作区没有已存会话时 `--continue` 会报错。

### `caw-agent serve`

本机 REST / SSE 控制面，默认 `http://127.0.0.1:4150`。非回环监听必须 `--token` 或环境变量 `CAW_SERVE_TOKEN`（`Authorization: Bearer …`）。

| 路径 | 说明 |
|------|------|
| `GET /v1/health` | 探活 |
| `GET /v1/models` | 已配置供应商与 router |
| `GET /v1/sessions` | 会话列表 |
| `POST /v1/sessions` | 新建会话 |
| `GET /v1/sessions/{id}` | 会话摘要 |
| `POST /v1/sessions/{id}/prompt` | 投递提示（`{"prompt":"…","stream":true}` 可 SSE） |
| `POST /v1/sessions/{id}/cancel` | 取消进行中的回合 |

`--on-approval` / `--on-ask` / `--on-plan` 与 `--print` 相同。权限提示在无人值守时默认失败。

---

## 斜杠命令

`/help` 列出内置命令。常用：

```text
/settings · /config      控制面板
/permissions             模式与授权摘要
/model                   供应商与密钥
/router                  按复杂度选模型（on|off|pin|heuristic|hybrid|llm|fast|…）
/theme                   主题（dark light midnight forest ember ocean noir dusk dawn ansi）
/compact [focus]         压缩较早轮次
/context                 上下文用量估计
/cost                    本会话花费估计（随会话持久化）
/cost limit <usd>|off    达到上限则在下一次 LLM 前停住
/export [md|json] [path] 脱敏笔录（默认 .caw-agent/exports/）
/upgrade [now|vX.Y.Z]    检查或安装 GitHub Release + hub MCP
/notify on|off           后台标签或 --print 结束时桌面通知
/copy [N]                复制倒数第 N 条助手回复
/diff                    git diff --stat
/goal <cond>|clear       做到条件为止
/loop [5m] <prompt>      空闲时再入队
/doctor                  依赖与设置检查
/hooks                   已加载的 plugin hooks
/btw <q>                 旁路提问（不进主历史，Esc 取消）
/about                   作者与像素动画
/memory                  记忆开关 / 列表 / 打开目录
/dream                   立刻整理记忆
/continue                恢复上次会话
/load <id>               按 id 恢复
/pause [note]            暂停并打印 resume id
/new · /clear            新会话
/save · /sessions        保存 / 列出
/cd [path]               切换工作区（缺目录会创建）
/add-dir [path]          额外工作目录
/rewind                  文件检查点（undo · last · redo）
/plan [任务]             进入计划模式；带任务则直接开写计划（/plan off 离开）
/debug                   调试器会话
/init                    探测技术栈并写 CAW.md
/skills · /skill <name>  技能
/mcp                     MCP 包（list / install NAME）
/plugin enable|disable   插件
/worktrees               Task worktree 列表
/todos [expand|collapse|id] 任务列表 · 点一行或 `/todos <id>` 看详情
/agents · /tasks         子代理与后台任务 · 点一行看详情
/exit                    保存并退出（exit / quit 同样）
```

对话里用任意语言说退出、再见、bye，模型会调用 `exit`，效果与 `/exit` 相同。只想暂停、不关程序，用 `/pause`。

异常退出（进程被杀、断电、panic）后再启动会弹出 **继续上次会话 / 新开会话**。选继续会还原对话和未完成任务，并立刻接着做，不用再输入「继续」。正常退出或关 Windows 窗口会先保存再清锁，下次不弹。`--continue` / `--resume` 直接恢复。

权限模式用 **Shift+Tab**（或 **Alt+M** / **Alt+Shift+M**）循环：default → accept edits → plan → auto → full access。

任务与子代理共用提示词上方一行：两边都有时宽屏并排、窄屏上下叠。点一行看该条详情；点标题 `▾` / `▸` 可单独折叠。`Tab` 在输入框、任务、子代理之间切换键盘焦点；焦点在面板上时 `↑↓` 滚动该列表，`← →` 在 agents 焦点下切换主 / 子代理；`Esc` 回到输入框。

---

## 模型与密钥

默认供应商是 `openai` → `https://api.openai.com/v1`（`gpt-5.6`）。

```text
/model                         打开菜单
/model list                    列表与密钥状态
/model <name>                  切换已保存的供应商
/model add openai              官方 GPT（别名 gpt / chatgpt）
/model add anthropic           原生 Messages API
/model add deepseek            以及 qwen、qwen-intl、glm、glm-coding、ollama
/model add myapi https://…/v1 mid    第三方 / OpenAI 兼容网关
/model key openai sk-...       写入 ~/.caw-agent/secrets.json（所有工作区）
/model key <provider> clear
/model url https://.../v1
/model name gpt-4o-mini
/model env CAW_API_KEY
/model remove ollama
```

菜单里 Enter 切换，→ 管理，Esc / ← 返回。

### 第三方中转 / OpenAI 兼容网关

NewAPI、OneAPI 以及各类「OpenAI 兼容」中转站，不要改 `openai` / `anthropic` 等官方预设的地址。单独加一个供应商，三样都从中转站控制台抄：

| 填什么 | 从哪抄 |
|--------|--------|
| Base URL | OpenAI 兼容地址，一般以 `/v1` 结尾 |
| 密钥 | 中转站发的 `sk-…`，不是官方 Anthropic / OpenAI key |
| 模型名 | 它文档里的 id（例如 `gpt-4o` 或带供应商前缀的 id） |

```text
/model add relay https://your-gateway.example/v1 gpt-4o
/model key relay sk-...
```

中转请求走 `/v1/chat/completions`。原生 Messages 协议仅在对应的官方端点使用；将已保存的配置改为中转地址后，会自动使用兼容接口。OpenRouter 可通过 `/model add openrouter` 添加，密钥为 `OPENROUTER_API_KEY`。

**原生 Messages：** 仅当配置使用其官方端点时走 `/v1/messages`；其他地址均按兼容接口处理。支持 `/chat/completions` 网关，密钥可用环境变量或 `/model key` 配置。

查找顺序（当前供应商）：环境变量（该供应商的 `api_key_env`，例如 OpenRouter 用 `OPENROUTER_API_KEY`；`CAW_API_KEY` 作为兜底）→ 可选的项目 `.caw-agent/secrets.json` → **`~/.caw-agent/secrets.json`** → 配置里的内联密钥。`use_keyring` 为 true 时（全局配置默认）优先系统钥匙串；钥匙串不可用时密钥会留在 `secrets.json`，不会被内存 mock 清掉。

可选：`OPENAI_ORG_ID`、`OPENAI_PROJECT_ID`。

**Ollama：** `/model add ollama` 后可在菜单里挑本机已拉的模型，**不需要** API 密钥。空的 `config.json` 不会挡住启动。

**Router：** `/router on` 按回合复杂度在 fast / default / strong 三档之间选模型。分类器可以是 `heuristic`（规则）、`llm`（另一次短调用）或 `hybrid`。`/router pin` 钉死当前 `/model`，不再自动换。档位用 `/router fast|default|strong [provider] [model]` 指定。

---

## 工作区与全局目录

每个项目有自己的 `.caw-agent/`；跨项目数据在 `~/.caw-agent/`。

### `~/.caw-agent/`

| 路径 | 用途 |
|------|------|
| `config.json` | 全局默认（如新工作区主题） |
| `secrets.json` | API 密钥（`/model key` 写这里） |
| `rules/*.md` | 你写的全局规则 |
| `memory/` | 全局自动记忆（OS / 工具链坑） |
| `hf/` | `hf` 工具默认下载目录 |
| `skills/` | 技能覆盖（默认技能打在二进制里） |
| `tools/` | 便携安装与 winget `--location` |
| `bin/` | 发布二进制与 shim（会 prepend 到 `run` / debug 的 PATH） |
| `downloads/` | `download_file` 默认目录 |
| `scoop/` | Windows 隔离 Scoop 根 |
| `mcp/` | 已安装的 MCP 包 |
| `languages.toml` | 额外语言栈 / LSP / 调试映射（仍走内置 `analyze` / `lsp` / `debug`） |

### 项目 `.caw-agent/`

| 路径 | 用途 |
|------|------|
| `config.json` | 模型、权限、MCP、`last_session_id`、记忆开关 |
| `secrets.json` | 可选的项目级密钥覆盖（不要提交） |
| `memory/` | 项目自动记忆 |
| `sessions/` | 会话 |
| `runtime.lock` | TUI 运行中标记；异常退出后用于询问是否还原 |
| `exports/` | `/export` 脱敏笔录 |
| `checkpoints/` | `/rewind` 文件快照 |
| `audit.log` | 工具允许/拒绝审计 |
| `input_history.json` | 提示词历史 |
| `rules/*.md` | 项目规则 |
| `worktrees/` | `Task worktree: true` 的隔离树 |
| `media/` | 截图输出（仍在 jail 内） |
| `plan.md` | 计划模式文稿 |
| `languages.toml` | 覆盖本仓库的语言探测（工作区优先于全局） |

项目说明写在工作区根的 `CAW.md`。工作区 MCP 服务器可写在 `.mcp.json`，但仓库配置能启动本地进程，所以默认不加载；确认仓库可信后用 `/settings mcp-workspace` 开启。长尾语言用 `languages.toml` 加探测表，不要为每种语言装一个 MCP。

`/cd` 可在会话中换工作区：保存旧会话、加载新根的配置 / 技能 / 已信任 MCP、重绑文件 jail、新开 session id（屏幕上的对话文本会保留）。回合或权限提示进行中不能切。

---

## 权限与沙箱

### 模式

| 模式 | 行为 |
|------|------|
| `default` | 读可自动；写 / exec / MCP / 网络 / 截图要问 |
| `acceptEdits` | 文件写入与安全文件系统命令自动过；MCP / 网络 / 其它 `run` 仍问 |
| `plan` | 只调研。写 `.caw-agent/plan.md` 后 `ExitPlanMode`；架构类计划会带图；批准后进 auto（或 ask first），Plan 本身不作为启动默认档 |
| `auto` | accept-edits + `analyze` / 检查测试 lint + git **只读检查**。改 git、裸 `make`、网络、屏幕、MCP、安装仍问 |
| `bypassPermissions`（界面：**full access**） | 跳过全部提示（含截图）。离开 full access 会清掉 session 授权 |

硬拒绝（`permissions.deny`、`/settings deny exec:rm *`）在任何模式都生效，包括 full access。`/settings clear-grants` 清授权和拒绝规则。

第一次进入 full access 会确认并写 `"allow_bypass": true`。

**Full access 只跳过提示，不会关掉 OS jail。**

权限表：`1` / Enter 一次 · `2` 本会话 · `3` 写入配置 · Esc 拒绝。

### 文件 jail

`read_file` / `write_file` / `delete_file` / `list_dir` / `glob` / `grep` / `apply_patch` 必须落在 canonicalize 后的工作区内。逃逸的中间符号链接会被拒。`delete_file` 只删文件。`.ipynb` 按 cell 视图编辑。

### `run` 的 OS jail

| 系统 | 后端 | 说明 |
|------|------|------|
| Linux / WSL2 | bubblewrap + 代理桥 | 需 `bwrap` + `socat`。拦截 `*.exe` / `/mnt/...` |
| macOS | Seatbelt (`sandbox-exec`) | 系统自带。拒绝 `~/.ssh` |
| 原生 Windows | **不可用**（失败即关） | 默认 `sandbox: false`；请用 WSL2 |

默认：jail **开**（Windows 除外）、exec 网络 **关**、超时 120s。`/settings sandbox` 可关 jail。每次沙箱失败的 `run` 会附 `<sandbox_violations>`。`dangerouslyDisableSandbox: true` 是单次逃生（`/settings unsandbox`）。

硬拦截包括 fork-bomb、`rm -rf /`、管道进 shell、以及读写 `.caw-agent/secrets.json` / `config.json`。

### LSP 独立 jail

语言服务器按“工作区 + server id”持久复用，但使用独立的 OS jail 策略：默认断网、工作区源码只读，只有 `.caw-agent/lsp/<server>/` 缓存目录可写；工具链和包缓存只读，SSH、云凭证、钥匙串与 caw-agent 密钥不可见。关闭或切换策略时会回收整棵服务器进程树，LSP 消息队列也有固定上限。

项目 `.caw-agent/languages.toml` 定义的服务器属于仓库控制的可执行代码。每次启动新进程前都会显示解析后的程序、参数、隔离策略和配置指纹，并要求 **Start server / Cancel**；auto、Full access 和旧授权都不能跳过。配置或命令变化后指纹随即失效。

`/settings lsp-sandbox` 切换 LSP jail，`/settings lsp-writes` 控制是否允许写整个工作区，`/settings lsp-network` 控制宿主网络。修改任一项都会先停止现有语言服务器。原生 Windows 尚无 OS jail，建议在 WSL2 下运行；项目自定义服务器仍会强制确认。

---

## 会话、记忆与导出

| 层 | 路径 | 谁写 | 用途 |
|----|------|------|------|
| 全局规则 | `~/.caw-agent/rules/*.md` | 你 | 所有工作区的固定说明 |
| 全局记忆 | `~/.caw-agent/memory/` | agent + 你 | 跨仓库的机器级坑 |
| 项目规则 | `CAW.md` | 你 | 本仓库说明 |
| 项目记忆 | `.caw-agent/memory/` | agent + 你 | 架构、构建命令、仓库怪癖 |
| 会话交接 | session JSON `handoff` | `/pause` 或工具 | 停在哪里 |

失败恢复后若没写记忆，回合结束会催一次。同一回合两次失败未读记忆会打断并要求先打开 index / `debugging.md`。空转有熔断：多次同一错误后停 `run` / 编辑 / 安装，并弹出继续 / 换思路 / 换模型。

`/dream` 用当前 LLM 整理记忆。`auto_dream_enabled` 且自上次整理后的写入次数 ≥ `auto_dream_min_writes` 时自动做。

`/cost` 读会话里持久化的 token，恢复会话**不会**清零花费。`/export md|json` 写脱敏笔录，不改磁盘上的 session 文件。自动 compact 优先用接口返回的 `prompt_tokens`，否则按字符/4。

`/rewind` 或空提示下 **Esc Esc** 打开检查点：可恢复代码、对话或两者。不撤销 `run` / MCP / 手改，那些用 git。

退出时若后台任务或未完成 todo 还在，第一次 `/exit`、Ctrl+C 或对话里的 `exit` 会确认。

---

## 工具摘要

| 工具 | 说明 | 权限 |
|------|------|------|
| 文件读写 / glob / grep / apply_patch | 工作区 jail | 读默认自动；写要问 |
| `run` | 工作区根执行命令 | Exec + 可选 OS jail |
| `analyze` | 跑检查/测试并解析 `file:line`（内置，不是 MCP） | Exec |
| `lsp` | 语言服务器：hover / 定义 / 引用 / 符号 / 诊断（内置） | 首次查询可启动进程，需 Exec；status / shutdown 为读 |
| `debug` | gdb / lldb / cdb / pdb / node / dlv / jdb 等（内置） | Exec |
| `git_*` | status / diff / log / commit / fetch / pull / push / conflicts / stash | 检查只读；变更要 Exec。commit 不添加第三方署名。push 从不用 `--force` |
| `gh` | PR / issue / release / run / `repo_view`；可创建与评论 | 不提供 merge / close / `gh api` |
| `hf` | Hugging Face：whoami / download / upload / cache | 下载走网络；upload 要 Exec。令牌用 `HF_TOKEN` |
| `db` | sqlite（工作区路径）或 postgres / mysql（DSN） | 只读 query；`exec` 要问。非 localhost 需白名单 |
| `docker` | `ps` / images / logs / build / compose | 无 `--privileged`。jail 挡 socket 时可 unsandbox |
| `ssh` | 白名单主机 `exec` / upload / download | 新主机要批准；不用 `ssh-copy-id` |
| `cloud` | `aws` / `gcloud` / `az` / `kubectl` | 只读检查自动；变更要问。无 destroy / login |
| `web_search` / `web_fetch` / `download_file` | 搜索与下载 | Network；禁 localhost / 私网 |
| `screenshot` / `computer` | 截图与键鼠 | Screen。computer-use **默认关**，`/settings computer-use` |
| `extract_archive` | zip / tar / gz… | Write |
| `install_program` | 自动探测当前系统包管理器；支持 winget/choco/scoop/apt/dnf/pacman/brew/pip/便携安装 | 每次安装都弹出“立即安装 / 取消” |
| `Task` | 子代理。`worktree: true` 时 jail 绑到 `.caw-agent/worktrees/<id>/` | — |
| `Worktree` | `list` / `merge` / `abandon` | — |
| `exit` | 用户告别或要求离开时结束进程（仅主代理） | 自动 |

`auto` 下 git **只检查**：`git_status` / `git_conflicts` / `git status|diff|log|show` / `git stash list|show`。变基仍走 `run`。

截图只写到 jail 内（默认 `.caw-agent/media/`）。全屏会尽量遮住本终端。macOS 用 ScreenCaptureKit，失败回退 CoreGraphics。

Computer-use 有机器级锁、应用白名单与密码管理器/银行等硬拒绝。浏览器建议 `/mcp install browser`，不要用 computer 去点网页。

---

## MCP 与技能

`.mcp.json` 支持 stdio 或远程 URL（HTTP / SSE）：

```json
{
  "mcpServers": {
    "local": { "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "."] },
    "remote": { "url": "https://example.com/mcp", "headers": { "Authorization": "Bearer …" } }
  }
}
```

全局已安装包和启用的插件由用户管理，可正常加载。仓库内 `.mcp.json` 默认视为不可信并忽略；只对你信任的仓库开启 `/settings mcp-workspace`，关闭后会立即卸载这些工作区服务器。

官方包装在公开仓 `mcp/`（[目录](https://github.com/noxrick91/caw-agent-hub/tree/master/mcp)）：browser、doc、image、ocr、speech、freecad、blender。`/mcp install <name>` 从 GitHub 下载到 `~/.caw-agent/mcp/<name>/`。也可以装任意 GitHub 包：`/mcp install owner/repo` 或仓库 URL。工作区里的 `./mcp/<name>`、文件夹、zip 仍然可用。`/mcp install browser` 之后用 `mcp__browser__*`。

附加音频只是路径，**不会**自动转写。用户明确要求转写时再用 speech 包。

默认技能打在二进制里：`review`、`fix`、`commit`、`doctor`、`verify`、`code-review`、`simplify`、`batch`、`pr`。可用 `~/.caw-agent/skills/`、工作区 `skills/` 覆盖。`/mcp install` 会把该包的 skills 拷进全局 skills（带 `.mcp-pack` 戳）；卸载只删带戳的。

```text
/skills
/skill review [args]
/review
/plugin enable <name>
```

---

## 界面与快捷键

多标签：每个标签独立回合与队列。`ctrl+t` 新标签，`ctrl+tab` 切换，`ctrl+w` 关闭。后台跑完的标签会标 `•`。

提示词上方是 **tasks / agents** 条：有待办或子代理时出现。两边都展开且够宽时并排等高；窄屏上下叠，高度跟着内容走。点一行看详情（how / accept / 最近验收，或子代理笔录）。点 `▾` / `▸` 单独折叠。任务按文档顺序从上往下推进；子代理按开始时间新的在上（`main` 钉在顶部）。

`Tab` 在输入框和已展开的 tasks / agents 面板之间循环焦点。焦点在面板上时 `↑↓` 滚动该列表，`← →` 切换主 / 子。点 tasks / agents 一行（或 `/todos <id>`）看该条的 how / accept / 最近验收或实时笔录。`/todos expand|collapse` 折任务。滚轮落在对应面板上滚动；`Alt+↑↓` 仍滚当前焦点区域。`/worktrees` 处理隔离树。

忙碌时 Enter **入队**，不打断。Esc：先清草稿；空且忙碌则中断。**Ctrl+C** 退出（有后台任务会先确认）。**Ctrl+Shift+C** 复制拖选的笔录。

`@` 打开文件选择。粘贴超长文本会收成 `[Pasted text #N]`。输入框最多约 8 行；溢出时用 `Shift+↑↓` / `Shift+PgUp` 滚输入框（不移动光标、不拉队列），有鼠标也可滚轮。草稿上限 4000 字。`PageUp` / `PageDown` 翻笔录。

---

## 配置片段

`.caw-agent/config.json` 常见项：

```json
{
  "auto_memory_enabled": true,
  "auto_dream_enabled": true,
  "auto_dream_min_writes": 3,
  "auto_compact_enabled": true,
  "compact_token_threshold": 80000,
  "cost_limit_usd": 5.0,
  "notify_on_idle": false,
  "permissions": {
    "lsp": {
      "sandbox": true,
      "allow_network": false,
      "allow_workspace_writes": false
    }
  },
  "router": {
    "enabled": false,
    "classifier": "heuristic",
    "fast": { "provider": "ollama", "model": "qwen2.5-coder:7b" }
  }
}
```

`languages.toml` 示例（`~/.caw-agent/` 或项目 `.caw-agent/`）：

全局文件由用户管理；项目文件中的 `commands` 每次创建服务器进程都会触发带指纹的启动确认。

```toml
[[stack]]
name = "Acme"
manifests = ["acme.lock"]
check = "acme check"
test = "acme test"

[[lsp]]
id = "acme"
extensions = ["acme"]
commands = [["acme-lsp", "--stdio"]]

[[debug]]
backend = "native"
extensions = ["acme"]
```

`/settings notify-on-idle` 或 `/notify on`：后台标签结束或 `--print` 完成时发桌面通知（默认关）。

---

## 故障排除

| 现象 | 处理 |
|------|------|
| 升级 HTTP 404 | 该 tag 还没有 Release，或私有仓还没把产物推到 hub。看 [Releases](https://github.com/noxrick91/caw-agent-hub/releases) |
| 没有本平台资产 | 矩阵只有上表列出的目标 |
| GitHub 403 / 429 | 设置 `GH_TOKEN` 或 `CAW_GITHUB_TOKEN` |
| SHA256 不符 | 重新下；不要混用不同 tag 的 sums 与二进制 |
| `--version` 对不上 | 安装器会尝试恢复 `.bak` |
| 原生 Windows `run` 沙箱失败 | 预期行为；用 WSL2 或 `/settings sandbox` 关掉 jail |
| macOS 截图黑屏 / 空图 | 给终端「屏幕录制」权限后重启终端 |
| `--print` 退出码 2 | 默认 `fail`：权限 / 提问 / 计划需要人。改 `--on-approval` / `--on-ask` / `--on-plan` |
| Windows `irm …/install.ps1` 报错或没有真正执行 | GitHub Pages 把 `.ps1` 标成二进制。改用 `irm https://agent.noxcaw.com/install.txt \| iex`，或 `iex ((New-Object Net.WebClient).DownloadString('https://agent.noxcaw.com/install.ps1'))` |
| Windows 提示 TLS / secure channel | 用 Windows PowerShell 5.1+ 或 PowerShell 7；安装器会强制 TLS 1.2 |
| 已有损坏的 `caw-agent.exe` 无法重装 | 关掉所有 caw-agent 窗口后再跑安装器，或删掉 `%USERPROFILE%\.caw-agent\bin\caw-agent.exe` |
| Windows 重装/更新后仍是旧版本 | 旧安装器会把「已安装」交给 `caw-agent upgrade now`，文件锁或 GitHub API 失败时不会换包。关掉窗口后重新跑 `irm https://agent.noxcaw.com/install.txt \| iex`，再新开终端执行 `caw-agent --version`。用 `Get-Command caw-agent` 确认不是别的目录里的旧 exe |
| 找不到命令 | `source ~/.caw-agent/env` 或新开终端；安装器会写 rc hook。Windows 新开一个终端以加载用户 PATH |
| `serve` 拒绝监听 | 非 `127.0.0.1` / `::1` 必须 `--token` 或 `CAW_SERVE_TOKEN` |
| Ollama 仍要密钥 | 用 `/model add ollama`，不要走需要 key 的 OpenAI 兼容网关 |
| 中转站 401 / 模型不存在 | 用中转站自己的 Base URL、密钥和模型名；不要改 `openai` / `anthropic` 预设地址。见 [模型与密钥](#/models) |

本手册是对外使用说明的唯一维护处。实现细节只在私有源码仓里。
