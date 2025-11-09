// frontend/src/ui/App.tsx
import React, { useState, useRef, useEffect } from "react";
import Editor from "@monaco-editor/react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github.css";

type Msg = { role: "user" | "assistant"; content: string };

const defaultCode = `# 你可以在这里写 Python 代码，然后点击“运行”查看结果
def fib(n):
    return 1 if n <= 2 else fib(n-1) + fib(n-2)

print("fib(10) =", fib(10))
`;

export default function App() {
  const [messages, setMessages] = useState<Msg[]>([
    { role: "assistant", content: "你好！我是编程教学助手，右侧可以聊天，左侧可写 Python 代码～" }
  ]);
  const [input, setInput] = useState("请帮我解释一下递归函数的时间复杂度。");
  const [busy, setBusy] = useState(false);
  const [code, setCode] = useState(defaultCode);
  const [output, setOutput] = useState("");
  const [errorMode, setErrorMode] = useState(false);
  const [errorLevel, setErrorLevel] = useState("轻微");
  const [errorType, setErrorType] = useState("语法错误");
  const chatScrollRef = useRef<HTMLDivElement>(null);

  // 保持聊天区滚动到底部
  useEffect(() => {
    const el = chatScrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  // 运行 Python 代码
  const runCode = async () => {
    setOutput("正在运行...\n");
    try {
      const resp = await fetch("http://localhost:8787/api/run-python", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code })
      });
      if (!resp.ok) throw new Error(resp.statusText);
      const data = await resp.json();
      setOutput(data.error ? data.error : data.output || "");
    } catch (e: any) {
      setOutput("运行出错：" + e.message);
    }
  };

  // 分析代码功能
  const analyzeCode = async () => {
    setBusy(true);
    try {
      const resp = await fetch("http://localhost:8787/api/analyze-code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code })
      });
      if (!resp.ok) throw new Error(resp.statusText);
      const data = await resp.json();

      let msg = "";
      if (data.runtimeError) msg += `运行错误:\n${data.runtimeError}\n\n`;
      if (data.output) msg += `输出结果:\n${data.output}\n\n`;
      if (data.analysis) msg += `代码分析:\n${data.analysis}`;

      setMessages((m) => [...m, { role: "assistant", content: msg }]);
    } catch (e: any) {
      setMessages((m) => [...m, { role: "assistant", content: "分析出错：" + e.message }]);
    } finally {
      setBusy(false);
    }
  };

  // 发送聊天消息
  const send = async () => {
    if (!input.trim()) return;
    const nextMsgs = [...messages, { role: "user", content: input }];
    setMessages(nextMsgs);
    setInput("");
    setBusy(true);

    try {
      const resp = await fetch("http://localhost:8787/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: nextMsgs, max_tokens: 500 })
      });
      if (!resp.ok) throw new Error(resp.statusText);

      const reader = resp.body!.getReader();
      const decoder = new TextDecoder();
      let assistant = "";
      setMessages((m) => [...m, { role: "assistant", content: "" }]);

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        const lines = chunk.split("\n\n").filter(Boolean);
        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          const dataStr = line.slice(5).trim();
          if (dataStr === "[DONE]") break;
          try {
            const obj = JSON.parse(dataStr);
            if (obj.delta) {
              assistant += obj.delta;
              setMessages((m) => {
                const copy = [...m];
                const last = copy[copy.length - 1];
                if (last?.role === "assistant") last.content = assistant;
                return copy;
              });
            }
          } catch {}
        }
      }
    } catch (e: any) {
      setMessages((m) => [...m, { role: "assistant", content: "调用后端出错：" + e.message }]);
    } finally {
      setBusy(false);
    }
  };

  // 生成错误代码
  const generateErrorCode = async () => {
    setBusy(true);
    try {
      const resp = await fetch("http://localhost:8787/api/generate-error", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ level: errorLevel, type: errorType })
      });
      if (!resp.ok) throw new Error(resp.statusText);

      const data = await resp.json();
      setCode(data.code || "");
      if (data.tip) setMessages((m) => [...m, { role: "assistant", content: data.tip }]);
    } catch (e: any) {
      alert("生成出错：" + e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ position: "fixed", inset: 0, display: "grid", gridTemplateColumns: "1fr 1fr", overflow: "hidden", background: "#fff" }}>
      {/* 左侧代码区 */}
      <div style={{ display: "flex", flexDirection: "column", borderRight: "1px solid #eee", minHeight: 0, height: "100%", overflow: "hidden" }}>
        <div style={{ padding: 8, display: "flex", gap: 8, alignItems: "center", borderBottom: "1px solid #eee", flexShrink: 0, flexWrap: "wrap" }}>
          <strong>代码编辑区（Python）</strong>
          <button onClick={() => setErrorMode((v) => !v)} disabled={busy}>
            {errorMode ? "关闭错误模式" : "开启错误模式"}
          </button>
          {errorMode && (
            <>
              <label>
                错误等级：
                <select value={errorLevel} onChange={(e) => setErrorLevel(e.target.value)} style={{ marginLeft: 4 }}>
                  <option value="轻微">轻微</option>
                  <option value="中等">中等</option>
                  <option value="严重">严重</option>
                </select>
              </label>
              <label>
                错误类型：
                <select value={errorType} onChange={(e) => setErrorType(e.target.value)} style={{ marginLeft: 4 }}>
                  <option value="语法错误">语法错误</option>
                  <option value="逻辑错误">逻辑错误</option>
                  <option value="内容错误">内容错误</option>
                </select>
              </label>
              <button onClick={generateErrorCode} disabled={busy}>生成错误代码</button>
            </>
          )}
          <button onClick={runCode} disabled={busy}>运行</button>
          <button onClick={analyzeCode} disabled={busy}>分析代码</button>
        </div>

        <div style={{ flex: 1, minHeight: 0 }}>
          <Editor
            height="100%"
            defaultLanguage="python"
            theme="vs-dark"
            value={code}
            onChange={(v) => setCode(v ?? "")}
            options={{ fontSize: 14, minimap: { enabled: false } }}
          />
        </div>

        <div style={{ display: "flex", flexDirection: "column", borderTop: "1px solid #eee", height: 200, flexShrink: 0 }}>
          <div style={{ padding: "6px 8px", borderBottom: "1px solid #eee", background: "#fafafa" }}>运行输出</div>
          <div style={{ flex: 1, padding: 8, background: "black", color: "white", whiteSpace: "pre-wrap", overflowY: "auto" }}>{output}</div>
        </div>
      </div>

      {/* 右侧聊天区 */}
      <div style={{ display: "flex", flexDirection: "column", minHeight: 0, height: "100%", overflow: "hidden" }}>
        <div ref={chatScrollRef} style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: 12 }}>
          {messages.map((m, i) => (
            <div key={i} style={{ whiteSpace: "pre-wrap", marginBottom: 12 }}>
              <div style={{ fontSize: 12, opacity: 0.6 }}>{m.role === "user" ? "你" : "助手"}</div>
              <div style={{ padding: "6px 10px", background: m.role === "assistant" ? "#f7f7f7" : "transparent", borderRadius: 6 }}>
                <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>{m.content}</ReactMarkdown>
              </div>
            </div>
          ))}
          {busy && <div style={{ opacity: 0.6 }}>模型思考中…</div>}
        </div>

        <div style={{ padding: 12, borderTop: "1px solid #eee", display: "flex", gap: 8, flexShrink: 0 }}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) send(); }}
            placeholder="向编程助手提问…"
            style={{ flex: 1, padding: "8px 10px" }}
          />
          <button onClick={send} disabled={busy || !input.trim()}>发送</button>
        </div>
      </div>
    </div>
  );
}
