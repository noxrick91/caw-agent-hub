# caw-agent 使用手册

沙箱里的终端编程助手：Claude Code 风格 TUI、权限经纪、MCP、会话与记忆。预编译包从本站所属仓库的 [GitHub Releases](https://github.com/noxrick91/caw-agent-hub/releases) 安装到 `~/.caw-agent/bin`。源码仓私有，不对外。

---

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
irm https://agent.noxcaw.com/install.ps1 | iex
```

脚本按本机 OS/ARCH 选择资产（Linux x64/arm64、macOS Apple Silicon/Intel、Windows x64），下载后核对同 Release 的 `SHA256SUMS`，装到 `~/.caw-agent/bin`。已安装且装 latest 时会走 `caw-agent upgrade now`。安装脚本会写入 `~/.caw-agent/env`，并在 `.bashrc` / `.zshrc` / `.bash_profile` / fish `config.fish` 里加上 hook，然后 `source` 该 env。`curl | bash` 改不了你当前已经打开的 shell，新开终端即可，或执行 `source ~/.caw-agent/env`。不想改 rc 时设 `CAW_NO_PATH=1`。

Pages 尚未生效时可用：

```bash
curl -fsS https://raw.githubusercontent.com/noxrick91/caw-agent-hub/master/install | bash
```

### 官网 / 手动下载

打开本站首页，按平台下载最新资产，放到 `~/.caw-agent/bin`（Windows 为 `%USERPROFILE%\.caw-agent\bin\caw-agent.exe`），并对照 `SHA256SUMS`。首页表格的「本版 / 累计」来自 GitHub Release 每个资产的 `download_count`：一键安装、`caw-agent upgrade`、浏览器手动下载都会加一。拉 Pages 上的 `install` 脚本本身不计入；`SHA256SUMS` 单独计数（每次安装会先下校验文件）。`upgrade --check` 只打 API，不增加下载量。

| 平台 | 资产 |
|------|------|
| Linux x86_64 | `caw-agent-x86_64-unknown-linux-gnu` |
| Linux aarch64 | `caw-agent-aarch64-unknown-linux-gnu` |
| macOS Apple Silicon | `caw-agent-aarch64-apple-darwin` |
| macOS Intel | `caw-agent-x86_64-apple-darwin` |
| Windows x64 | `caw-agent-x86_64-pc-windows-msvc.exe` |

不支持的组合（如 Windows ARM、Linux musl）没有预编译包，需从源码构建。

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

Windows 若正在替换自己，会旁路写入并提示重启后再生效。

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

配置模型（二选一即可）：

```text
/model add openai
/model key openai sk-...

/model add anthropic
/model key anthropic sk-ant-...
```

或环境变量：`OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `CAW_API_KEY`。

没有密钥时仍可用演示启发式（如 `read Cargo.toml`、`grep fn `、`git status`）。

---

## 命令行

```text
caw-agent [选项] [--print 提示词…]
caw-agent upgrade [--check] [now|latest|vX.Y.Z]
```

| 选项 | 说明 |
|------|------|
| `-w, --workdir` | 工作区根目录，默认当前目录 |
| `--no-mcp` | 不自动启动 MCP |
| `--base-url` / `CAW_BASE_URL` | OpenAI 兼容 API |
| `--model` / `CAW_MODEL` | 模型 id |
| `--api-key` / `CAW_API_KEY` | 本次进程密钥 |
| `-c, --continue` | 恢复本工作区上次会话 |
| `-r, --resume <id>` | 按完整 UUID 或唯一前缀恢复 |
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

---

## 斜杠命令

`/help` 列出内置命令。常用：

```text
/settings · /config      控制面板
/permissions             模式与授权摘要
/model                   供应商与密钥
/theme                   主题（dark light midnight forest ember ocean noir dusk dawn ansi）
/compact [focus]         压缩较早轮次
/context                 上下文用量估计
/cost                    本会话花费估计（随会话持久化）
/cost limit <usd>|off    达到上限则在下一次 LLM 前停住
/export [md|json] [path] 脱敏笔录（默认 .caw-agent/exports/）
/upgrade [now|vX.Y.Z]    检查或安装 GitHub Release
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
/export                  导出笔录
/cd [path]               切换工作区（缺目录会创建）
/rewind                  文件检查点
/plan                    计划模式
/train                   从会话训练学生模型
/skills · /skill <name>  技能
/mcp                     MCP 包
/plugin enable|disable   插件
/worktrees               Task worktree 列表
/agents · /tasks         子代理与后台任务
/exit                    保存并退出（exit / quit / 退出 同样）
```

权限模式用 **Shift+Tab**（或 **Alt+M** / **Alt+Shift+M**）循环：default → accept edits → plan → auto → full access。

---

## 模型与密钥

默认供应商是 `openai` → `https://api.openai.com/v1`（`gpt-5.6`）。

```text
/model                         打开菜单
/model list                    列表与密钥状态
/model <name>                  切换已保存的供应商
/model add openai              官方 GPT（别名 gpt / chatgpt）
/model add anthropic           Claude Messages API（别名 claude）
/model add deepseek            以及 qwen、qwen-intl、glm、glm-coding、ollama
/model add myapi https://…/v1 mid    自定义 OpenAI 兼容端点
/model key openai sk-...       写入 ~/.caw-agent/secrets.json（所有工作区）
/model key <provider> clear
/model url https://.../v1
/model name gpt-4o-mini
/model env CAW_API_KEY
/model remove ollama
```

菜单里 Enter 切换，→ 管理，Esc / ← 返回。

**Anthropic：** 供应商为 `anthropic` / `claude` 或主机为 `api.anthropic.com` 时走原生 `/v1/messages`。OpenRouter、DashScope、URL 含 `compatible` 或 `/chat/completions` 的网关仍走 `/v1/chat/completions`。密钥：`ANTHROPIC_API_KEY` 或 `/model key anthropic`。

查找顺序（当前供应商）：环境变量（`api_key_env` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`）→ 可选的项目 `.caw-agent/secrets.json` → **`~/.caw-agent/secrets.json`** → 配置里的内联密钥。`use_keyring` 为 true 时（全局配置默认）优先系统钥匙串。

可选：`OPENAI_ORG_ID`、`OPENAI_PROJECT_ID`。

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
| `train/` | SFT 导出、权重、训练日志 |
| `models/` | 训练出的 LoRA / student |
| `skills/` | 技能覆盖（默认技能打在二进制里） |
| `tools/` | 便携安装与 winget `--location` |
| `bin/` | 发布二进制与 shim（会 prepend 到 `run` / debug 的 PATH） |
| `downloads/` | `download_file` 默认目录 |
| `scoop/` | Windows 隔离 Scoop 根 |
| `mcp/` | 已安装的 MCP 包 |

### 项目 `.caw-agent/`

| 路径 | 用途 |
|------|------|
| `config.json` | 模型、权限、MCP、`last_session_id`、记忆开关 |
| `secrets.json` | 可选的项目级密钥覆盖（不要提交） |
| `memory/` | 项目自动记忆 |
| `sessions/` | 会话 |
| `exports/` | `/export` 脱敏笔录 |
| `checkpoints/` | `/rewind` 文件快照 |
| `audit.log` | 工具允许/拒绝审计 |
| `input_history.json` | 提示词历史 |
| `rules/*.md` | 项目规则 |
| `worktrees/` | `Task worktree: true` 的隔离树 |
| `media/` | 截图输出（仍在 jail 内） |
| `plan.md` | 计划模式文稿 |

项目说明写在工作区根的 `CAW.md`。MCP 服务器写在 `.mcp.json`。

`/cd` 可在会话中换工作区：保存旧会话、加载新根的配置 / 技能 / MCP、重绑文件 jail、新开 session id（屏幕上的对话文本会保留）。回合或权限提示进行中不能切。

---

## 权限与沙箱

### 模式

| 模式 | 行为 |
|------|------|
| `default` | 读可自动；写 / exec / MCP / 网络 / 截图要问 |
| `acceptEdits` | 文件写入与安全文件系统命令自动过；MCP / 网络 / 其它 `run` 仍问 |
| `plan` | 只调研。写 `.caw-agent/plan.md` 后 `ExitPlanMode`；你批准再实现 |
| `auto` | accept-edits + `analyze` / 检查测试 lint + git **只读检查**。改 git、裸 `make`、网络、屏幕、MCP、安装仍问 |
| `bypassPermissions`（界面：**full access**） | 跳过全部提示（含截图）。离开 full access 会清掉 session 授权 |

硬拒绝（`permissions.deny`、`/settings deny exec:rm *`）在任何模式都生效，包括 full access。`/settings clear-grants` 清授权和拒绝规则。

第一次进入 full access 会确认并写 `"allow_bypass": true`。

**Full access 只跳过提示，不会关掉 OS jail。** 这与 Claude Code 一致。

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

退出时若后台任务还在跑，第一次 `/exit` 或 Ctrl+C 会确认。

---

## 工具摘要

| 工具 | 说明 | 权限 |
|------|------|------|
| 文件读写 / glob / grep / apply_patch | 工作区 jail | 读默认自动；写要问 |
| `run` | 工作区根执行命令 | Exec + 可选 OS jail |
| `analyze` | 跑检查/测试并解析 `file:line` | Exec |
| `debug` | gdb / lldb / cdb / pdb / node / dlv / jdb 等 | Exec |
| `git_*` | status / diff / log / commit / fetch / pull / push / conflicts / stash | 检查只读；变更要 Exec。commit 拒 Cursor 署名。push 从不用 `--force` |
| `gh` | `status` / `pr_view` / `pr_list` / `pr_checks` / `pr_create` / `pr_comment` | 不提供 merge |
| `web_search` / `web_fetch` / `download_file` | 搜索与下载 | Network；禁 localhost / 私网 |
| `screenshot` / `computer` | 截图与键鼠 | Screen。computer-use **默认关**，`/settings computer-use` |
| `extract_archive` | zip / tar / gz… | Write |
| `install_program` | winget / choco / scoop / 便携解压 | Exec |
| `Task` | 子代理。`worktree: true` 时 jail 绑到 `.caw-agent/worktrees/<id>/` | — |
| `Worktree` | `list` / `merge` / `abandon` | — |

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

子代理用 `Task` 拉起，显示在提示词上方。`← →` 切换主 / 子；`/worktrees` 处理隔离树。

忙碌时 Enter **入队**，不打断。Esc：先清草稿；空且忙碌则中断。**Ctrl+C** 退出（有后台任务会先确认）。**Ctrl+Shift+C** 复制拖选的笔录。

`@` 打开文件选择。粘贴超长文本会收成 `[Pasted text #N]`。`PageUp` / `PageDown` 翻笔录。

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
  "notify_on_idle": false
}
```

`/settings notify-on-idle` 或 `/notify on`：后台标签结束或 `--print` 完成时发桌面通知（默认关）。

---

## 训练（可选）

日常会话可导出为带质量权重的 SFT 语料：

```text
/train
/train export
/train start
/train status
```

数据在 `~/.caw-agent/train/`，适配器在 `~/.caw-agent/models/`。导出默认脱敏。请遵守模型供应商条款，仅限本地自用。

---

## 故障排除

| 现象 | 处理 |
|------|------|
| 升级 HTTP 404 | 该 tag 还没有 Release，或私有仓还没把产物推到 hub。看 [Releases](https://github.com/noxrick91/caw-agent-hub/releases) |
| 没有本平台资产 | 矩阵只有上表五个目标 |
| GitHub 403 / 429 | 设置 `GH_TOKEN` 或 `CAW_GITHUB_TOKEN` |
| SHA256 不符 | 重新下；不要混用不同 tag 的 sums 与二进制 |
| `--version` 对不上 | 安装器会尝试恢复 `.bak` |
| 原生 Windows `run` 沙箱失败 | 预期行为；用 WSL2 或 `/settings sandbox` 关掉 jail |
| macOS 截图黑屏 / 空图 | 给终端「屏幕录制」权限后重启终端 |
| `--print` 退出码 2 | 默认 `fail`：权限 / 提问 / 计划需要人。改 `--on-approval` / `--on-ask` / `--on-plan` |
| 找不到命令 | `source ~/.caw-agent/env` 或新开终端；安装器会写 rc hook |

本手册是对外使用说明的唯一维护处。实现细节只在私有源码仓里。
