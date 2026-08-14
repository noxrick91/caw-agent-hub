# caw-agent-hub

[caw-agent](https://github.com/noxrick91/caw-agent) 的公开主页与发布通道：下载预编译包、阅读手册。

源码仓保持私有。访客只从**本仓库的 GitHub Release** 取二进制和 `SHA256SUMS`，不访问私有 API。

## 本地预览

不要用 `file://`（文档用 `fetch` 加载 Markdown）。

```bash
python3 -m http.server 8080
# http://127.0.0.1:8080
```

## 发布站点

GitHub Pages：Settings → Pages → `master` / `/ (root)`。本仓需为 **public**。

## 发布二进制

私有 `caw-agent` 在 `v*` 标签上编好后，把五个平台资产和 `SHA256SUMS` 上传到 **本仓同名 tag 的 Release**。官网读 `noxrick91/caw-agent-hub` 的 `releases/latest`。`caw-agent upgrade` 的默认仓库也应指向这里。

安装脚本请放在本仓（或站点内），不要从私有仓的 `raw.githubusercontent.com` 拉。

## 相关

| 项目 | 可见性 | 说明 |
|------|--------|------|
| `caw-agent` | 私有 | 源码与 CI |
| `caw-agent-hub` | 公开 | 官网、手册、Release 资产 |
