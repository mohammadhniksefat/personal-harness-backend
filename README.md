# Personal Harness Backend

A local-first AI agent harness built with **FastAPI** and designed to connect an OpenAI-compatible LLM endpoint to a controlled set of local tools.

The backend is responsible for the agent loop, conversation state, tool execution, approvals, persistence, streaming events, cancellation, and communication with the local language model.

> **Status:** MVP / active development

## Overview

Personal Harness is an experimental agent runtime for running an AI assistant against a local Windows environment.

The core loop is:

```text
User
  │
  ▼
FastAPI API
  │
  ▼
Agent Runtime
  │
  ├── Conversation history
  ├── Long-term memory
  ├── Tool definitions
  ├── Execution limits
  ├── Approval policy
  │
  ▼
OpenAI-compatible LLM
  │
  ├── Final response
  │
  └── Tool call
        │
        ▼
   Tool Registry
        │
        ├── terminal
        ├── file_read
        ├── file_write
        ├── calculator
        ├── datetime
        ├── system_info
        └── clipboard
        │
        ▼
   Tool result
        │
        ▼
   LLM continues
        │
        ▼
   Final response
```

The backend currently supports one structured tool call per model turn and limits the total number of tool executions for a run.

## Features

* Local LLM integration through an OpenAI-compatible `/chat/completions` API
* Agent execution loop
* Streaming assistant responses
* Server-Sent Events (SSE)
* Persistent chat sessions
* Persistent conversation messages
* Long-term key/value memory
* Tool execution tracking
* User approval for sensitive operations
* Run cancellation
* Configurable execution limits
* Configurable context limit
* Workspace sandboxing for file operations
* Windows PowerShell terminal execution
* Tool risk classification
* SQLite persistence
* CORS support for the frontend

## Technology Stack

* Python
* FastAPI
* Uvicorn
* SQLAlchemy 2
* Pydantic 2
* Pydantic Settings
* HTTPX
* SQLite
* OpenAI-compatible LLM API

The current dependency versions are defined in `requirements.txt`.

## Project Structure

```text
personal-harness-backend/
│
├── app/
│   ├── api/
│   │   └── routes.py
│   │
│   ├── core/
│   │   └── config.py
│   │
│   ├── db/
│   │   ├── database.py
│   │   └── models.py
│   │
│   ├── services/
│   │   ├── agent.py
│   │   └── llm.py
│   │
│   ├── tools/
│   │   └── registry.py
│   │
│   └── main.py
│
├── .env.example
├── requirements.txt
└── ...
```

The current application separates HTTP/API handling, agent orchestration, LLM communication, database access, and tool registration.

## Requirements

* Python 3.10+
* Windows
* A locally running OpenAI-compatible LLM server
* PowerShell
* SQLite

The harness is designed around a local model endpoint. The default configuration is compatible with **LM Studio**.

## Installation

Clone the repository:

```bash
git clone https://github.com/mohammadhniksefat/personal-harness-backend.git
cd personal-harness-backend
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

Copy the example environment file:

```powershell
Copy-Item .env.example .env
```

The default configuration is:

```env
LLM_BASE_URL=http://localhost:1234/v1
LLM_API_KEY=lm-studio
LLM_MODEL=local-model

CONTEXT_LIMIT=8192
MAX_TOOL_EXECUTIONS=10
MAX_TOOL_OUTPUT_CHARS=12000

HARNESS_WORKSPACE=./workspace
DATABASE_URL=sqlite:///./data/harness.db
```

These settings control the LLM endpoint, model, context budget, execution budget, tool output size, workspace, and database location.

### Local LLM

The backend expects an OpenAI-compatible endpoint:

```text
http://localhost:1234/v1
```

The LLM client sends a request to:

```text
/v1/chat/completions
```

with:

* model
* messages
* tool definitions
* `tool_choice=auto`

The current client uses HTTPX and supports streaming through the agent service.

## Running the Server

Start the development server:

```bash
uvicorn app.main:app --reload --port 8000
```

The API will be available at:

```text
http://localhost:8000
```

Health check:

```text
GET /health
```

Expected response:

```json
{
  "status": "ok"
}
```

The application initializes the database during startup and mounts the API under `/api`.

## API

### Health

```http
GET /health
```

### Sessions

Create a session:

```http
POST /api/sessions
```

List sessions:

```http
GET /api/sessions
```

Get session messages:

```http
GET /api/sessions/{session_id}/messages
```

### Chat

Send a message:

```http
POST /api/sessions/{session_id}/chat
```

Request:

```json
{
  "message": "What files are in the workspace?"
}
```

The endpoint returns an SSE stream.

Example event:

```text
data: {"type":"run_started","run_id":"..."}

data: {"type":"assistant_delta","content":"..."}

data: {"type":"tool_requested","tool":"terminal","arguments":{...}}

data: {"type":"tool_started","execution_id":1}

data: {"type":"tool_output","execution_id":1,"data":"..."}

data: {"type":"tool_finished","execution_id":1,"status":"succeeded"}

data: {"type":"run_completed","run_id":"..."}

data: {"type":"done"}
```

The backend explicitly emits lifecycle events for agent runs, assistant output, tools, approvals, completion, failure, and cancellation.

### Memory

List memory:

```http
GET /api/memory
```

Create/update memory:

```http
POST /api/memory
```

Request:

```json
{
  "key": "preferred_editor",
  "value": "VS Code"
}
```

Memory is injected into the system context when the agent builds its messages.

### Approvals

Approve or reject an operation:

```http
POST /api/approvals/{approval_id}?action=approve
```

or:

```http
POST /api/approvals/{approval_id}?action=reject
```

### Cancellation

Cancel a running agent:

```http
POST /api/runs/{run_id}/cancel
```

## Tool System

Tools are registered in:

```text
app/tools/registry.py
```

Current tools:

| Tool          | Purpose                                        | Risk   |
| ------------- | ---------------------------------------------- | ------ |
| `terminal`    | Execute policy-constrained PowerShell commands | High   |
| `file_read`   | Read UTF-8 files inside workspace              | Medium |
| `file_write`  | Write UTF-8 files inside workspace             | High   |
| `calculator`  | Evaluate basic arithmetic                      | Low    |
| `datetime`    | Get date/time for a timezone                   | Low    |
| `system_info` | Get local system information                   | Low    |
| `clipboard`   | Read/write Windows clipboard                   | Medium |

The registry exposes tool descriptions and JSON schemas to the LLM.

### Workspace Security

File operations are restricted to the configured harness workspace.

```env
HARNESS_WORKSPACE=./workspace
```

Paths outside this workspace are rejected by the path validation layer.

### Terminal Security

The terminal tool runs through PowerShell but applies a command policy.

Currently allowed command families include:

```text
dir
echo
where
whoami
hostname
ipconfig
python
py
pip
npm
node
git
```

Sensitive operations such as package installation, destructive Git operations, shutdown, deletion, and similar commands require approval.

## Agent Execution Model

Each user message creates an agent run.

Conceptually:

```text
1. Create run
2. Persist user message
3. Build conversation context
4. Send messages + tools to LLM
5. Stream assistant content
6. Inspect structured tool calls
7. Validate tool call
8. Request approval if necessary
9. Execute tool
10. Persist tool result
11. Repeat
12. Finish when model returns no tool call
```

The agent currently supports **exactly one tool call per model turn**. The total number of tool executions is bounded by `MAX_TOOL_EXECUTIONS`.

## Context Management

The agent loads:

* system instructions
* long-term memory
* recent conversation messages

The current implementation keeps the latest 30 messages when constructing the normal conversation context. If the serialized context becomes too large, it reduces the conversation passed to the model.

Configure the approximate context budget with:

```env
CONTEXT_LIMIT=8192
```

## Security Model

This project is designed as a local development harness rather than a production multi-user service.

Important protections currently include:

* Workspace path restrictions
* Terminal command allowlist
* Sensitive-command approval
* Tool execution limits
* Tool output limits
* Explicit structured tool calls
* Run cancellation
* Untrusted tool output treated as data

The agent system prompt explicitly instructs the model not to treat tool/file/database output as instructions and not to claim actions succeeded without tool confirmation.

## Development

Run the server with auto-reload:

```bash
uvicorn app.main:app --reload --port 8000
```

Useful areas when extending the project:

```text
app/api/       → HTTP/API layer
app/services/  → Agent and LLM orchestration
app/tools/     → Tool implementations and schemas
app/db/        → Persistence
app/core/      → Configuration
```

## Current Limitations

This is an MVP and intentionally has several limitations:

* One tool call per model turn
* Local LLM dependency
* Windows/PowerShell-oriented terminal implementation
* SQLite persistence
* No authentication/authorization layer
* No production deployment configuration
* Database query tool is currently disabled
* Tool execution is synchronous within the agent loop
* Approval handling is currently polling-based
* No multi-agent architecture
* No distributed run management

## Roadmap

Potential future improvements include:

* Robust structured-output validation
* Better tool-call recovery
* Parallel tool execution
* Improved context management
* Token-aware context budgeting
* Tool timeout policies
* Better approval policies
* Richer event types
* Authentication
* Multi-user isolation
* Production database support
* Persistent run state
* Better observability
* Test suite
* WebSocket/SSE reliability improvements
* Plugin-based tool system
* MCP integration
* Background task execution

## Related Repository

Frontend:

https://github.com/mohammadhniksefat/personal-harness-frontend

## License

No license is currently specified in the repository.
