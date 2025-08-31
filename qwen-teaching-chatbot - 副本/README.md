# 本地教学 Chatbot（Qwen）+ 代码编辑/运行一体化示例

左侧是 Monaco 编辑器和 JavaScript 运行器（在安全的 iframe 中执行 JS）；
右侧是通过后端代理的 Qwen Chatbot（OpenAI 兼容接口）。

## 一、准备

1. 安装 Node.js (>=18)
2. 申请 Qwen API Key（阿里云 Model Studio）
3. 在 `backend/.env` 中填写：
   ```ini
   OPENAI_API_KEY=你的QwenKey
   OPENAI_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
   QWEN_MODEL=qwen-plus   # 可改成 qwen2.5-max、qwen3-coder-plus 等
   PORT=8787
   ```

## 二、启动步骤（两个终端）

**终端 1：后端**
```bash
cd backend
npm i
cp .env.example .env   # 然后编辑 .env，填入你的 Key
npm run dev            # 默认 http://localhost:8787
```

**终端 2：前端**
```bash
cd frontend
npm i
npm run dev            # 默认 http://localhost:5173
```

前端 dev 服务器已配置代理到 `http://localhost:8787/api`。

## 三、常见问题

- **401/403**：检查 `OPENAI_API_KEY` 是否正确、账户是否开通国际站；
- **模型名错误**：更换 `QWEN_MODEL`，如 `qwen-plus`、`qwen2.5-max`、`qwen3-coder-plus`；
- **无法联网**：此项目仅本地运行，后端会直接请求 Qwen API，需要机器可以访问外网。

## 四、扩展点（可选）

- 将 JS 运行器替换/并行集成 Pyodide 支持 Python；
- 给 Chatbot 增加“读取左侧代码”的上下文，将编辑器代码一并作为系统提示或工具输入；
- 接入函数调用（function calling）让模型帮忙“运行单元测试”“生成样例”等。
