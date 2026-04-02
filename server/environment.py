"""
Core environment logic for the Esports Tournament Operations Manager.
"""
import json
import copy
import os
from typing import Dict, Any, Tuple
from models import Observation, Action


class TournamentEnvironment:
    """Main environment class managing tournament state and task grading."""
    
    def __init__(self):
        self.current_task: str = ""
        self.current_state: Dict[str, Any] = {}
        self.step_count: int = 0
        self.max_steps: int = 10
        
        # Path to data directory
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        
        # Expected exact solutions for grading (updated to match new JSON structure)
        self.expected_solutions = {
            "task_easy_bracket": {
                "bracket_state": {
                    "M1": "Team_Alpha",  # Based on alert: Team_Alpha defeated Team_Beta
                    "M2": "pending"
                }
            },
            "task_medium_conflict": {
                # M3 should be reallocated to an available server (eu-west-2 or eu-west-3)
                "available_servers": ["eu-west-2", "eu-west-3"]
            },
            "task_hard_dropout": {
                "bracket_state": {"M4": "Team_Solid"},  # forfeit win to Team_Solid
                "prize_pool_adjustment": {
                    "Team_Liquid": 0.0,  # loses their allocation
                    "Team_Solid": 2000.0,  # 1000 + 1000 (3000/3)
                    "Team_Spirit": 2000.0,  # 1000 + 1000 (3000/3)
                    "Team_Falcon": 2000.0   # 1000 + 1000 (3000/3)
                }
            }
        }
    
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
            prize_pool_status=self.current_state.get("prize_pool_status", {})
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
        """Grade action based on current task."""
        if self.current_task == "task_easy_bracket":
            return self._grade_easy_bracket(action)
        elif self.current_task == "task_medium_conflict":
            return self._grade_medium_conflict(action)
        elif self.current_task == "task_hard_dropout":
            return self._grade_hard_dropout(action)
        else:
            return 0.0
    
    def _grade_easy_bracket(self, action: Action) -> float:
        """Grade Task 1: Match processing - 1.0 if bracket_state matches expected exact JSON, 0.0 otherwise."""
        if not action.update_matches:
            return 0.0
        
        expected = self.expected_solutions["task_easy_bracket"]["bracket_state"]
        current = self.current_state["bracket_state"]
        
        # Check if bracket state matches expected solution exactly
        if current == expected:
            return 1.0
        else:
            return 0.0
    
    def _grade_medium_conflict(self, action: Action) -> float:
        """Grade Task 2: Server conflict - +0.5 for reallocation without double-booking, +0.5 for broadcast."""
        score = 0.0
        
        # +0.5 for correct server reallocation without double-booking
        if action.reallocate_servers:
            if "M3" in action.reallocate_servers:
                reallocated_server = action.reallocate_servers["M3"]
                server_availability = self.current_state.get("server_availability", {})
                available_servers = self.expected_solutions["task_medium_conflict"]["available_servers"]
                
                # Check if reallocated to an available server (not eu-west-1 which is occupied)
                if (reallocated_server in available_servers and 
                    server_availability.get(reallocated_server, False)):
                    score += 0.5
        
        # +0.5 for broadcast message
        if action.broadcast_message and len(action.broadcast_message.strip()) > 0:
            score += 0.5
        
        return min(score, 1.0)
    
    def _grade_hard_dropout(self, action: Action) -> float:
        """Grade Task 3: Team dropout - +0.4 for match winner, +0.6 for exact prize pool math."""
        score = 0.0
        
        # +0.4 for correctly updating match winner (forfeit to Team_Solid)
        if action.update_matches and "M4" in action.update_matches:
            if action.update_matches["M4"] == "Team_Solid":
                score += 0.4
        
        # +0.6 for exact correct prize pool math
        if action.adjust_prize_pool:
            expected_amounts = self.expected_solutions["task_hard_dropout"]["prize_pool_adjustment"]
            
            tolerance = 0.01  # Allow small floating point differences
            all_correct = True
            
            for team_id, expected_amount in expected_amounts.items():
                if team_id not in action.adjust_prize_pool:
                    all_correct = False
                    break
                actual_amount = action.adjust_prize_pool[team_id]
                if abs(actual_amount - expected_amount) > tolerance:
                    all_correct = False
                    break
            
            if all_correct:
                score += 0.6
        
        return min(score, 1.0)