import express from "express";
import morgan from "morgan";
import cors from "cors";
import dotenv from "dotenv";
import { OpenAI } from "openai";
import { spawn } from "child_process";

dotenv.config();

const app = express();
app.use(cors());
app.use(express.json());
app.use(morgan("dev"));

const PORT = process.env.PORT || 8787;

// OpenAI (Qwen兼容模式)
const client = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
  baseURL: process.env.OPENAI_BASE_URL,
});

// 聊天接口
app.post("/api/chat", async (req, res) => {
  try {
    const { messages, model, temperature, max_tokens } = req.body || {};
    const chosenModel = model || process.env.QWEN_MODEL || "qwen-plus";

    const completion = await client.chat.completions.create({
      model: chosenModel,
      messages,
      temperature: temperature ?? 0.6,
      max_tokens: max_tokens ?? 1024,
      stream: true,
    });

    res.setHeader("Content-Type", "text/event-stream");
    res.setHeader("Cache-Control", "no-cache");
    res.setHeader("Connection", "keep-alive");

    for await (const chunk of completion) {
      const delta = chunk.choices?.[0]?.delta?.content;
      if (delta) {
        res.write(`data: ${JSON.stringify({ delta })}\n\n`);
      }
    }
    res.write("data: [DONE]\n\n");
    res.end();
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message || "Chat API error" });
  }
});

// Python运行接口
app.post("/api/run-python", async (req, res) => {
  const { code } = req.body;
  if (!code) return res.status(400).json({ error: "No code provided" });

  const py = spawn("python", ["-c", code]); // 如果系统命令是 python3，请改成 "python3"
  let result = "";
  let error = "";

  py.stdout.on("data", (data) => {
    result += data.toString();
  });
  py.stderr.on("data", (data) => {
    error += data.toString();
  });

  py.on("close", () => {
    if (error) {
      res.json({ error });
    } else {
      res.json({ output: result });
    }
  });
});

// 健康检查
app.get("/health", (_req, res) => {
  res.json({ ok: true });
});

app.listen(PORT, () => {
  console.log(`Backend running on http://localhost:${PORT}`);
});
