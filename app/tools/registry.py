import asyncio, ast, operator, os, platform, subprocess, uuid
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from app.core.config import settings


class ToolError(Exception):
    pass


def safe_path(p):
    root = Path(settings.harness_workspace).resolve()
    target = (root / p).resolve() if not Path(p).is_absolute() else Path(p).resolve()
    if root != target and root not in target.parents:
        raise ToolError("Path is outside the configured harness workspace")
    return target


SAFE_CMDS = {
    "dir",
    "echo",
    "where",
    "whoami",
    "hostname",
    "ipconfig",
    "python",
    "py",
    "pip",
    "npm",
    "node",
    "git",
}
SENSITIVE_PREFIXES = (
    "git clean",
    "git reset",
    "shutdown",
    "taskkill",
    "format",
    "del ",
    "remove-item",
    "set-itemproperty",
)


def terminal(args, cancel_event):
    command = args["command"].strip()
    first = command.split()[0].lower() if command else ""
    if first not in SAFE_CMDS:
        raise ToolError(f"Command not allowed by terminal policy: {first}")
    sensitive = any(command.lower().startswith(x) for x in SENSITIVE_PREFIXES)
    if sensitive:
        raise ToolError(
            "APPROVAL_REQUIRED: This terminal command is classified as sensitive."
        )
    proc = subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=settings.harness_workspace,
    )
    while True:
        if cancel_event.is_set():
            proc.kill()
            raise ToolError("CANCELLED_BY_USER")
        line = proc.stdout.readline()
        if line:
            yield line
        elif proc.poll() is not None:
            break
    if proc.returncode:
        raise ToolError(f"Command exited with code {proc.returncode}")


def file_read(args, cancel_event):
    return safe_path(args["path"]).read_text(encoding="utf-8")[
        : settings.max_tool_output_chars
    ]


def file_write(args, cancel_event):
    p = safe_path(args["path"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(args["content"], encoding="utf-8")
    return f"Wrote {p.relative_to(Path(settings.harness_workspace).resolve())}"


def calculator(args, cancel_event):
    allowed = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
    }

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in allowed:
            return allowed[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in allowed:
            return allowed[type(n.op)](ev(n.operand))
        raise ToolError("Unsupported calculator expression")

    return str(ev(ast.parse(args["expression"], mode="eval")))


def datetime_tool(args, cancel_event):
    return datetime.now(ZoneInfo(args.get("timezone", "UTC"))).isoformat()


def system_info(args, cancel_event):
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cwd": os.getcwd(),
    }


def clipboard(args, cancel_event):
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        if args["operation"] == "write":
            root.clipboard_clear()
            root.clipboard_append(args["text"])
            root.update()
            return "Clipboard updated."
        root.update()
        return root.clipboard_get()
    finally:
        root.destroy()


def database_query(args, cancel_event):
    # MVP deliberately exposes a separate safe read-only DB API rather than arbitrary SQL.
    raise ToolError(
        "Database query tool is intentionally disabled until an explicit safe-query adapter is configured."
    )


TOOLS = {
    "terminal": {
        "description": "Run an approved, policy-constrained PowerShell command in the harness workspace.",
        "schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
        "risk": "high",
        "fn": terminal,
    },
    "file_read": {
        "description": "Read a UTF-8 text file inside the harness workspace.",
        "schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        "risk": "medium",
        "fn": file_read,
    },
    "file_write": {
        "description": "Write UTF-8 text to a file inside the harness workspace.",
        "schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
        "risk": "high",
        "fn": file_write,
    },
    "calculator": {
        "description": "Calculate a basic arithmetic expression.",
        "schema": {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        },
        "risk": "low",
        "fn": calculator,
    },
    "datetime": {
        "description": "Get current date/time.",
        "schema": {
            "type": "object",
            "properties": {"timezone": {"type": "string"}},
            "required": [],
        },
        "risk": "low",
        "fn": datetime_tool,
    },
    "system_info": {
        "description": "Get basic local system information.",
        "schema": {"type": "object", "properties": {}, "required": []},
        "risk": "low",
        "fn": system_info,
    },
    "clipboard": {
        "description": "Read or write the local clipboard.",
        "schema": {
            "type": "object",
            "properties": {
                "operation": {"type": "string", "enum": ["read", "write"]},
                "text": {"type": "string"},
            },
            "required": ["operation"],
        },
        "risk": "medium",
        "fn": clipboard,
    },
    #  'database_query': {'description':'Retrieve information through a future read-only database adapter.','schema':{'type':'object','properties':{'query':{'type':'string'}},'required':['query']},'risk':'medium','fn':database_query},
}


def definitions():
    return [
        {
            "type": "function",
            "function": {
                "name": n,
                "description": v["description"],
                "parameters": v["schema"],
            },
        }
        for n, v in TOOLS.items()
    ]
