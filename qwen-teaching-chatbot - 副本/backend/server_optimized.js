// backend/server.js
import express from "express";
import morgan from "morgan";
import cors from "cors";
import dotenv from "dotenv";
import { OpenAI } from "openai";
import { spawn } from "child_process";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

dotenv.config();
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
app.use(cors());
app.use(express.json());
app.use(morgan("dev"));

const PORT = process.env.PORT || 8787;

// OpenAI 客户端
const client = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
  baseURL: process.env.OPENAI_BASE_URL,
});

// 系统提示词 & 元数据
let SYSTEM_PROMPT = `
你是一个专业的编程教学助手，专门帮助学生学习编程和调试代码。
你的职责：
1. 分析学生提交的代码，找出错误
2. 用清晰易懂的语言解释错误原因
3. 引导学生思考如何修正，而不是直接给出完整答案
4. 提供相关的学习建议和最佳实践
输出格式要求：
- 首先标注错误位置
- 解释错误的原因和影响
- 提供修正的思路和建议
- 鼓励学生独立思考
`;
let promptMetadata = { version: "default", timestamp: new Date().toISOString(), score: 0, source: "manual" };

// 🆕 错误代码生成提示词
let ERROR_GENERATION_PROMPT = `你是一名编程教学助手。
请生成一段带有明显错误的 Python 代码，满足以下要求：
1. 代码本体（包括变量名、函数名、字符串内容、打印输出等）必须全为英文或数字，不能包含任何中文或全角字符。
2. 代码中必须包含中文注释（# 开头），用简短自然的中文解释代码的意图。
3. 代码应能被 Python 解释器运行（尽管有错误），结构完整。
4. 输出格式严格为 JSON：{"code": "...", "tip": "..."}
5. "tip" 字段用简短中文（≤50字）说明错误类型和严重等级。
6. 不要在代码中使用中文字符串、中文变量名、或中文函数名。
7. 不要在 JSON 外输出任何其他文字或说明。
`;

let errorPromptMetadata = { version: "default", timestamp: new Date().toISOString(), score: 0, source: "manual" };

// 加载优化后的系统提示词
function loadOptimizedPrompt() {
  try {
    const resultsDir = path.join(__dirname, "../results");
    if (!fs.existsSync(resultsDir)) return false;

    const files = fs
      .readdirSync(resultsDir)
      .filter(f => f.startsWith("system_prompt_") && f.endsWith(".txt"))
      .sort()
      .reverse();
    if (files.length === 0) return false;

    const latestPromptFile = files[0];
    const promptPath = path.join(resultsDir, latestPromptFile);
    SYSTEM_PROMPT = fs.readFileSync(promptPath, "utf-8");

    const jsonFile = latestPromptFile.replace("system_prompt_", "optimized_prompt_").replace(".txt", ".json");
    const jsonPath = path.join(resultsDir, jsonFile);
    if (fs.existsSync(jsonPath)) {
      const metadata = JSON.parse(fs.readFileSync(jsonPath, "utf-8"));
      promptMetadata = {
        version: latestPromptFile.replace("system_prompt_", "").replace(".txt", ""),
        timestamp: metadata.timestamp || new Date().toISOString(),
        score: metadata.score || 0,
        source: "optimized",
        metrics: metadata.metrics || {}
      };
    }
    console.log(`✅ 已加载优化提示词: ${latestPromptFile}`);
    return true;
  } catch (error) {
    console.error("❌ 加载优化提示词失败:", error.message);
    return false;
  }
}

// 🆕 加载优化后的错误生成提示词
function loadOptimizedErrorPrompt() {
  try {
    const errorResultsDir = path.join(__dirname, "../results/error_generation");
    if (!fs.existsSync(errorResultsDir)) return false;

    const files = fs
      .readdirSync(errorResultsDir)
      .filter(f => f.startsWith("error_generation_prompt_") && f.endsWith(".txt"))
      .sort()
      .reverse();
    if (files.length === 0) return false;

    const latestPromptFile = files[0];
    const promptPath = path.join(errorResultsDir, latestPromptFile);
    ERROR_GENERATION_PROMPT = fs.readFileSync(promptPath, "utf-8");

    const jsonFile = latestPromptFile.replace("error_generation_prompt_", "optimized_error_prompt_").replace(".txt", ".json");
    const jsonPath = path.join(errorResultsDir, jsonFile);
    if (fs.existsSync(jsonPath)) {
      const metadata = JSON.parse(fs.readFileSync(jsonPath, "utf-8"));
      errorPromptMetadata = {
        version: latestPromptFile.replace("error_generation_prompt_", "").replace(".txt", ""),
        timestamp: metadata.timestamp || new Date().toISOString(),
        score: metadata.score || 0,
        source: "optimized",
        metrics: metadata.metrics || {}
      };
    }
    console.log(`✅ 已加载优化错误生成提示词: ${latestPromptFile} (得分: ${errorPromptMetadata.score.toFixed(4)})`);
    return true;
  } catch (error) {
    console.error("❌ 加载优化错误生成提示词失败:", error.message);
    return false;
  }
}

// 启动时加载优化提示词
console.log("\n🚀 初始化系统提示词...");
loadOptimizedPrompt();
loadOptimizedErrorPrompt();

// ---------------- 聊天接口（流式 + 系统提示词，回答限制约 500 字） ----------------
app.post("/api/chat", async (req, res) => {
  try {
    const { messages, model, temperature, max_tokens } = req.body || {};
    const chosenModel = model || process.env.QWEN_MODEL || "qwen-plus";

    const messagesWithSystem = [
      { role: "system", content: SYSTEM_PROMPT },
      ...messages
    ];

    const completion = await client.chat.completions.create({
      model: chosenModel,
      messages: messagesWithSystem,
      temperature: temperature ?? 0.6,
      max_tokens: max_tokens ?? 1500,
      stream: true
    });

    res.setHeader("Content-Type", "text/event-stream; charset=utf-8");
    res.setHeader("Cache-Control", "no-cache");
    res.setHeader("Connection", "keep-alive");

    let assistant = "";
    for await (const chunk of completion) {
      const delta = chunk.choices?.[0]?.delta?.content;
      if (delta) {
        assistant += delta;
        res.write(`data: ${JSON.stringify({ delta })}\n\n`);
      }
    }

    res.write("data: [DONE]\n\n");
    res.end();
  } catch (err) {
    console.error("Chat API error:", err);
    res.status(500).json({ error: err.message || "Chat API error" });
  }
});

// ---------------- Python运行接口 ----------------
app.post("/api/run-python", async (req, res) => {
  const { code } = req.body;
  if (!code) return res.status(400).json({ error: "No code provided" });

  const py = spawn("python", ["-c", code]);
  let result = "";
  let error = "";

  py.stdout.on("data", (data) => { result += data.toString(); });
  py.stderr.on("data", (data) => { error += data.toString(); });
  py.on("close", () => {
    if (error) res.json({ error });
    else res.json({ output: result });
  });
});

// ---------------- 错误代码生成（改写版） ----------------
app.post("/api/generate-error", async (req, res) => {
  try {
    const { level = "中等", type = "语法错误" } = req.body || {};
    const chosenModel = process.env.QWEN_MODEL || "qwen-plus";

    // 将系统提示词和用户请求合并成一个完整 prompt
    const fullPrompt = `
你是一名专业的编程教学助手。
生成一段含错误的 Python 代码，要求：
1. 错误等级: ${level}
2. 错误类型: ${type}
3. 代码可直接运行，带中文注释
4. 同时生成一条 ≤50字提示，说明错误类型和等级
请严格输出 **纯 JSON**，格式如下：
{"code": "...", "tip": "..."}
⚠️ 不要输出 Markdown、换行或多余文字
`;

    // 调用 OpenAI 接口
    const completion = await client.chat.completions.create({
      model: chosenModel,
      messages: [{ role: "user", content: fullPrompt }],
      temperature: 0.7,
      max_tokens: 500,
      stream: false
    });

    const respText = completion.choices?.[0]?.message?.content || "";

    let parsed = { code: "", tip: "" };
    try {
      // 直接解析 JSON
      parsed = JSON.parse(respText);
    } catch (err) {
      console.error("❌ JSON解析失败:", err);
      // 解析失败时，返回完整文本，避免截断
      parsed = {
        code: `# 生成失败，请重试\n# 原始响应:\n${respText.substring(0, 500)}`,
        tip: `${level} ${type}（JSON解析失败）`
      };
    }

    // 返回接口，Node 会自动进行安全转义
    res.json(parsed);

  } catch (err) {
    console.error("Generate-error failed:", err);
    res.status(500).json({ error: err.message || "Generate error API failed" });
  }
});


// ---------------- 分析代码功能 ----------------
app.post("/api/analyze-code", async (req, res) => {
  try {
    const { code } = req.body;
    if (!code) return res.status(400).json({ error: "No code provided" });

    // 先尝试运行代码，判断是否有语法或运行错误
    const py = spawn("python", ["-c", code]);
    let output = "";
    let error = "";

    py.stdout.on("data", (data) => { output += data.toString(); });
    py.stderr.on("data", (data) => { error += data.toString(); });

    py.on("close", async () => {
      // 生成分析提示词
      const analysisPrompt = `
你是一名专业的编程教学助手。
分析下面这段 Python 代码：
代码内容：
${code}

要求：
1. 先判断代码是否存在错误，如果有，请指出错误类型和位置。
2. 解释这段代码的功能和执行逻辑。
3. 给出改进或优化建议（如果有）。
4. 用清晰自然的语言输出。
`;

      try {
        const completion = await client.chat.completions.create({
          model: process.env.QWEN_MODEL || "qwen-plus",
          messages: [
            { role: "system", content: SYSTEM_PROMPT },
            { role: "user", content: analysisPrompt }
          ],
          temperature: 0.6,
          max_tokens: 1000,
          stream: false
        });

        const analysis = completion.choices?.[0]?.message?.content || "";
        res.json({ runtimeError: error || null, analysis, output: output || null });
      } catch (aiErr) {
        console.error("分析代码失败:", aiErr);
        res.status(500).json({ error: aiErr.message || "Analyze code failed" });
      }
    });
  } catch (err) {
    console.error("分析代码接口异常:", err);
    res.status(500).json({ error: err.message || "Analyze code API failed" });
  }
});



// ---------------- 提示词管理接口 ----------------
app.get("/api/prompt-info", (req, res) => {
  res.json({ metadata: promptMetadata, preview: SYSTEM_PROMPT.substring(0, 200) + "...", length: SYSTEM_PROMPT.length });
});

app.post("/api/optimize-prompt", async (req, res) => {
  try {
    const pythonScript = path.join(__dirname, "../../optimize_teaching_prompt.py");
    if (!fs.existsSync(pythonScript)) return res.status(404).json({ success: false, error: "优化脚本不存在" });

    const pyProc = spawn("python", [pythonScript], { cwd: path.join(__dirname, "../../") });
    let output = "", errorOutput = "";

    pyProc.stdout.on("data", (data) => { output += data.toString(); console.log(data.toString()); });
    pyProc.stderr.on("data", (data) => { errorOutput += data.toString(); console.error(data.toString()); });
    pyProc.on("close", (code) => {
      if (code === 0) {
        loadOptimizedPrompt();
        res.json({ success: true, message: "优化完成，已应用新提示词", metadata: promptMetadata, output: output.split("\n").slice(-20).join("\n") });
      } else {
        res.status(500).json({ success: false, error: "优化失败", code, output, errorOutput });
      }
    });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

app.post("/api/reload-prompt", (req, res) => {
  try {
    const loaded = loadOptimizedPrompt();
    if (loaded) res.json({ success: true, message: "提示词已重新加载", metadata: promptMetadata });
    else res.json({ success: false, message: "未找到优化提示词，使用默认提示词", metadata: promptMetadata });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

app.get("/api/prompt-versions", (req, res) => {
  try {
    const resultsDir = path.join(__dirname, "../../results");
    if (!fs.existsSync(resultsDir)) return res.json({ versions: [] });

    const promptFiles = fs.readdirSync(resultsDir)
      .filter(f => f.startsWith("system_prompt_") && f.endsWith(".txt"))
      .map(f => {
        const version = f.replace("system_prompt_", "").replace(".txt", "");
        const jsonFile = f.replace("system_prompt_", "optimized_prompt_").replace(".txt", ".json");
        let metadata = { version, timestamp: version };
        const jsonPath = path.join(resultsDir, jsonFile);
        if (fs.existsSync(jsonPath)) {
          try {
            const data = JSON.parse(fs.readFileSync(jsonPath, "utf-8"));
            metadata = { version, timestamp: data.timestamp, score: data.score, metrics: data.metrics };
          } catch {}
        }
        return metadata;
      }).sort((a, b) => b.version.localeCompare(a.version));
    res.json({ versions: promptFiles, current: promptMetadata.version });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post("/api/switch-prompt", (req, res) => {
  try {
    const { version } = req.body;
    if (!version) return res.status(400).json({ error: "缺少version参数" });

    const resultsDir = path.join(__dirname, "../../results");
    const promptFile = `system_prompt_${version}.txt`;
    const promptPath = path.join(resultsDir, promptFile);
    if (!fs.existsSync(promptPath)) return res.status(404).json({ error: "提示词版本不存在" });

    SYSTEM_PROMPT = fs.readFileSync(promptPath, "utf-8");
    const jsonFile = `optimized_prompt_${version}.json`;
    const jsonPath = path.join(resultsDir, jsonFile);
    if (fs.existsSync(jsonPath)) {
      const metadata = JSON.parse(fs.readFileSync(jsonPath, "utf-8"));
      promptMetadata = { version, timestamp: metadata.timestamp, score: metadata.score, source: "optimized", metrics: metadata.metrics };
    } else {
      promptMetadata = { version, timestamp: new Date().toISOString(), score: 0, source: "optimized" };
    }

    console.log(`✅ 已切换到提示词版本: ${version}`);
    res.json({ success: true, message: `已切换到版本 ${version}`, metadata: promptMetadata });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// ---------------- 健康检查 ----------------
app.get("/health", (_req, res) => {
  res.json({ ok: true, prompt: { version: promptMetadata.version, source: promptMetadata.source, score: promptMetadata.score } });
});

// ---------------- 启动服务 ----------------
app.listen(PORT, () => {
  console.log(`\n${"=".repeat(60)}`);
  console.log(`Backend running on http://localhost:${PORT}`);
  console.log(`当前提示词: ${promptMetadata.version} (来源: ${promptMetadata.source}, 得分: ${promptMetadata.score.toFixed(4)})`);
  console.log(`${"=".repeat(60)}\n`);
});
