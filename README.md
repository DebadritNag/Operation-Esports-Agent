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

**Version 2.0** | OpenEnv-compliant agentic environment

Live Space: https://Debadrit-esports-tournament-env.hf.space
Web UI: https://Debadrit-esports-tournament-env.hf.space/ui
API Docs: https://Debadrit-esports-tournament-env.hf.space/docs
Health: https://Debadrit-esports-tournament-env.hf.space/health

---

## Environment Description and Motivation

Esports tournaments are real operational infrastructure. A major event like ESL One or The International runs on live server allocation, dynamic bracket management, and prize pool contracts — all of which must be updated in real time, often under pressure, with zero tolerance for errors. A wrong bracket update or an incorrect prize distribution is not a cosmetic bug; it affects team standings, contracts, and payouts worth thousands of dollars.

This environment models that operational reality. The agent acts as an automated Tournament Admin API — it receives live alerts about match conclusions, server conflicts, and team withdrawals, and must respond with precise, structured JSON commands. There is no room for approximation: the grader checks exact state matches, not fuzzy intent.

This is not a game or a toy because:

- The decision space mirrors real backend ops tooling used by tournament organizers
- Actions have cascading consequences — a wrong server reallocation double-books infrastructure; a wrong prize split fails financial reconciliation
- The hard task requires multi-step reasoning: parse a dropout alert, identify the forfeit winner, zero one account, and redistribute funds with correct arithmetic, all in a single atomic action
- The reward function is strict: partial credit only where operationally meaningful, full credit only on exact correctness

The goal is to test whether an LLM agent can reliably operate as a backend automation layer in a high-stakes, time-sensitive domain.

---

## Observation Space

Each call to `/reset` or `/step` returns an `Observation` object:

```python
class Observation(BaseModel):
    current_time: str          # Current tournament time (ISO format)
    active_alerts: List[str]   # Live alert messages describing what happened
    bracket_state: Dict[str, str]      # match_id -> winner_id or "pending"
    server_availability: Dict[str, bool]  # server_id -> True (available) / False (occupied)
    prize_pool_status: Dict[str, float]   # team_id -> prize amount in USD
```

Example observation:
```json
{
  "current_time": "14:00:00",
  "active_alerts": ["Match M1 has concluded. 'Team_Alpha' defeated 'Team_Beta'. Please update the bracket state."],
  "bracket_state": { "M1": "pending", "M2": "pending" },
  "server_availability": { "us-east-1": true, "us-east-2": true },
  "prize_pool_status": {}
}
```

---

## Action Space

The agent submits an `Action` object to `/step`. All fields are optional — include only what the task requires:

```python
class Action(BaseModel):
    update_matches:     Optional[Dict[str, str]]   # match_id -> winner_id
    reallocate_servers: Optional[Dict[str, str]]   # match_id -> server_id
    broadcast_message:  Optional[str]              # free-text broadcast
    adjust_prize_pool:  Optional[Dict[str, float]] # team_id -> new prize amount
```

Example action:
```json
{
  "update_matches": { "M1": "Team_Alpha" },
  "adjust_prize_pool": { "Team_Liquid": 0.0, "Team_Solid": 2000.0 }
}
```

The environment applies actions in this order: match updates, server reallocations, prize pool adjustments, then broadcasts. Unused fields are ignored.

---

## Tasks

### Task 1: Match Processing — Easy

**Task ID:** `task_easy_bracket`

**Difficulty:** Easy. Single-field update, no arithmetic, alert directly states the winner.

**Scenario:** Match M1 has concluded. The alert names the winner. The agent must update the bracket state.

**Alert:**
> "Match M1 has concluded. 'Team_Alpha' defeated 'Team_Beta'. Please update the bracket state."

**Initial State:**
```json
{
  "bracket_state": { "M1": "pending", "M2": "pending" },
  "server_availability": { "us-east-1": true, "us-east-2": true },
  "prize_pool_status": {}
}
```

**Required Action:**
```json
{ "update_matches": { "M1": "Team_Alpha" } }
```

**Grading:** `1.0` if `bracket_state` matches `{"M1": "Team_Alpha", "M2": "pending"}` exactly, `0.0` otherwise.

---

### Task 2: Server Conflict Resolution — Medium

**Task ID:** `task_medium_conflict`

**Difficulty:** Medium. Requires identifying which server is occupied, choosing an available one, and composing a broadcast — two independent sub-tasks.

**Scenario:** Match M2 is in overtime on `eu-west-1`. Match M3 is scheduled to start on the same server in 5 minutes. The agent must reallocate M3 to a free server and broadcast a delay notice.

**Alert:**
> "URGENT: Match M2 is in triple overtime on server 'eu-west-1'. Match M3 is scheduled to start on 'eu-west-1' in 5 minutes. Reallocate Match M3 to an available server and broadcast a delay message."

**Initial State:**
```json
{
  "server_availability": { "eu-west-1": false, "eu-west-2": true, "eu-west-3": true },
  "bracket_state": { "M2": "pending", "M3": "pending" }
}
```

**Required Action:**
```json
{
  "reallocate_servers": { "M3": "eu-west-2" },
  "broadcast_message": "Match M3 moved due to server conflict"
}
```

**Grading:**
- `+0.5` — M3 reallocated to an available server (`eu-west-2` or `eu-west-3`), not the occupied one
- `+0.5` — `broadcast_message` is non-empty
- Max: `1.0`

---

### Task 3: Team Dropout Management — Hard

**Task ID:** `task_hard_dropout`

**Difficulty:** Hard. Requires multi-step reasoning: parse the dropout, determine the forfeit winner, zero one prize entry, and redistribute funds with exact arithmetic across three teams.

**Scenario:** Team_Liquid has withdrawn due to illness. Their scheduled opponent in M4 was Team_Solid. The agent must mark M4 as a forfeit win, zero Team_Liquid's prize allocation, and distribute their $3,000 evenly among the three remaining teams.

**Alert:**
> "CRITICAL: 'Team_Liquid' has dropped out of the tournament due to illness. Their opponent in Match M4 was 'Team_Solid'. Mark Match M4 as a forfeit win for 'Team_Solid'. You must also completely zero out Team_Liquid's prize pool and distribute their $3000 evenly among the 3 remaining active teams (Team_Solid, Team_Spirit, Team_Falcon)."

**Initial State:**
```json
{
  "bracket_state": { "M4": "pending" },
  "prize_pool_status": {
    "Team_Liquid": 3000.0,
    "Team_Solid": 1000.0,
    "Team_Spirit": 1000.0,
    "Team_Falcon": 1000.0
  }
}
```

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

Math: `3000 / 3 = 1000` additional per team. `1000 + 1000 = 2000` each.

**Grading:**
- `+0.4` — `M4` winner set to `"Team_Solid"`
- `+0.6` — all four prize pool values match exactly (tolerance: `±0.01`)
- Max: `1.0`

---

## Baseline Scores

Scores achieved by `meta-llama/Meta-Llama-3-8B-Instruct` via the Hugging Face router API:

| Task | Task ID | Reward | Done |
|------|---------|--------|------|
| Easy - Match Processing | `task_easy_bracket` | 1.00 | true |
| Medium - Server Conflict | `task_medium_conflict` | 1.00 | true |
| Hard - Team Dropout | `task_hard_dropout` | 1.00 | true |

All three tasks solved in a single step each. The model correctly parsed the alert text and produced exact JSON actions matching the grader expectations.

---

## Setup and Usage

### Requirements

- Python 3.11+
- HF Token with inference access

### Install

```bash
pip install -r requirements.txt
```

### Run Locally

```bash
python main.py
# Server starts at http://localhost:7860
```

### Run Inference

```bash
export HF_TOKEN="your-hf-token"
export API_BASE_URL="https://router.huggingface.co/v1"
export MODEL_NAME="meta-llama/Meta-Llama-3-8B-Instruct"
python inference.py
```

### Run with Docker

```bash
docker build -t esports-env .
docker run -p 7860:7860 -e HF_TOKEN=your_token esports-env
```

### Test the Deployed Space

```bash
python test_space.py
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Environment info |
| POST | `/reset?task_id={id}` | Reset for a task |
| POST | `/step` | Execute an action |
| GET | `/state` | Current raw state |
| GET | `/health` | Health check |
| GET | `/ui` | Interactive web UI |
| GET | `/docs` | Swagger docs |

### Web UI Usage

1. Open https://Debadrit-esports-tournament-env.hf.space/ui
2. Click "Reset Task" on any task — the Execute button enables after a successful reset
3. Click "Execute Action" to run the pre-configured correct action
4. Review the reward and completion status

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HF_TOKEN` | required | Hugging Face token (API key) |
| `API_BASE_URL` | `https://router.huggingface.co/v1` | LLM API endpoint |
| `MODEL_NAME` | `meta-llama/Meta-Llama-3-8B-Instruct` | Model identifier |
| `PORT` | `7860` | Server port |
| `HOST` | `0.0.0.0` | Bind address |
| `ENABLE_WEB_INTERFACE` | `true` | Enable `/ui` |

---

## STDOUT Format

```
[START] task=task_easy_bracket env=esports_env model=meta-llama/Meta-Llama-3-8B-Instruct
[STEP] step=1 action={"update_matches":{"M1":"Team_Alpha"}} reward=1.00 done=true error=null
[END] success=true steps=1 rewards=1.00
```

Rules: one `[START]`/`[STEP]`/`[END]` per task, booleans lowercase, rewards to 2 decimal places, action JSON with no newlines.

---

## File Structure

```
esports-env/
  server/
    app.py             FastAPI app + web UI
    environment.py     Environment logic and graders
    __init__.py
  data/
    task_easy_bracket.json
    task_medium_conflict.json
    task_hard_dropout.json
  models.py            Pydantic models (Action, Observation, StepResponse)
  graders.py           Standalone grading functions
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
- Fixed JS crash: replaced fragile `string.replace('_', '-')` with explicit `TASK_MAP`
- Fixed multi-worker state loss: forced single uvicorn worker
- Fixed Windows cp1252 encoding: removed all emoji from server-side code
- Added workflow guide to web UI with disabled Execute buttons until reset

### v1.0
- Initial OpenEnv deployment with three tasks
- Interactive web UI at `/ui`
- HF Spaces on port 7860
