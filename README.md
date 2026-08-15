# caw-agent

[官网](https://agent.noxcaw.com) · [文档](https://agent.noxcaw.com/docs.html) · [![downloads](https://img.shields.io/github/downloads/noxrick91/caw-agent-hub/total)](https://github.com/noxrick91/caw-agent-hub/releases)

网站页面、安装器和手册从私有产品仓发布。请在那边改 `hub/` 与 `scripts/install*`，不要直接改本仓的 `index.html`、`docs.html`、`assets/`、`content/`、`install*`。本仓只手改 Releases、`mcp/` 和这份 README。

你的终端里多了一个会改代码的搭档。

读代码、改文件、跑测试，都在你打开的这个项目里完成。每次写盘或执行命令前，它都会停下来等你确认。

## 安装

Linux / macOS：

```bash
curl -fsS https://agent.noxcaw.com/install | bash
```

Windows PowerShell：

```powershell
irm https://agent.noxcaw.com/install.txt | iex
```

安装脚本会把 `~/.caw-agent/bin` 写进 shell rc（并 `source ~/.caw-agent/env`）。之后：

```bash
caw-agent --workdir .
```

用 `/model add` 配置模型，或设置 `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`。升级：

```text
caw-agent upgrade now
```

完整说明见 [文档](https://agent.noxcaw.com/docs.html)。

## 它做什么

- **动手干活** — 在你的项目里读代码、改文件、跑测试
- **安全可控** — 只访问你打开的目录；写盘和命令都会先问你
- **过程透明** — 每一步都显示在终端里，随时可以介入

支持 Linux（x64 / arm64）、macOS（Apple Silicon / Intel）、Windows（x64 / ARM64）。

## 扩展

官方 MCP 可在 agent 里直接安装，例如：

```text
/mcp install browser
```

也提供 `doc`、`image`、`ocr`、`speech`、`freecad`、`blender`。
