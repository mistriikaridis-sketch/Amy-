# 轮换 DeepSeek API Key（必做）

开源导出与演示环境里**不会**附带真实密钥。若你曾把 DeepSeek sk-… 写进本机 config/config.jsonc，或该文件曾被复制到可分享目录：

1. 打开 [DeepSeek 开放平台控制台](https://platform.deepseek.com/)（或你实际使用的供应商控制台）。
2. **作废 / 轮换**旧 key，创建新 key。
3. 只把新 key 写回本机 config/config.jsonc → llm.api_key（该文件已在 .gitignore，**不要** git add）。
4. 重启阅稿服务后再用校对 / 总结。

机器人无法替你登录控制台轮换。详见 [SECURITY.md](SECURITY.md)。
