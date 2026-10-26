# Security Policy

## 支持的版本

阅稿（VideoTranscriptAPI fork）以你自建部署为准。请使用仓库当前 `main` 与发布说明中的版本；上游 PolyForm Noncommercial 条款见 [LICENSE](LICENSE)。

## 汇报漏洞

请通过仓库 Issues（可标 private / security）或维护者私信描述：影响面、复现步骤、是否已在公网暴露。**不要**在公开 issue 里贴真实 `auth_token`、用户库或生产日志。

## 密钥

发行包与公开仓**不得**包含真实 `api_key` / token。用户须自备 DeepSeek 等密钥，写入本机 `config/config.jsonc`（gitignore）。若密钥曾误提交，请立即在服务商侧轮换。

## 已知边界与限制（请按此配置）

1. **访问令牌 / LAN**  
   Web 提交与历史查询依赖 `api.auth_token`（及 `users.json` 多用户 key）。`/view/{view_token}` 是**不可猜测的公开只读 capability**：拿到链接即可读对应文稿。局域网部署时请勿把服务裸暴露到公网；需要外网时请加反向代理鉴权 / VPN，并轮换 token。

2. **章节 `start_time` 为近似**  
   章节时间由 segment 下标反查推导，脏时间戳或乱序 segment 可能导致倒挂修复后的**近似**时间，不宜当剪辑帧级真值。

3. **飞书 / TikHub / MediaResolver 均为可选**  
   未配置时相关下载或妙记桥不可用；不影响 Path A（文稿 → `/view`）与已配置的 `local_whisper`。勿把第三方 API key 提交进 git。

4. **无「分钟级」托管 E2E 承诺**  
   公开 CI 只跑轻量单测与配置预检，**不**保证 CapsWriter / 飞书妙记 / TikHub 的端到端联调。完整 ASR 链路请在本机用 `scripts/ops/smoke_check.py` 与自有样例验收。

5. **密钥与数据目录**  
   `config/config.jsonc`、`config/users.json`、`.env`、`data/` 已在 `.gitignore`。分发或开源导出时务必确认这些文件未打进包。

6. **依赖与供应链**  
   使用 `uv sync --frozen` 与锁文件；自行添加依赖时注意许可证（本仓为 Noncommercial）与来源可信度。

## 安全加固建议

- 生产或共享 LAN：反向代理 TLS + 限制来源 IP；定期轮换 `auth_token`
- 关闭不需要的下载器 / 通知通道
- 分享 `/view` 链接前确认文稿不含不该公开的内容

## 轮换已暴露的 Key

见 [ROTATE-KEY.md](ROTATE-KEY.md)：在 DeepSeek 控制台作废旧 key，新 key 只写本机 config/config.jsonc，勿提交。
