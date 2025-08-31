import React, { useRef, useState, useEffect } from 'react'
import Editor from '@monaco-editor/react'

type Msg = { role: 'user' | 'assistant'; content: string }

const defaultCode = `# 你可以在这里写 Python 代码，然后点击“运行”查看结果
# 例如：
def fib(n):
    return 1 if n <= 2 else fib(n-1) + fib(n-2)

print("fib(10) =", fib(10))
`

export default function App() {
  // —— 全局注入样式：彻底取消页面滚动，仅允许内部容器滚动 ——
  useEffect(() => {
    const style = document.createElement('style')
    style.innerHTML = `
      html, body, #root { height: 100%; margin: 0; overflow: hidden; }
      * { box-sizing: border-box; }
    `
    document.head.appendChild(style)
    return () => document.head.removeChild(style)
  }, [])

  const [messages, setMessages] = useState<Msg[]>([
    { role: 'assistant', content: '你好！我是一名编程教学助手，右侧可以和我聊天，左侧可以直接写 Python 代码并运行～' }
  ])
  const [input, setInput] = useState('请帮我解释一下递归函数的时间复杂度。')
  const [busy, setBusy] = useState(false)               // 统一的忙碌状态（运行/聊天）
  const [code, setCode] = useState(defaultCode)
  const [output, setOutput] = useState('')
  const chatScrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = chatScrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages])

  // —— 运行 Python 代码（后端 /api/run-python） ——
  const runCode = async () => {
    setOutput('正在运行...\n')
    try {
      const resp = await fetch('http://localhost:8787/api/run-python', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code })
      })
      if (!resp.ok) throw new Error(resp.statusText)
      const data = await resp.json()
      setOutput(data.error ? data.error : (data.output || ''))
    } catch (e: any) {
      setOutput('运行出错：' + e.message)
    }
  }

  // —— 发送消息到聊天（后端 /api/chat，流式） ——
  const send = async () => {
    if (!input.trim()) return
    const nextMsgs = [...messages, { role: 'user', content: input }]
    setMessages(nextMsgs)
    setInput('')
    setBusy(true)

    try {
      const resp = await fetch('http://localhost:8787/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: nextMsgs })
      })
      if (!resp.ok) throw new Error(resp.statusText)

      const reader = resp.body!.getReader()
      const decoder = new TextDecoder()
      let assistant = ''
      setMessages(m => [...m, { role: 'assistant', content: '' }])

      let doneOuter = false
      while (!doneOuter) {
        const { value, done } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value)
        const lines = chunk.split('\n\n').filter(Boolean)
        for (const line of lines) {
          if (!line.startsWith('data:')) continue
          const data = line.slice(5).trim()
          if (data === '[DONE]') { doneOuter = true; break }
          try {
            const obj = JSON.parse(data)
            if (obj.delta) {
              assistant += obj.delta
              setMessages(m => {
                const copy = [...m]
                const last = copy[copy.length - 1]
                if (last?.role === 'assistant') last.content = assistant
                return copy
              })
            }
          } catch {}
        }
      }
    } catch (e: any) {
      setMessages(m => [...m, { role: 'assistant', content: '调用后端出错：' + e.message }])
    } finally {
      setBusy(false)
    }
  }

  return (
    // 最外层：固定在视口，禁止页面滚动，内部各区自己滚动
    <div
      style={{
        position: 'fixed',
        inset: 0,
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        overflow: 'hidden',     // 关键：不让内容把页面撑高
        background: '#fff'
      }}
    >
      {/* 左侧：代码编辑 + 输出（自身不滚动，由内部控制） */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          borderRight: '1px solid #eee',
          minHeight: 0,
          height: '100%',
          overflow: 'hidden'    // 关键：左列不把父容器撑出滚动
        }}
      >
        {/* 编辑器区：顶部工具条 + 可伸缩编辑器 */}
        <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
          <div style={{ padding: 8, display: 'flex', gap: 8, alignItems: 'center', borderBottom: '1px solid #eee', flexShrink: 0 }}>
            <strong>代码编辑区（Python）</strong>
            <button onClick={runCode} disabled={busy}>运行</button>
          </div>
          <div style={{ flex: 1, minHeight: 0 }}>
            <Editor
              height="100%"
              defaultLanguage="python"
              theme="vs-dark"
              value={code}
              onChange={(v) => setCode(v ?? '')}
              options={{ fontSize: 14, minimap: { enabled: false } }}
            />
          </div>
        </div>

        {/* 输出区固定高度，内部可滚动 */}
        <div style={{ display: 'flex', flexDirection: 'column', borderTop: '1px solid #eee', height: 200, flexShrink: 0 }}>
          <div style={{ padding: '6px 8px', borderBottom: '1px solid #eee', background: '#fafafa' }}>运行输出</div>
          <div style={{ flex: 1, padding: 8, background: 'black', color: 'white', whiteSpace: 'pre-wrap', overflowY: 'auto' }}>
            {output}
          </div>
        </div>
      </div>

      {/* 右侧：Chatbot（右列自己的滚动条） */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          minHeight: 0,
          height: '100%',
          overflow: 'hidden'      // 关键：右列本身不产生页面滚动
        }}
      >
        {/* 消息区：独立滚动 */}
        <div
          ref={chatScrollRef}
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',    // 关键：右侧的滚动条在这里！
            padding: 12
          }}
        >
          {messages.map((m, i) => (
            <div key={i} style={{ whiteSpace: 'pre-wrap', marginBottom: 12 }}>
              <div style={{ fontSize: 12, opacity: 0.6 }}>{m.role === 'user' ? '你' : '助手'}</div>
              <div>{m.content}</div>
            </div>
          ))}
          {busy && <div style={{ opacity: 0.6 }}>模型思考中…</div>}
        </div>

        {/* 输入区固定在底部，不参与滚动 */}
        <div style={{ padding: 12, borderTop: '1px solid #eee', display: 'flex', gap: 8, flexShrink: 0 }}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) send() }}
            placeholder="向编程助手提问…"
            style={{ flex: 1, padding: '8px 10px' }}
          />
          <button onClick={send} disabled={busy || !input.trim()}>发送</button>
        </div>
      </div>
    </div>
  )
}




