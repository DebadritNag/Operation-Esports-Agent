"""
Core environment logic for the Esports Tournament Operations Manager.
"""
import json
import copy
import os
import random
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
    
    def _generate_medium_task_state(self) -> Dict[str, Any]:
        """Generate randomized state for medium task (server conflict resolution)."""
        # Pool of possible matches and servers
        pending_matches = ["M3", "M4", "M5", "M6"]
        all_servers = ["eu-west-1", "us-east-1", "ap-south-1", "eu-west-2", "eu-west-3", "us-west-2"]
        
        # Randomly select conflict match and overloaded server
        target_match = random.choice(pending_matches)
        overloaded_server = random.choice(all_servers[:3])  # Choose from first 3 as overloaded
        
        # Select 1-2 available backup servers (not the overloaded one)
        available_pool = [s for s in all_servers if s != overloaded_server]
        num_backups = random.randint(1, 2)
        backup_servers = random.sample(available_pool, num_backups)
        
        # Build server availability dict
        server_availability = {overloaded_server: False}
        for backup in backup_servers:
            server_availability[backup] = True
        
        # Add some unavailable servers for realism
        remaining_servers = [s for s in all_servers if s not in server_availability]
        for server in remaining_servers[:2]:  # Add 2 more unavailable servers
            server_availability[server] = False
        
        # Construct dynamic alert message
        active_alerts = [
            f"URGENT: Match M2 is in triple overtime on server '{overloaded_server}'. "
            f"Match {target_match} is scheduled to start on '{overloaded_server}' in 5 minutes. "
            f"Reallocate Match {target_match} to an available server and broadcast a delay message."
        ]
        
        # Build state with hidden expected_solution
        state = {
            "current_time": "15:30:00",
            "active_alerts": active_alerts,
            "bracket_state": {
                "M2": "in_progress",
                target_match: "pending"
            },
            "server_availability": server_availability,
            "prize_pool_status": {},
            "expected_solution": {
                "conflict_match": target_match,
                "valid_servers": backup_servers
            }
        }
        
        return state
    
    def reset(self, task_id: str) -> Observation:
        """Reset environment to initial state for specified task."""
        # Use dynamic generation for medium task, static JSON for others
        if task_id == "task_medium_conflict":
            initial_data = self._generate_medium_task_state()
        else:
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
        """Convert current state to Observation model (excludes expected_solution)."""
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