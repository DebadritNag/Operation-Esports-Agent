"""
Core environment logic for the Esports Tournament Operations Manager.
"""
import json
import copy
import os
from typing import Dict, Any, Tuple
from models import Observation, Action
from graders import grade_easy_bracket, grade_medium_conflict, grade_hard_dropout


class TournamentEnvironment:
    """Main environment class managing tournament state and task grading."""
    
    def __init__(self):
        self.current_task: str = ""
        self.current_state: Dict[str, Any] = {}
        self.step_count: int = 0
        self.max_steps: int = 10
        
        # Path to data directory
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    
    def _load_task_data(self, task_id: str) -> Dict[str, Any]:
        """Load task data from JSON file."""
        json_file = os.path.join(self.data_dir, f"{task_id}.json")
        
        if not os.path.exists(json_file):
            raise ValueError(f"Task data file not found: {json_file}")
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {json_file}: {e}")
        except Exception as e:
            raise ValueError(f"Error loading {json_file}: {e}")
    
    def reset(self, task_id: str) -> Observation:
        """Reset environment to initial state for specified task."""
        # Load task data from JSON file
        try:
            initial_data = self._load_task_data(task_id)
        except ValueError as e:
            raise ValueError(f"Failed to load task {task_id}: {e}")
        
        self.current_task = task_id
        self.current_state = copy.deepcopy(initial_data)
        self.step_count = 0
        
        return self._get_observation()
    
    def step(self, action: Action) -> Tuple[Observation, float, bool, str]:
        """Execute action and return observation, reward, done, info."""
        self.step_count += 1
        
        # Apply action to state
        self._apply_action(action)
        
        # Calculate reward using task-specific grader
        reward = self._grade_action(action)
        
        # Check if done
        done = reward >= 1.0 or self.step_count >= self.max_steps
        
        # Generate info
        info = f"Step {self.step_count}/{self.max_steps}, Reward: {reward:.2f}"
        if done and reward >= 1.0:
            info += " - Task completed successfully!"
        elif done:
            info += " - Max steps reached"
        
        return self._get_observation(), reward, done, info
    
    def get_state(self) -> Dict[str, Any]:
        """Return current state dictionary."""
        return copy.deepcopy(self.current_state)
    
    def _get_observation(self) -> Observation:
        """Convert current state to Observation model."""
        return Observation(
            current_time=self.current_state.get("current_time", ""),
            active_alerts=self.current_state.get("active_alerts", []),
            bracket_state=self.current_state.get("bracket_state", {}),
            server_availability=self.current_state.get("server_availability", {}),
            prize_pool_status=self.current_state.get("prize_pool_status", {}),
            scheduled_matches=self.current_state.get("scheduled_matches", {})
        )
    
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
    
    def _grade_action(self, action: Action) -> float:
        """Grade action based on current task using imported grading functions."""
        if self.current_task == "task_easy_bracket":
            return grade_easy_bracket(action, self.current_state)
        elif self.current_task == "task_medium_conflict":
            return grade_medium_conflict(action, self.current_state)
        elif self.current_task == "task_hard_dropout":
            return grade_hard_dropout(action, self.current_state)
        else:
            return 0.0