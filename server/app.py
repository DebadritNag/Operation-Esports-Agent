"""
FastAPI application for the Esports Tournament Operations Manager environment.
"""
import os
import sys
import json
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from pydantic import ValidationError
import uvicorn
from typing import Dict, Any, Optional
from pydantic import BaseModel

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from models import Action, Observation, StepResponse
from server.environment import TournamentEnvironment

# Request models for OpenEnv compliance
class ResetRequest(BaseModel):
    task_id: Optional[str] = "task_easy_bracket"

# OpenEnv configuration via environment variables
WORKERS = int(os.getenv("WORKERS", "4"))
PORT = int(os.getenv("PORT", "7860"))  # HF Spaces use 7860
HOST = os.getenv("HOST", "0.0.0.0")
MAX_CONCURRENT_ENVS = int(os.getenv("MAX_CONCURRENT_ENVS", "100"))
ENABLE_WEB_INTERFACE = os.getenv("ENABLE_WEB_INTERFACE", "true").lower() == "true"

app = FastAPI(
    title="Esports Tournament Operations Manager",
    description="OpenEnv environment for tournament management operations",
    version="1.0.0"
)

# CORS - allow all origins including huggingface.co iframe
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom middleware to set headers that allow iframe embedding on huggingface.co
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest

class IframeCompatMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "ALLOWALL"
        response.headers["Content-Security-Policy"] = "frame-ancestors *"
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
        return response

app.add_middleware(IframeCompatMiddleware)

# Global environment instance
env = TournamentEnvironment()

# Global LLM chat history — cleared on every /reset call
global_chat_history: list = []


@app.get("/")
async def root():
    """Root endpoint - returns API info as JSON."""
    return {
        "name": "Esports Tournament Operations Manager",
        "version": "1.0.0",
        "description": "OpenEnv environment for tournament management operations",
        "status": "running",
        "config": {
            "workers": WORKERS,
            "port": PORT,
            "host": HOST,
            "max_concurrent_envs": MAX_CONCURRENT_ENVS,
            "web_interface_enabled": ENABLE_WEB_INTERFACE
        },
        "available_tasks": [
            "task_easy_bracket",
            "task_medium_conflict",
            "task_hard_dropout"
        ],
        "endpoints": {
            "POST /reset": "Reset environment for specific task (JSON body: {task_id})",
            "POST /step": "Execute action in environment",
            "GET /state": "Get current environment state",
            "GET /health": "Health check",
            "GET /docs": "API documentation",
            "GET /ui": "Interactive web interface"
        },
        "docs_url": "/docs",
        "ui_url": "/ui"
    }


@app.get("/api")
async def api_info():
    """API information endpoint."""
    return {
        "name": "Esports Tournament Operations Manager",
        "version": "1.0.0",
        "description": "OpenEnv environment for tournament management operations",
        "status": "running",
        "config": {
            "workers": WORKERS,
            "port": PORT,
            "host": HOST,
            "max_concurrent_envs": MAX_CONCURRENT_ENVS,
            "web_interface_enabled": ENABLE_WEB_INTERFACE
        },
        "available_tasks": [
            "task_easy_bracket",
            "task_medium_conflict", 
            "task_hard_dropout"
        ],
        "endpoints": {
            "POST /reset": "Reset environment for specific task (JSON body: {task_id})",
            "POST /step": "Execute action in environment",
            "GET /state": "Get current environment state",
            "GET /health": "Health check",
            "GET /docs": "API documentation",
            "GET /ui": "Interactive web interface (if enabled)"
        },
        "docs_url": "/docs",
        "ui_url": "/ui" if ENABLE_WEB_INTERFACE else None
    }


@app.get("/web")
async def web_probe():
    """HF Spaces internal probe endpoint - returns UI for iframe embedding."""
    return await web_interface()


@app.post("/reset", response_model=Observation)
async def reset_environment(request: Optional[ResetRequest] = None, task_id: Optional[str] = Query(None)):
    """
    Reset the environment to initial state for specified task.
    
    Args:
        request: Optional ResetRequest containing task_id (defaults to task_easy_bracket)
        task_id: Optional query parameter for task_id
    
    Returns:
        Initial observation for the task
    """
    try:
        global global_chat_history
        
        # Priority: query parameter > request body > default
        if task_id:
            final_task_id = task_id
        elif request:
            final_task_id = request.task_id
        else:
            final_task_id = "task_easy_bracket"

        # Clear LLM chat history so the agent starts with blank memory
        global_chat_history = []

        observation = env.reset(final_task_id)
        return observation
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.post("/step", response_model=StepResponse)
async def step_environment(action: Action):
    """
    Execute an action in the environment.
    
    Args:
        action: Action to execute
    
    Returns:
        StepResponse containing observation, reward, done status, and info
    """
    try:
        if not env.current_task:
            raise HTTPException(status_code=400, detail="Environment not initialized. Call /reset first.")
        
        observation, reward, done, info = env.step(action)
        
        # Guarantee reward is strictly within (0, 1) — validator requirement
        reward = max(0.001, min(float(reward), 0.999))
        
        return StepResponse(
            observation=observation,
            reward=reward,
            done=done,
            info=info
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=f"Validation error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get("/state")
async def get_state() -> Dict[str, Any]:
    """
    Get the current raw state of the environment.
    
    Returns:
        Current state dictionary
    """
    try:
        return env.get_state()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/metadata")
async def metadata():
    """OpenEnv metadata endpoint — returns environment name and description."""
    return {
        "name": "esports_env",
        "description": "Esports Tournament Operations Manager — OpenEnv environment for tournament management operations",
        "version": "1.0.0",
        "tasks": [
            {
                "id": "task_easy_bracket",
                "name": "Match Processing",
                "description": "Read match results and update bracket state",
                "difficulty": "easy"
            },
            {
                "id": "task_medium_conflict",
                "name": "Server Conflict Resolution",
                "description": "Handle server conflicts during overtime matches",
                "difficulty": "medium"
            },
            {
                "id": "task_hard_dropout",
                "name": "Team Dropout Management",
                "description": "Manage team dropouts and prize pool recalculation",
                "difficulty": "hard"
            }
        ],
        "reward_range": [0.001, 0.999]
    }


@app.get("/schema")
async def schema():
    """OpenEnv schema endpoint — returns action, observation, and state schemas."""
    return {
        "action": {
            "type": "object",
            "properties": {
                "update_matches": {
                    "type": "object",
                    "description": "Match ID to winner ID updates",
                    "additionalProperties": {"type": "string"}
                },
                "reallocate_servers": {
                    "type": "object",
                    "description": "Match ID to server ID reallocation",
                    "additionalProperties": {"type": "string"}
                },
                "broadcast_message": {
                    "type": "string",
                    "description": "Broadcast message to send"
                },
                "adjust_prize_pool": {
                    "type": "object",
                    "description": "Team ID to prize pool adjustment",
                    "additionalProperties": {"type": "number"}
                }
            }
        },
        "observation": {
            "type": "object",
            "properties": {
                "current_time": {"type": "string"},
                "active_alerts": {"type": "array", "items": {"type": "string"}},
                "bracket_state": {"type": "object", "additionalProperties": {"type": "string"}},
                "server_availability": {"type": "object", "additionalProperties": {"type": "boolean"}},
                "prize_pool_status": {"type": "object", "additionalProperties": {"type": "number"}},
                "scheduled_matches": {"type": "object", "additionalProperties": {"type": "string"}}
            }
        },
        "state": {
            "type": "object",
            "properties": {
                "current_time": {"type": "string"},
                "active_alerts": {"type": "array", "items": {"type": "string"}},
                "bracket_state": {"type": "object", "additionalProperties": {"type": "string"}},
                "server_availability": {"type": "object", "additionalProperties": {"type": "boolean"}},
                "prize_pool_status": {"type": "object", "additionalProperties": {"type": "number"}},
                "scheduled_matches": {"type": "object", "additionalProperties": {"type": "string"}}
            }
        }
    }


@app.post("/mcp")
async def mcp_endpoint(request: Dict[str, Any]):
    """OpenEnv MCP endpoint — JSON-RPC 2.0 interface for tool-based access."""
    method = request.get("method", "")
    req_id = request.get("id", 1)
    params = request.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "esports_env", "version": "1.0.0"}
            }
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "reset",
                        "description": "Reset the environment for a specific task",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"task_id": {"type": "string"}},
                            "required": ["task_id"]
                        }
                    },
                    {
                        "name": "step",
                        "description": "Execute an action in the environment",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "update_matches": {"type": "object"},
                                "reallocate_servers": {"type": "object"},
                                "broadcast_message": {"type": "string"},
                                "adjust_prize_pool": {"type": "object"}
                            }
                        }
                    },
                    {
                        "name": "state",
                        "description": "Get the current environment state",
                        "inputSchema": {"type": "object", "properties": {}}
                    }
                ]
            }
        }

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        if tool_name == "reset":
            try:
                task_id = tool_args.get("task_id", "task_easy_bracket")
                observation = env.reset(task_id)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": observation.model_dump_json()}]}
                }
            except Exception as e:
                return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32000, "message": str(e)}}

        if tool_name == "step":
            try:
                action = Action(**tool_args)
                observation, reward, done, info = env.step(action)
                reward = max(0.001, min(float(reward), 0.999))
                result = {"observation": observation.model_dump(), "reward": reward, "done": done, "info": info}
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(result)}]}
                }
            except Exception as e:
                return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32000, "message": str(e)}}

        if tool_name == "state":
            try:
                state = env.get_state()
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(state)}]}
                }
            except Exception as e:
                return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32000, "message": str(e)}}

    # Unknown method
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"}
    }


@app.post("/run_task")
async def run_complete_task(task_id: str):
    """
    Run a complete task with detailed step-by-step output.
    Calls the environment directly in-process (no HTTP self-call).
    """
    import io
    import json
    from contextlib import redirect_stdout
    from openai import OpenAI

    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        raise HTTPException(
            status_code=500,
            detail="HF_TOKEN environment variable is required. Set it in Hugging Face Spaces secrets."
        )

    api_base_url = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
    model_name   = os.getenv("MODEL_NAME",   "meta-llama/Meta-Llama-3-8B-Instruct")

    task_descriptions = {
        "task_easy_bracket": (
            "You are managing an esports tournament bracket. "
            "Read active_alerts for match results and update bracket_state with the correct winner. "
            "Only include update_matches in your response."
        ),
        "task_medium_conflict": (
            "You are handling a server conflict during a tournament. "
            "Read active_alerts to find which match needs reallocation and which server is overloaded. "
            "Use reallocate_servers to move the match to an AVAILABLE server (check server_availability for True values). "
            "Also include broadcast_message to notify teams. "
            "Do NOT use the overloaded server."
        ),
        "task_hard_dropout": (
            "You are handling a team dropout. Read active_alerts carefully. "
            "1. Use update_matches to record the forfeit win. "
            "2. Use adjust_prize_pool: set the dropout team to 0.0, "
            "then add (dropout_balance * 0.50 / num_active_teams) to each active team's CURRENT balance. "
            "Use EXACT decimal values. Do not include broadcast_message or reallocate_servers."
        ),
    }

    if task_id not in task_descriptions:
        raise HTTPException(status_code=400, detail=f"Unknown task_id: {task_id}")

    try:
        llm = OpenAI(base_url=api_base_url, api_key=hf_token)

        # Reset once — do NOT reset again inside the loop
        observation = env.reset(task_id)
        obs_dict = observation.model_dump()
        task_desc = task_descriptions[task_id]

        max_steps = 5   # Match env hard limit
        steps = []
        rewards = []
        success = False

        for step_num in range(1, max_steps + 1):
            # --- Query LLM ---
            system_prompt = f"""{task_desc}

OUTPUT RULES — STRICTLY FOLLOW:
- Respond with a single valid JSON object ONLY
- No comments, no explanations, no markdown, no text before or after the JSON
- All numbers must be plain decimals: 2000.0 not (1000 + 1000)
- Use the ACTUAL match IDs, server IDs, and team names from the observation — not placeholders
- Available fields (include only what is needed):
  "update_matches": {{"M4": "Team_Name"}}
  "reallocate_servers": {{"M3": "eu-west-2"}}
  "broadcast_message": "your message here"
  "adjust_prize_pool": {{"Team_Name": 2000.0}}"""

            user_prompt = f"""Current observation:
{json.dumps(obs_dict, indent=2)}

Based on the active_alerts and current state, respond with the correct action JSON."""

            try:
                response = llm.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_prompt},
                    ],
                    temperature=0.0,
                    max_tokens=600,
                )
                action_text = response.choices[0].message.content.strip()

                import re, json as _json

                # 1. Strip markdown fences
                if "```" in action_text:
                    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", action_text)
                    if m:
                        action_text = m.group(1).strip()

                # 2. Extract outermost { ... } — be greedy to get full object
                s = action_text.find("{")
                e = action_text.rfind("}")
                if s != -1 and e != -1:
                    action_text = action_text[s:e+1]

                # 3. Remove single-line // comments
                action_text = re.sub(r'//[^\n]*', '', action_text)
                # 4. Remove block /* */ comments
                action_text = re.sub(r'/\*[\s\S]*?\*/', '', action_text)
                # 5. Remove Python-style # comments
                action_text = re.sub(r'#[^\n]*', '', action_text)
                # 6. Evaluate math expressions in value positions only
                def _eval_math(m):
                    try:
                        return m.group(1) + str(round(eval(m.group(2)), 4))
                    except Exception:
                        return m.group(0)
                action_text = re.sub(
                    r'(:\s*)(\d+(?:\.\d+)?\s*[\+\-\*\/]\s*\d+(?:\.\d+)?)',
                    _eval_math,
                    action_text
                )
                # 7. Remove trailing commas before } or ]
                action_text = re.sub(r',\s*([}\]])', r'\1', action_text)
                # 8. Fix missing closing braces
                action_text += '}' * max(0, action_text.count('{') - action_text.count('}'))
                # 9. Collapse multiple whitespace/newlines inside strings
                action_text = re.sub(r'\s+', ' ', action_text)

                print(f"[DEBUG] cleaned JSON: {action_text[:400]}", flush=True)

                action_dict = _json.loads(action_text)

                # Strip null values and empty dicts to avoid Pydantic validation errors
                action_dict = {
                    k: v for k, v in action_dict.items()
                    if v is not None and v != {} and v != []
                }
                # Also strip null values inside nested dicts
                for k in list(action_dict.keys()):
                    if isinstance(action_dict[k], dict):
                        action_dict[k] = {
                            ik: iv for ik, iv in action_dict[k].items()
                            if iv is not None and ik not in ("match_id", "team_id", "server_id", "winner_id")
                        }
                        if not action_dict[k]:
                            del action_dict[k]
            except Exception as llm_err:
                # Retry once with a strict repair prompt
                try:
                    repair_response = llm.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": "Output ONLY a valid JSON object. No text, no comments, no markdown."},
                            {"role": "user", "content": f"Fix this broken JSON and return only the corrected JSON object:\n{action_text if 'action_text' in dir() else '{}'}"},
                        ],
                        temperature=0.0,
                        max_tokens=600,
                    )
                    repair_text = repair_response.choices[0].message.content.strip()
                    s2 = repair_text.find("{"); e2 = repair_text.rfind("}")
                    if s2 != -1 and e2 != -1:
                        repair_text = repair_text[s2:e2+1]
                    action_dict = _json.loads(repair_text)
                except Exception:
                    steps.append({"step": step_num, "action": "{}", "reward": 0.001, "done": True, "error": str(llm_err), "info": ""})
                    rewards.append(0.001)
                    success = False
                    break

            # --- Execute action directly on env ---
            from models import Action
            action_obj = Action(**action_dict)
            observation, reward, done, info = env.step(action_obj)
            # Clamp reward strictly within (0, 1)
            reward = max(0.001, min(float(reward), 0.999))
            # Always use the latest observation so LLM sees strike hints
            obs_dict = observation.model_dump()
            rewards.append(reward)

            action_json_str = json.dumps(action_dict, separators=(',', ':'))
            steps.append({
                "step": step_num,
                "action": action_json_str,
                "reward": reward,
                "done": done,
                "error": None,
                "info": info,
            })

            # Task-specific success thresholds
            success_threshold = 0.50  # Default
            if task_id == "task_easy_bracket":
                success_threshold = 0.75
            elif task_id == "task_medium_conflict":
                success_threshold = 0.60
            elif task_id == "task_hard_dropout":
                success_threshold = 0.40

            if done or reward >= success_threshold:
                success = reward >= success_threshold
                break

        # Build raw output string matching OpenEnv STDOUT format
        raw_lines = [f"[START] task={task_id} env=esports_env model={model_name}"]
        for s in steps:
            done_str = "true" if s["done"] else "false"
            err_str  = s["error"] if s["error"] else "null"
            raw_lines.append(f"[STEP] step={s['step']} action={s['action']} reward={s['reward']:.4f} done={done_str} error={err_str}")
        success_str  = "true" if success else "false"
        rewards_str  = ",".join(f"{r:.4f}" for r in rewards)
        raw_lines.append(f"[END] success={success_str} steps={len(rewards)} rewards={rewards_str}")

        return {
            "task_id": task_id,
            "start_info": {"task": task_id, "env": "esports_env", "model": model_name},
            "steps": steps,
            "end_info": {"success": success, "steps": len(rewards), "rewards": rewards},
            "raw_output": "\n".join(raw_lines),
            "success": success,
            "total_reward": sum(rewards),
            "step_count": len(steps),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Task execution failed: {str(e)}")


@app.get("/ui", response_class=HTMLResponse)
async def web_interface():
    """Interactive web interface for the tournament environment."""
    if not ENABLE_WEB_INTERFACE:
        raise HTTPException(status_code=404, detail="Web interface is disabled")

    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Esports Tournament Ops Manager v3.0</title>
    <style>
        body{font-family:Arial,sans-serif;margin:20px;background:#1a1a2e;color:#e0e0e0}
        .container{max-width:1200px;margin:0 auto;background:#16213e;padding:20px;border-radius:8px;box-shadow:0 2px 20px rgba(0,0,0,.5)}
        .header{text-align:center;margin-bottom:30px}
        .header h1{color:#e94560;margin-bottom:5px}
        .header p{color:#a0a0b0}
        .badge{display:inline-block;background:#e94560;color:#fff;padding:2px 10px;border-radius:12px;font-size:12px;margin-left:8px}
        .guide{background:#0f3460;border:1px solid #e94560;border-radius:8px;padding:15px;margin-bottom:20px}
        .guide h3{margin:0 0 10px;color:#e94560}
        .guide ol{margin:0;padding-left:20px;color:#c0c0d0}
        .guide li{margin:5px 0}
        .task-section{margin:20px 0;padding:20px;border:1px solid #2a2a4a;border-radius:8px;background:#0d1b2a;position:relative}
        .task-section.active{border-color:#28a745;background:#0d1f14}
        .task-section.active::before{content:"ACTIVE";position:absolute;top:-10px;right:10px;background:#28a745;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px}
        .task-title{font-size:17px;font-weight:700;color:#e94560;margin-bottom:6px}
        .task-desc{color:#888;margin-bottom:12px;font-size:13px}
        .controls{display:flex;gap:10px;margin:12px 0;flex-wrap:wrap}
        button{padding:9px 18px;border:none;border-radius:4px;cursor:pointer;font-size:13px;font-weight:600;transition:all .2s}
        button:disabled{opacity:.4;cursor:not-allowed}
        .btn-primary{background:#0f3460;color:#e0e0e0;border:1px solid #e94560}
        .btn-success{background:#28a745;color:#fff}
        .btn-warning{background:#ffc107;color:#212529}
        .btn-primary:hover:not(:disabled){background:#e94560;color:#fff}
        .btn-success:hover:not(:disabled){background:#1e7e34}
        .btn-warning:hover:not(:disabled){background:#e0a800}
        .output{background:#0a0a1a;border:1px solid #2a2a4a;border-radius:4px;padding:15px;margin:10px 0;font-family:'Courier New',monospace;font-size:12px;white-space:pre-wrap;max-height:420px;overflow-y:auto;color:#c0ffc0}
        .status{padding:4px 10px;border-radius:3px;font-weight:700;margin-bottom:4px;display:block}
        .status.success{background:#1a3a1a;color:#4caf50;border-left:3px solid #4caf50}
        .status.error{background:#3a1a1a;color:#f44336;border-left:3px solid #f44336}
        .status.info{background:#1a2a3a;color:#2196f3;border-left:3px solid #2196f3}
        .status.warning{background:#3a2a1a;color:#ff9800;border-left:3px solid #ff9800}
        .status.strike{background:#3a1a3a;color:#e040fb;border-left:3px solid #e040fb}
        .step-block{border-left:2px solid #333;padding-left:10px;margin:6px 0}
        .raw{color:#80ff80;font-size:11px}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>Esports Tournament Operations Manager <span class="badge">v3.0</span></h1>
        <p>OpenEnv Environment &mdash; Esports Tournament Operations Manager</p>
    </div>
    <div class="guide">
        <h3>How to Use</h3>
        <ol>
            <li><strong>Reset Task</strong> &mdash; initializes the environment for the selected task</li>
            <li><strong>Run with LLM</strong> &mdash; the AI agent analyzes the situation and executes the appropriate actions</li>
            <li>Review the step-by-step execution and final reward in the output panel</li>
            <li>Check the OpenEnv STDOUT log at the bottom of each result for compliance output</li>
        </ol>
        <p style="color:#a0a0b0;font-size:12px;margin-top:10px;">
            <strong>Scoring System:</strong> Easy (0.75-0.87, 1 step), Medium (0.55-0.72, 2-3 steps), Hard (0.35-0.52, 3-4 steps)
        </p>
    </div>

    <div class="task-section" id="task-easy-bracket">
        <div class="task-title">Task 1: Easy &mdash; Match Processing <span style="color:#28a745;font-size:12px;">[Max: 0.87, Success: 0.75+] (1 step)</span></div>
        <div class="task-desc">Read match results from alerts and update bracket winners</div>
        <div class="controls">
            <button class="btn-primary" onclick="resetTask('task_easy_bracket')">Reset Task</button>
            <button class="btn-success" id="easy-execute" onclick="runTask('task_easy_bracket')" disabled>Run with LLM</button>
            <button class="btn-warning" onclick="clearTask('task_easy_bracket')">Clear</button>
        </div>
        <div id="easy-output" class="output">Click "Reset Task" to generate a scenario...</div>
    </div>

    <div class="task-section" id="task-medium-conflict">
        <div class="task-title">Task 2: Medium &mdash; Server Conflict <span style="color:#ffc107;font-size:12px;">[Max: 0.72, Success: 0.55+] (2-3 steps)</span></div>
        <div class="task-desc">Handle server conflicts and reallocate resources during live matches</div>
        <div class="controls">
            <button class="btn-primary" onclick="resetTask('task_medium_conflict')">Reset Task</button>
            <button class="btn-success" id="medium-execute" onclick="runTask('task_medium_conflict')" disabled>Run with LLM</button>
            <button class="btn-warning" onclick="clearTask('task_medium_conflict')">Clear</button>
        </div>
        <div id="medium-output" class="output">Click "Reset Task" to generate a scenario...</div>
    </div>

    <div class="task-section" id="task-hard-dropout">
        <div class="task-title">Task 3: Hard &mdash; Team Dropout <span style="color:#e94560;font-size:12px;">[Max: 0.52, Success: 0.35+] (3-4 steps)</span></div>
        <div class="task-desc">Manage team dropouts, forfeit rulings, and prize pool redistribution</div>
        <div class="controls">
            <button class="btn-primary" onclick="resetTask('task_hard_dropout')">Reset Task</button>
            <button class="btn-success" id="hard-execute" onclick="runTask('task_hard_dropout')" disabled>Run with LLM</button>
            <button class="btn-warning" onclick="clearTask('task_hard_dropout')">Clear</button>
        </div>
        <div id="hard-output" class="output">Click "Reset Task" to generate a scenario...</div>
    </div>

    <div class="task-section">
        <div class="task-title">Environment Status</div>
        <div class="controls">
            <button class="btn-primary" onclick="getStatus()">Get Status</button>
            <button class="btn-primary" onclick="getState()">Get State</button>
        </div>
        <div id="status-output" class="output">Environment information will appear here...</div>
    </div>
</div>

<script>
    const API_BASE = "https://cosmoser-esports-env.hf.space";
    let activeTasks = new Set();
    const TASK_MAP = {
        'task_easy_bracket':    {sec:'task-easy-bracket',   btn:'easy-execute',   out:'easy-output'},
        'task_medium_conflict': {sec:'task-medium-conflict',btn:'medium-execute', out:'medium-output'},
        'task_hard_dropout':    {sec:'task-hard-dropout',   btn:'hard-execute',   out:'hard-output'}
    };

    function setActive(taskId, on) {
        const t = TASK_MAP[taskId];
        document.getElementById(t.sec).classList.toggle('active', on);
        document.getElementById(t.btn).disabled = !on;
        on ? activeTasks.add(taskId) : activeTasks.delete(taskId);
    }

    function clearTask(taskId) {
        setActive(taskId, false);
        document.getElementById(TASK_MAP[taskId].out).innerHTML = 'Click "Reset Task" to generate a scenario...';
    }

    async function resetTask(taskId) {
        // Wipe all state + LLM memory
        activeTasks.clear();
        Object.keys(TASK_MAP).forEach(id => setActive(id, false));

        const out = document.getElementById(TASK_MAP[taskId].out);
        out.innerHTML = 'Resetting environment...';
        try {
            const r = await fetch(`${API_BASE}/reset`, {
                method:'POST', headers:{'Content-Type':'application/json'},
                body: JSON.stringify({task_id: taskId})
            });
            const d = await r.json();
            if (r.ok) {
                setActive(taskId, true);
                out.innerHTML =
                    '<span class="status success">&#10003; Reset successful &mdash; environment ready</span>\\n\\n' +
                    '<strong>Active Alerts:</strong>\\n' + JSON.stringify(d.active_alerts, null, 2) +
                    '\\n\\n<strong>Full Observation:</strong>\\n' + JSON.stringify(d, null, 2) +
                    '\\n\\n<span class="status info">Click "Run with LLM" to start the agent</span>';
            } else {
                out.innerHTML = '<span class="status error">Reset failed</span>\\n' + JSON.stringify(d, null, 2);
            }
        } catch(e) {
            document.getElementById(TASK_MAP[taskId].out).innerHTML =
                `<span class="status error">Network error: ${e.message}</span>`;
        }
    }

    async function runTask(taskId) {
        const out = document.getElementById(TASK_MAP[taskId].out);
        if (!activeTasks.has(taskId)) {
            out.innerHTML = '<span class="status warning">Reset the task first.</span>';
            return;
        }
        out.innerHTML = 'Running LLM agent (up to 5 steps)...';
        try {
            const r = await fetch(`${API_BASE}/run_task?task_id=${taskId}`, {
                method:'POST', headers:{'Content-Type':'application/json'}
            });
            const d = await r.json();
            if (r.ok) {
                // Determine overall success color based on task-specific thresholds
                let overallSuccessThreshold = 0.50;
                let overallMaxScore = 0.99;
                if (taskId === 'task_easy_bracket') {
                    overallSuccessThreshold = 0.75;
                    overallMaxScore = 0.87;
                } else if (taskId === 'task_medium_conflict') {
                    overallSuccessThreshold = 0.55;
                    overallMaxScore = 0.72;
                } else if (taskId === 'task_hard_dropout') {
                    overallSuccessThreshold = 0.35;
                    overallMaxScore = 0.52;
                }
                
                const sc = d.total_reward >= overallSuccessThreshold ? 'success' : 'error';
                const lbl = d.total_reward >= overallSuccessThreshold ? '&#10003; SUCCESS' : '&#10007; FAILED';
                let steps = '';
                d.steps.forEach(s => {
                    // Task-specific success thresholds and max scores for color coding
                    let successThreshold = 0.50; // Default
                    let maxScore = 0.99; // Default
                    if (taskId === 'task_easy_bracket') {
                        successThreshold = 0.75;
                        maxScore = 0.87;
                    } else if (taskId === 'task_medium_conflict') {
                        successThreshold = 0.55;
                        maxScore = 0.72;
                    } else if (taskId === 'task_hard_dropout') {
                        successThreshold = 0.35;
                        maxScore = 0.52;
                    }
                    
                    // Color coding based on performance relative to task difficulty
                    let c = 'error';
                    if (s.reward >= successThreshold) {
                        c = 'success'; // Green for success threshold
                    } else if (s.reward >= successThreshold * 0.7) {
                        c = 'warning'; // Yellow for partial success
                    } else if (s.reward > 0) {
                        c = 'info'; // Blue for some attempt
                    }
                    // Red (error) for zero score
                    
                    steps += `<div class="step-block">`;
                    steps += `<span class="status ${c}">Step ${s.step} &mdash; Reward: ${s.reward.toFixed(2)}/${maxScore.toFixed(2)} | Done: ${s.done}</span>`;
                    steps += `Action: ${s.action}\\n`;
                    if (s.info)  steps += `Info: ${s.info}\\n`;
                    if (s.error) steps += `<span class="status strike">&#9889; ${s.error}</span>\\n`;
                    steps += `</div>`;
                });
                
                out.innerHTML =
                    `<span class="status ${sc}">${lbl} &mdash; Reward: ${d.total_reward.toFixed(2)}/${overallMaxScore.toFixed(2)} | Steps: ${d.step_count} | Model: ${d.start_info.model}</span>\\n\\n` +
                    `<strong>Step-by-Step:</strong>\\n${steps}\\n` +
                    `<strong>OpenEnv STDOUT:</strong>\\n<span class="raw">${d.raw_output}</span>`;
                setActive(taskId, false);
            } else {
                out.innerHTML = '<span class="status error">Execution failed</span>\\n' + JSON.stringify(d, null, 2);
            }
        } catch(e) {
            document.getElementById(TASK_MAP[taskId].out).innerHTML =
                `<span class="status error">Network error: ${e.message}</span>`;
        }
    }

    async function getStatus() {
        const out = document.getElementById('status-output');
        try {
            out.innerHTML = 'Fetching...';
            const r = await fetch(`${API_BASE}/api`);
            const d = await r.json();
            out.innerHTML = '<span class="status info">Environment Status</span>\\n' + JSON.stringify(d, null, 2);
        } catch(e) { out.innerHTML = `<span class="status error">${e.message}</span>`; }
    }

    async function getState() {
        const out = document.getElementById('status-output');
        try {
            out.innerHTML = 'Fetching...';
            const r = await fetch(`${API_BASE}/state`);
            const d = await r.json();
            out.innerHTML = '<span class="status info">Current State</span>\\n' + JSON.stringify(d, null, 2);
        } catch(e) { out.innerHTML = `<span class="status error">${e.message}</span>`; }
    }
</script>
</body>
</html>"""
    return HTMLResponse(content=html_content)



def main():
    """Main entry point for the server."""
    # Always use 1 worker - the env state is in-process memory,
    # multiple workers each get their own env instance causing
    # reset/step to hit different processes and lose state.
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        workers=1
    )


if __name__ == "__main__":
    main()