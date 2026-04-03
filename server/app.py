"""
FastAPI application for the Esports Tournament Operations Manager environment.
"""
import os
import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from pydantic import ValidationError
import uvicorn
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from models import Action, Observation, StepResponse
from server.environment import TournamentEnvironment

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
            "POST /reset?task_id={id}": "Reset environment for specific task",
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
            "POST /reset?task_id={id}": "Reset environment for specific task",
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
async def reset_environment(task_id: str):
    """
    Reset the environment to initial state for specified task.
    
    Args:
        task_id: One of 'task_easy_bracket', 'task_medium_conflict', 'task_hard_dropout'
    
    Returns:
        Initial observation for the task
    """
    try:
        observation = env.reset(task_id)
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
    """
    Health check endpoint.
    
    Returns:
        Health status
    """
    return {"status": "healthy"}


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
        "task_easy_bracket": """You are managing an esports tournament bracket.
TASK: Read active_alerts to find match results, then update bracket_state with the correct winners.
Only include update_matches in your response. No other fields needed.""",

        "task_medium_conflict": """You are handling a server conflict during a tournament.
TASK: A match has a server conflict. You must:
1. Use reallocate_servers to move the conflicted match to an AVAILABLE server (check server_availability for True values, avoid occupied ones)
2. Use broadcast_message to notify teams
Only include reallocate_servers and broadcast_message in your response.""",

        "task_hard_dropout": """You are handling a team dropout situation.
TASK: Read active_alerts carefully. It tells you EXACTLY what to do:
- Which match to forfeit and to whom -> use update_matches
- How much prize money to redistribute and to which teams -> use adjust_prize_pool

CRITICAL RULES for prize pool:
- Set the dropped team's prize to 0.0
- Divide their original prize EVENLY among the remaining active teams
- Use the EXACT amounts from the observation's prize_pool_status to calculate
- Formula: new_amount = original_amount + (dropped_team_prize / num_remaining_teams)
- Do NOT include reallocate_servers or broadcast_message

Example: if dropped team had 3000 and 3 remaining teams each had 1000:
each remaining team gets 1000 + (3000/3) = 1000 + 1000 = 2000

Respond with ONLY update_matches and adjust_prize_pool.""",
    }

    if task_id not in task_descriptions:
        raise HTTPException(status_code=400, detail=f"Unknown task_id: {task_id}")

    try:
        llm = OpenAI(base_url=api_base_url, api_key=hf_token)

        # Reset the shared env directly
        observation = env.reset(task_id)
        obs_dict = observation.model_dump()
        # Keep a snapshot of the initial observation for retries
        initial_obs_dict = dict(obs_dict)
        task_desc = task_descriptions[task_id]

        max_steps = 10
        steps = []
        rewards = []
        success = False

        for step_num in range(1, max_steps + 1):
            # --- Query LLM ---
            system_prompt = f"""{task_desc}

Respond with a valid JSON object ONLY. No explanations, no markdown, no text outside the JSON.
Available action fields (only include what is needed for this task):
- update_matches: dict mapping match_id to winner_id (string)
- reallocate_servers: dict mapping match_id to server_id (string)
- broadcast_message: string
- adjust_prize_pool: dict mapping team_id to NEW total amount (float)

IMPORTANT: Use exact decimal numbers like 2000.0, not expressions like 1000 + 1000."""

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
                    max_tokens=300,
                )
                action_text = response.choices[0].message.content.strip()

                # Extract JSON from possible markdown fences
                import re
                if "```" in action_text:
                    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", action_text)
                    if m:
                        action_text = m.group(1).strip()
                if not action_text.startswith("{"):
                    s = action_text.find("{")
                    e = action_text.rfind("}")
                    if s != -1 and e != -1:
                        action_text = action_text[s:e+1]

                # Evaluate inline math expressions like 1000 + 1000 or 3000/3
                action_text = re.sub(
                    r'(\d+(?:\.\d+)?)\s*([\+\-\*\/])\s*(\d+(?:\.\d+)?)',
                    lambda m: str(round(eval(m.group(0)), 4)),
                    action_text
                )
                # Remove trailing commas before } or ]
                action_text = re.sub(r',\s*([}\]])', r'\1', action_text)
                # Fix missing closing braces
                open_count = action_text.count('{')
                close_count = action_text.count('}')
                if open_count > close_count:
                    action_text += '}' * (open_count - close_count)

                action_dict = json.loads(action_text)
            except Exception as llm_err:
                steps.append({"step": step_num, "action": "{}", "reward": 0.0, "done": True, "error": str(llm_err)})
                rewards.append(0.0)
                success = False
                break

            # --- Execute action directly on env ---
            # Always reset before each attempt so state doesn't compound
            env.reset(task_id)
            from models import Action
            action_obj = Action(**action_dict)
            observation, reward, done, info = env.step(action_obj)
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

            if done or reward >= 1.0:
                success = reward >= 1.0
                break

            # On partial reward, keep using the initial observation so the LLM
            # doesn't see a compounded/mutated state on the next attempt
            obs_dict = initial_obs_dict

        # Build raw output string matching OpenEnv STDOUT format
        raw_lines = [f"[START] task={task_id} env=esports_env model={model_name}"]
        for s in steps:
            done_str = "true" if s["done"] else "false"
            err_str  = s["error"] if s["error"] else "null"
            raw_lines.append(f"[STEP] step={s['step']} action={s['action']} reward={s['reward']:.2f} done={done_str} error={err_str}")
        success_str  = "true" if success else "false"
        rewards_str  = ",".join(f"{r:.2f}" for r in rewards)
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
    """
    Interactive web interface for the tournament environment.
    
    Returns:
        HTML page with interactive controls
    """
    if not ENABLE_WEB_INTERFACE:
        raise HTTPException(status_code=404, detail="Web interface is disabled")

    # Absolute backend URL injected into JS so fetch works inside the HF iframe too
    backend_url = "https://debadrit-esports-tournament-env.hf.space"

    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Esports Tournament Operations Manager v2.1</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .header { text-align: center; margin-bottom: 30px; }
            .workflow-guide { background: #e3f2fd; border: 1px solid #2196f3; border-radius: 8px; padding: 15px; margin-bottom: 20px; }
            .workflow-guide h3 { margin: 0 0 10px 0; color: #1976d2; }
            .workflow-steps { list-style: none; padding: 0; }
            .workflow-steps li { margin: 5px 0; padding: 5px 0; }
            .workflow-steps .step-number { background: #2196f3; color: white; border-radius: 50%; width: 20px; height: 20px; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; margin-right: 10px; }
            .task-section { margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 8px; position: relative; }
            .task-section.active { border-color: #28a745; background: #f8fff9; }
            .task-section.active::before { content: "ACTIVE"; position: absolute; top: -10px; right: 10px; background: #28a745; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
            .task-title { font-size: 18px; font-weight: bold; color: #333; margin-bottom: 10px; }
            .task-description { color: #666; margin-bottom: 15px; }
            .controls { display: flex; gap: 10px; margin: 15px 0; }
            button { padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; transition: all 0.2s; }
            button:disabled { opacity: 0.6; cursor: not-allowed; }
            .btn-primary { background: #007bff; color: white; }
            .btn-success { background: #28a745; color: white; }
            .btn-warning { background: #ffc107; color: #212529; }
            .btn-primary:hover:not(:disabled) { background: #0056b3; }
            .btn-success:hover:not(:disabled) { background: #1e7e34; }
            .btn-warning:hover:not(:disabled) { background: #e0a800; }
            .output { background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 15px; margin: 10px 0; font-family: monospace; white-space: pre-wrap; max-height: 300px; overflow-y: auto; }
            .status { padding: 5px 10px; border-radius: 4px; font-weight: bold; }
            .status.success { background: #d4edda; color: #155724; }
            .status.error { background: #f8d7da; color: #721c24; }
            .status.info { background: #d1ecf1; color: #0c5460; }
            .status.warning { background: #fff3cd; color: #856404; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Esports Tournament Operations Manager</h1>
                <p>Interactive OpenEnv Environment for Tournament Management | <strong>Version 2.1 Final</strong></p>
            </div>

            <div class="workflow-guide">
                <h3>How to Use This Interface</h3>
                <ol class="workflow-steps">
                    <li><span class="step-number">1</span>Click "Reset Task" to initialize a specific task environment</li>
                    <li><span class="step-number">2</span>Wait for the reset to complete and show active alerts</li>
                    <li><span class="step-number">3</span>Click "Run with LLM" to execute the complete task with AI agent</li>
                    <li><span class="step-number">4</span>Review the detailed step-by-step execution and final results</li>
                </ol>
                <p><strong>Important:</strong> You must reset a task before running it. The LLM agent will analyze the situation and execute appropriate actions automatically.</p>
            </div>

            <div class="task-section" id="task-easy-bracket">
                <div class="task-title">Task 1: Easy - Match Processing</div>
                <div class="task-description">Read match results and update bracket winners</div>
                <div class="controls">
                    <button class="btn-primary" onclick="resetTask('task_easy_bracket', 'easy')">Reset Task</button>
                    <button class="btn-success" id="easy-execute" onclick="executeEasyAction()" disabled>Run with LLM</button>
                    <button class="btn-warning" onclick="clearTask('easy')">Clear</button>
                </div>
                <div id="easy-output" class="output">Click "Reset Task" to begin, then "Run with LLM" to see detailed execution...</div>
            </div>

            <div class="task-section" id="task-medium-conflict">
                <div class="task-title">Task 2: Medium - Server Conflict</div>
                <div class="task-description">Handle server conflicts and reallocate resources</div>
                <div class="controls">
                    <button class="btn-primary" onclick="resetTask('task_medium_conflict', 'medium')">Reset Task</button>
                    <button class="btn-success" id="medium-execute" onclick="executeMediumAction()" disabled>Run with LLM</button>
                    <button class="btn-warning" onclick="clearTask('medium')">Clear</button>
                </div>
                <div id="medium-output" class="output">Click "Reset Task" to begin, then "Run with LLM" to see detailed execution...</div>
            </div>

            <div class="task-section" id="task-hard-dropout">
                <div class="task-title">Task 3: Hard - Team Dropout</div>
                <div class="task-description">Manage team dropouts and prize pool recalculation</div>
                <div class="controls">
                    <button class="btn-primary" onclick="resetTask('task_hard_dropout', 'hard')">Reset Task</button>
                    <button class="btn-success" id="hard-execute" onclick="executeHardAction()" disabled>Run with LLM</button>
                    <button class="btn-warning" onclick="clearTask('hard')">Clear</button>
                </div>
                <div id="hard-output" class="output">Click "Reset Task" to begin, then "Run with LLM" to see detailed execution...</div>
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
            // Absolute backend URL - works both direct and inside HF Spaces iframe
            const API_BASE = "https://debadrit-esports-tournament-env.hf.space";

            let activeTasks = new Set();

            // Maps full task_id -> { sectionId, executeBtnId, outputId, shortType }
            const TASK_MAP = {
                'task_easy_bracket':   { sectionId: 'task-easy-bracket',   executeBtnId: 'easy-execute',   outputId: 'easy-output',   shortType: 'easy' },
                'task_medium_conflict':{ sectionId: 'task-medium-conflict', executeBtnId: 'medium-execute', outputId: 'medium-output', shortType: 'medium' },
                'task_hard_dropout':   { sectionId: 'task-hard-dropout',    executeBtnId: 'hard-execute',   outputId: 'hard-output',   shortType: 'hard' }
            };

            function updateTaskUI(taskId, isActive) {
                const t = TASK_MAP[taskId];
                if (!t) { console.error('Unknown taskId:', taskId); return; }
                const section = document.getElementById(t.sectionId);
                const executeBtn = document.getElementById(t.executeBtnId);
                if (!section || !executeBtn) { console.error('Element not found for', taskId); return; }
                if (isActive) {
                    section.classList.add('active');
                    executeBtn.disabled = false;
                    activeTasks.add(taskId);
                } else {
                    section.classList.remove('active');
                    executeBtn.disabled = true;
                    activeTasks.delete(taskId);
                }
            }

            function clearTask(shortType) {
                const taskId = Object.keys(TASK_MAP).find(k => TASK_MAP[k].shortType === shortType);
                if (!taskId) return;
                updateTaskUI(taskId, false);
                document.getElementById(TASK_MAP[taskId].outputId).innerHTML = 'Click "Reset Task" to begin, then "Run with LLM" to see detailed execution...';
            }

            async function resetTask(taskId, taskType) {
                const t = TASK_MAP[taskId];
                const output = document.getElementById(t.outputId);
                
                // Deactivate any other active tasks first
                activeTasks.forEach(activeTask => {
                    if (activeTask !== taskId) updateTaskUI(activeTask, false);
                });
                
                try {
                    output.innerHTML = 'Resetting task environment...';
                    const response = await fetch(`${API_BASE}/reset?task_id=${taskId}`, { method: 'POST' });
                    const data = await response.json();
                    
                    if (response.ok) {
                        updateTaskUI(taskId, true);
                        output.innerHTML = `<div class="status success">Task Reset Successful - Ready for Action</div>` +
                                         `<strong>Active Alerts:</strong>\\n${JSON.stringify(data.active_alerts, null, 2)}\\n\\n` +
                                         `<strong>Initial State:</strong>\\n${JSON.stringify(data, null, 2)}\\n\\n` +
                                         `<div class="status info">You can now click "Run with LLM" to execute the complete task</div>`;
                    } else {
                        updateTaskUI(taskId, false);
                        output.innerHTML = `<div class="status error">Reset Failed</div>` +
                                         `<strong>Error Details:</strong>\\n${JSON.stringify(data, null, 2)}`;
                    }
                } catch (error) {
                    updateTaskUI(taskId, false);
                    output.innerHTML = `<div class="status error">Network Error: ${error.message}</div>`;
                }
            }

            async function executeCompleteTask(taskId) {
                const t = TASK_MAP[taskId];
                const output = document.getElementById(t.outputId);
                
                if (!activeTasks.has(taskId)) {
                    output.innerHTML = `<div class="status warning">Task Not Active - please click Reset Task first</div>`;
                    return;
                }
                
                try {
                    output.innerHTML = 'Running complete task with LLM agent...';
                    const response = await fetch(`${API_BASE}/run_task?task_id=${taskId}`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });
                    const data = await response.json();
                    
                    if (response.ok) {
                        const statusClass = data.success ? 'success' : 'error';
                        const label = data.success ? 'SUCCESS' : 'FAILED';
                        
                        // Build detailed step-by-step output
                        let stepDetails = '';
                        data.steps.forEach((step, index) => {
                            const stepStatus = step.reward >= 1.0 ? 'success' : step.reward > 0 ? 'info' : 'error';
                            stepDetails += `<div class="status ${stepStatus}">Step ${step.step}: Reward ${step.reward} | Done: ${step.done}</div>`;
                            stepDetails += `Action: ${step.action}\\n`;
                            if (step.error) {
                                stepDetails += `Error: ${step.error}\\n`;
                            }
                            stepDetails += '\\n';
                        });
                        
                        output.innerHTML = `<div class="status ${statusClass}">${label} - Total Reward: ${data.total_reward} | Steps: ${data.step_count}</div>` +
                                         `<strong>Task Execution Details:</strong>\\n` +
                                         `Model: ${data.start_info.model || 'Unknown'}\\n` +
                                         `Environment: ${data.start_info.env || 'Unknown'}\\n\\n` +
                                         `<strong>Step-by-Step Execution:</strong>\\n${stepDetails}` +
                                         `<strong>Final Results:</strong>\\n` +
                                         `Success: ${data.end_info.success}\\n` +
                                         `Total Steps: ${data.end_info.steps}\\n` +
                                         `Rewards: [${data.end_info.rewards ? data.end_info.rewards.join(', ') : 'None'}]\\n\\n` +
                                         `<div class="status info">Task completed! Reset to try again.</div>`;
                        updateTaskUI(taskId, false);
                    } else {
                        output.innerHTML = `<div class="status error">Task Execution Failed</div>` +
                                         `<strong>Error Details:</strong>\\n${JSON.stringify(data, null, 2)}\\n\\n` +
                                         `<div class="status warning">Try resetting the task and executing again</div>`;
                    }
                } catch (error) {
                    output.innerHTML = `<div class="status error">Network Error: ${error.message}</div>`;
                }
            }

            async function executeAction(action, taskId) {
                const t = TASK_MAP[taskId];
                const output = document.getElementById(t.outputId);
                
                if (!activeTasks.has(taskId)) {
                    output.innerHTML = `<div class="status warning">Task Not Active - please click Reset Task first</div>`;
                    return;
                }
                
                try {
                    output.innerHTML = 'Executing action...';
                    const response = await fetch(`${API_BASE}/step`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(action)
                    });
                    const data = await response.json();
                    
                    if (response.ok) {
                        const statusClass = data.reward >= 1.0 ? 'success' : data.reward > 0 ? 'info' : 'error';
                        const label = data.reward >= 1.0 ? 'SUCCESS' : data.reward > 0 ? 'PARTIAL' : 'FAILED';
                        output.innerHTML = `<div class="status ${statusClass}">${label} - Reward: ${data.reward} | Done: ${data.done}</div>` +
                                         `<strong>Action Executed:</strong>\\n${JSON.stringify(action, null, 2)}\\n\\n` +
                                         `<strong>Environment Response:</strong>\\n${JSON.stringify(data, null, 2)}\\n\\n` +
                                         `<div class="status info">Task completed! Reset to try again.</div>`;
                        updateTaskUI(taskId, false);
                    } else {
                        output.innerHTML = `<div class="status error">Action Failed</div>` +
                                         `<strong>Error Details:</strong>\\n${JSON.stringify(data, null, 2)}\\n\\n` +
                                         `<div class="status warning">Try resetting the task and executing again</div>`;
                    }
                } catch (error) {
                    output.innerHTML = `<div class="status error">Network Error: ${error.message}</div>`;
                }
            }

            function executeEasyAction()   { executeCompleteTask('task_easy_bracket'); }
            function executeMediumAction() { executeCompleteTask('task_medium_conflict'); }
            function executeHardAction()   { executeCompleteTask('task_hard_dropout'); }

            async function getStatus() {
                const output = document.getElementById('status-output');
                try {
                    output.innerHTML = 'Fetching environment status...';
                    const response = await fetch(`${API_BASE}/api`);
                    const data = await response.json();
                    output.innerHTML = `<div class="status info">Environment Status</div>` +
                                     `${JSON.stringify(data, null, 2)}`;
                } catch (error) {
                    output.innerHTML = `<div class="status error">Error: ${error.message}</div>`;
                }
            }

            async function getState() {
                const output = document.getElementById('status-output');
                try {
                    output.innerHTML = 'Fetching current state...';
                    const response = await fetch(`${API_BASE}/state`);
                    const data = await response.json();
                    output.innerHTML = `<div class="status info">Current State</div>` +
                                     `${JSON.stringify(data, null, 2)}`;
                } catch (error) {
                    output.innerHTML = `<div class="status error">Error: ${error.message}</div>`;
                }
            }
        </script>
    </body>
    </html>
    """
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