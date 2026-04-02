---
title: Esports Tournament Operations Manager
emoji: 🏆
colorFrom: blue
colorTo: purple
sdk: docker
app_file: server/app.py
pinned: false
---

# Esports Tournament Operations Manager

**Version 2.0** | OpenEnv-compliant environment for managing esports tournament logistics.

Live Space: https://Debadrit-esports-tournament-env.hf.space
Web UI: https://Debadrit-esports-tournament-env.hf.space/ui
API Docs: https://Debadrit-esports-tournament-env.hf.space/docs
Health: https://Debadrit-esports-tournament-env.hf.space/health

---

## Overview

The agent acts as an automated Tournament Admin API that receives alerts about tournament state and must issue precise JSON commands to manage brackets, reallocate servers, and handle prize pools.

Three progressively challenging tasks:

1. Easy - Match Processing: Read match results and update bracket winners
2. Medium - Server Conflict: Handle server conflicts during overtime matches
3. Hard - Team Dropout: Manage team dropouts and prize pool recalculation

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start the Environment Server

```bash
python main.py
```

Server starts on `http://localhost:7860`

### 3. Run Baseline Inference

```bash
export HF_TOKEN="your-hf-token-here"
export API_BASE_URL="https://router.huggingface.co/v1"
export MODEL_NAME="meta-llama/Meta-Llama-3-8B-Instruct"
python inference.py
```

---

## Web UI

The interactive web interface is available at `/ui`. It provides one-click testing for all three tasks.

**Workflow:**
1. Click "Reset Task" to initialize the environment for a specific task
2. Wait for the reset confirmation and active alerts to appear
3. Click "Execute Action" to run the pre-configured correct action
4. Review the reward score and completion status

The Execute button is disabled until a successful reset — this prevents the "Environment not initialized" error.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Environment info and status |
| POST | `/reset?task_id={id}` | Reset environment for a task |
| POST | `/step` | Execute an action |
| GET | `/state` | Get current environment state |
| GET | `/health` | Health check |
| GET | `/ui` | Interactive web interface |
| GET | `/docs` | Swagger API documentation |

---

## Tasks

### Task 1: Match Processing (Easy)

**Alert:** "Match M1 has concluded. 'Team_Alpha' defeated 'Team_Beta'. Please update the bracket state."

**Required Action:**
```json
{ "update_matches": { "M1": "Team_Alpha" } }
```

**Reward:** 1.0 if bracket_state matches exactly, 0.0 otherwise

---

### Task 2: Server Conflict Resolution (Medium)

**Alert:** "URGENT: Match M2 is in triple overtime on server 'eu-west-1'. Match M3 is scheduled to start on 'eu-west-1' in 5 minutes. Reallocate Match M3 to an available server and broadcast a delay message."

**Required Action:**
```json
{
  "reallocate_servers": { "M3": "eu-west-2" },
  "broadcast_message": "Match M3 moved due to server conflict"
}
```

**Reward:** +0.5 correct reallocation, +0.5 broadcast message

---

### Task 3: Team Dropout Management (Hard)

**Alert:** "CRITICAL: 'Team_Liquid' has dropped out. Mark Match M4 as forfeit win for 'Team_Solid'. Zero out Team_Liquid's prize pool and distribute their $3000 evenly among the 3 remaining teams."

**Required Action:**
```json
{
  "update_matches": { "M4": "Team_Solid" },
  "adjust_prize_pool": {
    "Team_Liquid": 0.0,
    "Team_Solid": 2000.0,
    "Team_Spirit": 2000.0,
    "Team_Falcon": 2000.0
  }
}
```

**Reward:** +0.4 correct match winner, +0.6 exact prize pool math

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HF_TOKEN` | required | Hugging Face token (used as API key) |
| `API_BASE_URL` | `https://router.huggingface.co/v1` | LLM API endpoint |
| `MODEL_NAME` | `meta-llama/Meta-Llama-3-8B-Instruct` | Model identifier |
| `PORT` | `7860` | Server port (HF Spaces default) |
| `HOST` | `0.0.0.0` | Bind address |
| `ENABLE_WEB_INTERFACE` | `true` | Enable `/ui` endpoint |

---

## STDOUT Format (inference.py)

The inference script emits structured logs for evaluation:

```
[START] task=task_easy_bracket env=esports_env model=meta-llama/Meta-Llama-3-8B-Instruct
[STEP] step=1 action={"update_matches":{"M1":"Team_Alpha"}} reward=1.00 done=true error=null
[END] success=true steps=1 rewards=1.00
```

Rules:
- Exactly one `[START]`, one `[STEP]`, one `[END]` per task
- Booleans lowercase (`true`/`false`)
- Rewards to 2 decimal places
- Action JSON with no newlines (`json.dumps(separators=(',', ':'))`)

---

## Data Models

### Action
```python
{
  "update_matches":    { "match_id": "winner_id" },   # optional
  "reallocate_servers":{ "match_id": "server_id" },   # optional
  "broadcast_message": "string",                       # optional
  "adjust_prize_pool": { "team_id": 1000.0 }          # optional
}
```

### StepResponse
```python
{
  "observation": { ... },
  "reward": 0.75,
  "done": false,
  "info": "string"
}
```

---

## Docker

```bash
docker build -t esports-env .
docker run -p 7860:7860 -e HF_TOKEN=your_token esports-env
```

---

## File Structure

```
esports-env/
  server/
    app.py             FastAPI application + web UI
    environment.py     Core environment logic
    __init__.py
  data/
    task_easy_bracket.json
    task_medium_conflict.json
    task_hard_dropout.json
  models.py            Pydantic data models
  graders.py           Reward grading functions
  inference.py         Baseline inference script
  main.py              Entry point
  client.py            OpenEnv client
  openenv.yaml         Environment manifest
  Dockerfile
  requirements.txt
```

---

## Changelog

### v2.0
- Fixed web UI: Execute buttons disabled until reset completes
- Fixed multi-worker state loss: forced single uvicorn worker
- Fixed JS crash: replaced fragile string manipulation with explicit TASK_MAP
- Removed all emoji from server code to fix Windows cp1252 encoding errors
- Added workflow guide to web UI

### v1.0
- Initial OpenEnv deployment
- Three tasks: easy/medium/hard
- Interactive web UI at /ui
- HF Spaces deployment on port 7860
