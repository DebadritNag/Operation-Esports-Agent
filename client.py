"""
Client interface for the Esports Tournament Operations Manager environment.
"""
import os
import json
import requests
from typing import Dict, Any
from openai import OpenAI

from models import Action, Observation, StepResponse


class EsportsClient:
    """Client for interacting with the esports tournament environment."""
    
    def __init__(self, base_url: str = "http://localhost:8001"):
        """
        Initialize the client.
        
        Args:
            base_url: Base URL of the environment server
        """
        self.base_url = base_url
        
    def reset(self, task_id: str) -> Observation:
        """Reset environment for a specific task."""
        response = requests.post(f"{self.base_url}/reset?task_id={task_id}", timeout=10)
        response.raise_for_status()
        return Observation(**response.json())
    
    def step(self, action: Action) -> StepResponse:
        """Execute an action in the environment."""
        response = requests.post(
            f"{self.base_url}/step",
            json=action.model_dump(),
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        response.raise_for_status()
        return StepResponse(**response.json())
    
    def get_state(self) -> Dict[str, Any]:
        """Get current environment state."""
        response = requests.get(f"{self.base_url}/state", timeout=5)
        response.raise_for_status()
        return response.json()
    
    def health_check(self) -> bool:
        """Check if the environment server is healthy."""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except Exception:
            return False


class EsportsInferenceClient(EsportsClient):
    """Extended client with LLM inference capabilities."""
    
    def __init__(self, base_url: str = "http://localhost:8001"):
        super().__init__(base_url)
        
        # LLM configuration
        self.api_key = os.getenv("HF_TOKEN")
        self.api_base_url = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
        self.model_name = os.getenv("MODEL_NAME", "meta-llama/Meta-Llama-3-8B-Instruct")
        
        if not self.api_key:
            raise ValueError("HF_TOKEN environment variable is required")
        
        # Initialize OpenAI client
        self.llm_client = OpenAI(
            base_url=self.api_base_url,
            api_key=self.api_key
        )
        
        # Task descriptions for the LLM
        self.task_descriptions = {
            "task_easy_bracket": """
            You are managing an esports tournament bracket. You need to:
            1. Read the match results from active_alerts
            2. Determine the winners based on the alert message
            3. Update the bracket_state with the correct winners
            
            The alert contains match results. Extract the winner and update only the matches that have results.
            """,
            
            "task_medium_conflict": """
            You are handling a server conflict during a tournament. You need to:
            1. A match has gone into triple overtime causing server conflicts
            2. Reallocate the conflicted match to an available server
            3. Send a broadcast message to notify teams about the change
            
            Check server_availability to find available servers.
            Use reallocate_servers to move matches and broadcast_message to notify.
            """,
            
            "task_hard_dropout": """
            You are handling a team dropout situation. You need to:
            1. A team has dropped out due to illness
            2. Award their current match to their opponent (forfeit)
            3. Recalculate the prize pool by distributing the dropped team's allocation evenly among remaining teams
            
            Use update_matches to record the forfeit and adjust_prize_pool to redistribute money.
            """
        }
    
    def query_llm(self, observation: Observation, task_description: str) -> Action:
        """Query the LLM for an action based on the observation."""
        system_prompt = f"""You are an AI agent managing an esports tournament. {task_description}

You must respond with a valid JSON object containing an action. The action can have these optional fields:
- update_matches: dict mapping match_id to winner_id
- reallocate_servers: dict mapping match_id to server_id  
- broadcast_message: string message to broadcast
- adjust_prize_pool: dict mapping team_id to new prize amount

Only include fields that are relevant to the current task.

Example response format:
{{
    "update_matches": {{"M1": "Team_Alpha"}},
    "broadcast_message": "Match schedule updated due to server conflict"
}}"""
        
        user_prompt = f"""Current tournament observation:
{observation.model_dump_json(indent=2)}

Based on this observation and the active alerts, what action should be taken?
Respond with only a JSON object containing the action."""
        
        response = self.llm_client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=500
        )
        
        action_text = response.choices[0].message.content.strip()
        
        # Try to extract JSON from the response
        if action_text.startswith("```json"):
            action_text = action_text.split("```json")[1].split("```")[0].strip()
        elif action_text.startswith("```"):
            action_text = action_text.split("```")[1].split("```")[0].strip()
        
        action_dict = json.loads(action_text)
        return Action(**action_dict)
    
    def run_episode(self, task_id: str, max_steps: int = 10) -> Dict[str, Any]:
        """Run a complete episode for a task."""
        observation = self.reset(task_id)
        task_description = self.task_descriptions.get(task_id, "")
        
        episode_data = {
            "task_id": task_id,
            "steps": [],
            "total_reward": 0.0,
            "success": False
        }
        
        for step in range(max_steps):
            try:
                # Query LLM for action
                action = self.query_llm(observation, task_description)
                
                # Execute action
                step_response = self.step(action)
                
                step_data = {
                    "step": step + 1,
                    "action": action.model_dump(),
                    "reward": step_response.reward,
                    "done": step_response.done,
                    "observation": step_response.observation.model_dump()
                }
                
                episode_data["steps"].append(step_data)
                episode_data["total_reward"] += step_response.reward
                
                if step_response.done:
                    episode_data["success"] = step_response.reward >= 1.0
                    break
                    
                observation = step_response.observation
                
            except Exception as e:
                step_data = {
                    "step": step + 1,
                    "action": {},
                    "reward": 0.0,
                    "done": True,
                    "error": str(e)
                }
                episode_data["steps"].append(step_data)
                break
        
        return episode_data