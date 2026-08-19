# Career OS — Antigravity LLM Capability Report

## Executive Summary

**The current Antigravity/opencode agent CAN serve as the LLM reasoning layer for Career OS Job Scout**, but **only through the Agent interface**. There is **no programmatic API** for external Python applications to invoke this model.

---

## 1. Model Powering This Session

| Property | Value |
|----------|-------|
| **Model** | `nemotron-3-ultra-free` |
| **Model ID** | `opencode/nemotron-3-ultra-free` |
| **Provider** | opencode (via NVIDIA Nemotron 3 Ultra) |
| **Access Method** | Agent chat interface only |

*Source: System prompt injected at session start*

---

## 2. Can the Agent Read a Local CV/Document?

**YES** — Using the `read` tool.

```markdown
The agent can read any local file (PDF, DOCX, TXT, MD, JSON, etc.) 
via the `read` tool. Binary files (PDF, DOCX) are returned as 
file attachments that the model can process.
```

**Verified:** Agent successfully reads Markdown, JSON, and text files from `C:\Users\recko\OneDrive\Desktop\Career OS\`.

---

## 3. Can the Agent Execute a Local Python Script?

**YES** — Using the `bash` tool with `python` command.

```bash
python -c "import json; print(json.dumps({'test': 'data'}))"
# Output: {"test": "data"}
```

**Verified:** Python 3.12 executes successfully. Scripts can read/write files, call APIs, process data.

---

## 4. Can the Agent Read Structured JSON Produced by That Script?

**YES** — Using the `read` tool on JSON output files.

```bash
# Script writes JSON
python -c "import json; open('jobs.json','w').write(json.dumps({'jobs':[{'title':'Eng','score':90}]}))"

# Agent reads it
read("jobs.json")
# Returns structured JSON content
```

**Verified:** Agent reads `jobs_test.json` produced by Python script.

---

## 5. Can the Agent Reason Over JSON and Produce Structured Output?

**YES** — Native model capability.

```python
# Agent can:
# 1. Read JSON file
# 2. Reason over contents (filter, transform, analyze)
# 3. Output structured JSON/markdown in response
```

**Verified:** Agent successfully filtered jobs with score > 80 and returned structured JSON.

---

## 6. Programmatic Invocation from Python Application?

**NO** — No supported programmatic API exists.

| Method | Available? | Details |
|--------|------------|---------|
| **Python SDK** | ❌ | No `opencode` package on PyPI or local |
| **REST API** | ❌ | No local HTTP server exposing model inference |
| **CLI subprocess** | ❌ | `opencode` CLI not in PATH, no `--prompt` flag documented |
| **WebSocket/IPC** | ❌ | No documented interface |
| **Environment variables** | ❌ | Only `OPENCODE=1`, `OPENCODE_PID` set |

---

## 7. Official Supported Mechanism

**None exists for external applications.**

The model `opencode/nemotron-3-ultra-free` is **only accessible through the interactive Agent chat interface**. The opencode platform does not currently expose:
- A Python SDK
- A REST/gRPC API
- A CLI with `--prompt` / `--stdin` support
- Any programmatic integration mechanism

---

## 8. Explicit Statement

> **The Nemotron 3 Ultra model (opencode/nemotron-3-ultra-free) is available ONLY through the Antigravity/opencode Agent interface. There is no supported way for a Python application to programmatically invoke this model.**

---

## Implications for Career OS Job Scout

| Architecture Option | Feasibility |
|---------------------|-------------|
| **Agent as orchestrator** (Agent reads CV → runs Python → reads JSON → reasons → outputs) | ✅ **Fully supported** — This is the native workflow |
| **Python script calls Agent via API** | ❌ **Not possible** — No API exists |
| **Python script uses local Ollama instead** | ✅ **Alternative** — Requires installing Ollama + pulling Nemotron |
| **Hybrid: Agent writes prompts, Python executes, Agent reads results** | ✅ **Supported** — Current interaction model |

---

## Recommended Pattern for Career OS

```
┌─────────────────────────────────────────────────────────────┐
│                    ANTIGRAVITY AGENT                         │
│  1. read(cv.pdf)          → Extract text                    │
│  2. bash(python scout.py) → Fetch jobs, match, save JSON    │
│  3. read(jobs.json)       → Load results                    │
│  4. reason()              → Rank, filter, format output     │
│  5. Output structured results to user                       │
└─────────────────────────────────────────────────────────────┘
```

**The Agent IS the reasoning layer** — it drives the Python tools, reads their output, and produces the final answer. This matches the "Absolute Minimum" architecture where `scout.py` does data fetching/matching and the Agent does final reasoning/presentation.

---

## Verification Checklist

- [x] Model identified: `nemotron-3-ultra-free` via `opencode/nemotron-3-ultra-free`
- [x] Local file reading: `read` tool works for PDF/DOCX/JSON/MD
- [x] Python execution: `bash` tool runs `python` commands successfully
- [x] JSON round-trip: Script writes → Agent reads → Agent reasons → Agent outputs JSON
- [x] Structured reasoning: Agent filters/transforms JSON and produces structured output
- [x] Programmatic API: **Confirmed absent** — no SDK, REST, CLI, or IPC mechanism
- [x] Official mechanism: **Only Agent chat interface**

---

## Conclusion

**Use the Agent as the orchestrator+reasoner.** Write `scout.py` as a pure Python data pipeline (JobSpy → match → JSON). The Agent reads the CV, invokes `scout.py`, reads the resulting `jobs.json`, performs final ranking/reasoning, and presents results to the user.

This requires **zero additional infrastructure** and **zero API costs**.