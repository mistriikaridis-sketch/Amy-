# 阅稿开源发布步骤

本导出包（或工作副本）已完成「必须先做」准备：**不要** push 到 `https://github.com/zlxlabs/VideoTranscriptAPI`。

## 已完成

- [x] PolyForm Noncommercial LICENSE + 上游 / 阅稿 Required Notice
- [x] README 改为阅稿安装入口（含截图、smoke_check、.env.example）
- [x] 私有 CI / 部署工作流已移除，换成 `ubuntu-latest` 的 `.github/workflows/ci.yml`
- [x] `.gitignore` 覆盖 `data/`、密钥配置、`patch-bak-*`、`.env.*`
- [x] 敏感文件未纳入导出（`config/config.jsonc`、`config/users.json`、`.env`、`data/` 等）

## 你需要做的

1. 在 GitHub（或其它托管）**新建空仓库**（建议公开，名称自定，例如 `yuegao`）。
2. 把新仓 URL 发给助手，或本地执行：

```bash
cd /path/to/yuegao-oss
git remote add origin <新仓 URL>
git push -u origin main
```

**把新仓 URL 给我即可 push。**
