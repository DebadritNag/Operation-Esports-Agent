"""
Core environment logic for the Esports Tournament Operations Manager.
Includes randomization, 3-strike feedback loop, and 5-step hard limit.
"""
import json
import copy
import os
import random
from typing import Dict, Any, Tuple, List
from models import Observation, Action
from graders import grade_easy_bracket, grade_medium_conflict, grade_hard_dropout

# Team pool for hard task randomization
TEAM_POOL = ["Team_Alpha", "Team_Blaze", "Team_Cipher", "Team_Dusk", "Team_Echo", "Team_Falcon"]
BALANCE_POOL = [1200.0, 1800.0, 2400.0, 3000.0, 3600.0]

# Server pools for medium task randomization
SERVER_POOL = ["eu-west-1", "eu-west-2", "eu-west-3", "us-east-1", "us-east-2"]
MATCH_POOL  = ["M2", "M3", "M4", "M5", "M6"]


class TournamentEnvironment:
    """Main environment class managing tournament state and task grading."""

    def __init__(self):
        self.current_task: str = ""
        self.current_state: Dict[str, Any] = {}
        self.step_count: int = 0
        self.max_steps: int = 5          # Hard 5-step limit

        # Hard task dynamic solution (set on reset)
        self.expected_solution: Dict[str, float] = {}
        self.dropout_team: str = ""
        self.forfeit_match: str = ""
        self.forfeit_winner: str = ""

        # Medium task dynamic targets (set on reset)
        self.overloaded_server: str = ""
        self.target_match: str = ""

        # 3-strike counter for prize pool errors
        self.math_strikes: int = 0

        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reset(self, task_id: str) -> Observation:
        """Reset environment to initial state for specified task."""
        self.current_task = task_id
        self.step_count = 0
        self.math_strikes = 0

        if task_id == "task_hard_dropout":
            self._build_hard_task()
        elif task_id == "task_medium_conflict":
            self._build_medium_task()
        else:
            # Easy task — load from JSON as before
            try:
                initial_data = self._load_task_data(task_id)
            except ValueError as e:
                raise ValueError(f"Failed to load task {task_id}: {e}")
            self.current_state = copy.deepcopy(initial_data)

        return self._get_observation()

    def step(self, action: Action) -> Tuple[Observation, float, bool, str]:
        """Execute action and return (observation, reward, done, info)."""
        self.step_count += 1

        # Apply action to state
        self._apply_action(action)

        # Grade
        reward = self._grade_action(action)

        # Hard step limit
        if self.step_count >= self.max_steps and reward < 1.0:
            return self._get_observation(), reward, True, (
                f"Step {self.step_count}/{self.max_steps} — max steps reached. "
                f"Final reward: {reward:.2f}"
            )

        done = reward >= 1.0
        info = f"Step {self.step_count}/{self.max_steps}, Reward: {reward:.2f}"
        if done:
            info += " — Task completed successfully!"

        return self._get_observation(), reward, done, info

    def get_state(self) -> Dict[str, Any]:
        return copy.deepcopy(self.current_state)

    # ------------------------------------------------------------------
    # Task builders (randomized)
    # ------------------------------------------------------------------

    def _build_hard_task(self) -> None:
        """Build a fully randomized hard dropout task."""
        # Pick 4 teams from pool
        teams: List[str] = random.sample(TEAM_POOL, 4)
        self.dropout_team = random.choice(teams)
        active_teams = [t for t in teams if t != self.dropout_team]

        # Random starting balances (multiples of 600)
        dropout_balance = random.choice(BALANCE_POOL)
        active_balances = {t: random.choice(BALANCE_POOL) for t in active_teams}

        # Organizer gets 50 % of dropout's balance
        organizer_share = round(dropout_balance * 0.50, 2)
        # Each active team gets their current + (50 % of dropout / 3)
        active_share_each = round((dropout_balance * 0.50) / len(active_teams), 2)

        # Build expected solution
        self.expected_solution = {self.dropout_team: 0.0}
        for t in active_teams:
            self.expected_solution[t] = round(active_balances[t] + active_share_each, 2)

        # Pick a random match and winner
        self.forfeit_match  = random.choice(MATCH_POOL)
        self.forfeit_winner = random.choice(active_teams)

        prize_pool = {self.dropout_team: dropout_balance}
        prize_pool.update(active_balances)

        alert = (
            f"CRITICAL: '{self.dropout_team}' has dropped out due to illness. "
            f"Their opponent in {self.forfeit_match} was '{self.forfeit_winner}'. "
            f"Mark {self.forfeit_match} as a forfeit win for '{self.forfeit_winner}'. "
            f"Zero out {self.dropout_team}'s prize and redistribute 50% of their "
            f"${dropout_balance:.0f} equally among the {len(active_teams)} remaining teams. "
            f"The organizer retains the other 50% (${organizer_share:.0f})."
        )

        self.current_state = {
            "current_time": "09:00:00",
            "active_alerts": [alert],
            "bracket_state": {self.forfeit_match: "pending", "M5": "pending"},
            "server_availability": {"us-west-1": True},
            "prize_pool_status": prize_pool,
            "scheduled_matches": {},
        }

    def _build_medium_task(self) -> None:
        """Build a randomized medium server-conflict task."""
        # Pick an overloaded server and a different available server
        self.overloaded_server = random.choice(SERVER_POOL)
        available = [s for s in SERVER_POOL if s != self.overloaded_server]
        free_servers = random.sample(available, 2)

        # Pick two different matches
        matches = random.sample(MATCH_POOL, 2)
        overtime_match = matches[0]
        self.target_match = matches[1]

        server_availability = {self.overloaded_server: False}
        for s in free_servers:
            server_availability[s] = True

        alert = (
            f"URGENT: Match {overtime_match} is in triple overtime on server "
            f"'{self.overloaded_server}'. Match {self.target_match} is scheduled "
            f"to start on '{self.overloaded_server}' in 5 minutes. "
            f"Reallocate Match {self.target_match} to an available server and "
            f"broadcast a delay message."
        )

        self.current_state = {
            "current_time": "15:30:00",
            "active_alerts": [alert],
            "bracket_state": {overtime_match: "in_progress", self.target_match: "pending"},
            "server_availability": server_availability,
            "prize_pool_status": {},
            "scheduled_matches": {},
        }

    # ------------------------------------------------------------------
    # Action application
    # ------------------------------------------------------------------

    def _apply_action(self, action: Action) -> None:
        """Apply action to current state."""
        if action.update_matches:
            for match_id, winner_id in action.update_matches.items():
                if match_id in self.current_state.get("bracket_state", {}):
                    self.current_state["bracket_state"][match_id] = winner_id

        if action.reallocate_servers:
            if "scheduled_matches" not in self.current_state:
                self.current_state["scheduled_matches"] = {}
            for match_id, server_id in action.reallocate_servers.items():
                self.current_state["scheduled_matches"][match_id] = server_id

        if action.adjust_prize_pool:
            for team_id, amount in action.adjust_prize_pool.items():
                if team_id in self.current_state.get("prize_pool_status", {}):
                    self.current_state["prize_pool_status"][team_id] = amount

        # 3-strike feedback injection for hard task prize errors
        if self.current_task == "task_hard_dropout" and action.adjust_prize_pool:
            if not self._prize_correct(action):
                self.math_strikes += 1
                self._inject_prize_hint()

    def _prize_correct(self, action: Action) -> bool:
        """Check if prize pool adjustment matches expected solution."""
        if not action.adjust_prize_pool:
            return False
        tolerance = 0.02
        for team, expected in self.expected_solution.items():
            actual = action.adjust_prize_pool.get(team)
            if actual is None or abs(actual - expected) > tolerance:
                return False
        return True

    def _inject_prize_hint(self) -> None:
        """Inject progressive hint into active_alerts based on strike count."""
        alerts = self.current_state.get("active_alerts", [])
        # Remove any previous hint (covers both FEEDBACK and SYSTEM HINT prefixes)
        alerts = [a for a in alerts if not a.startswith("FEEDBACK:") and not a.startswith("[SYSTEM HINT")]

        if self.math_strikes == 1:
            hint = (
                "FEEDBACK: Prize pool math is wrong. "
                "Set the dropout team amount to 0. "
                "For each active team: new_amount = their_current_amount + (dropout_balance * 0.50 / num_active_teams). "
                "Use plain decimal numbers only."
            )
        elif self.math_strikes == 2:
            # Format as plain text, not JSON-like, to avoid confusing the LLM
            parts = []
            for t, v in self.expected_solution.items():
                parts.append(f"{t} should be {v}")
            hint = "FEEDBACK: Still incorrect. Correct values: " + "; ".join(parts) + "."
        else:
            hint = "FEEDBACK: Maximum attempts reached. Submit your best answer."

        alerts.append(hint)
        self.current_state["active_alerts"] = alerts

    # ------------------------------------------------------------------
    # Grading
    # ------------------------------------------------------------------

    def _grade_action(self, action: Action) -> float:
        if self.current_task == "task_easy_bracket":
            return grade_easy_bracket(action, self.current_state)
        elif self.current_task == "task_medium_conflict":
            return self._grade_medium_dynamic(action)
        elif self.current_task == "task_hard_dropout":
            return self._grade_hard_dynamic(action)
        return 0.0

    def _grade_medium_dynamic(self, action: Action) -> float:
        """Grade medium task against randomized targets."""
        score = 0.0
        if action.reallocate_servers and self.target_match in action.reallocate_servers:
            chosen = action.reallocate_servers[self.target_match]
            avail  = self.current_state.get("server_availability", {})
            if avail.get(chosen) is True and chosen != self.overloaded_server:
                score += 0.5
        if action.broadcast_message and action.broadcast_message.strip():
            score += 0.5
        return min(score, 1.0)

    def _grade_hard_dynamic(self, action: Action) -> float:
        """Grade hard task against dynamically computed expected solution."""
        score = 0.0

        # +0.4 for correct forfeit winner
        if (action.update_matches and
                action.update_matches.get(self.forfeit_match) == self.forfeit_winner):
            score += 0.4

        # +0.6 for exact prize pool
        if self._prize_correct(action):
            score += 0.6

        # Strike 3 forces done regardless of score
        if self.math_strikes >= 3:
            return score  # step() will set done=True

        return min(score, 1.0)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_observation(self) -> Observation:
        return Observation(
            current_time=self.current_state.get("current_time", ""),
            active_alerts=self.current_state.get("active_alerts", []),
            bracket_state=self.current_state.get("bracket_state", {}),
            server_availability=self.current_state.get("server_availability", {}),
            prize_pool_status=self.current_state.get("prize_pool_status", {}),
            scheduled_matches=self.current_state.get("scheduled_matches", {}),
        )

    def _load_task_data(self, task_id: str) -> Dict[str, Any]:
        json_file = os.path.join(self.data_dir, f"{task_id}.json")
        if not os.path.exists(json_file):
            raise ValueError(f"Task data file not found: {json_file}")
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {json_file}: {e}")
        except Exception as e:
            raise ValueError(f"Error loading {json_file}: {e}")
