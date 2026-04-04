"""
Grading functions for the Esports Tournament Operations Manager environment.
This file contains the core grading logic used by the environment.
"""
from typing import Dict, Any
from models import Action


def grade_easy_bracket(action: Action, current_state: Dict[str, Any]) -> float:
    """
    Grade Task 1: Match processing.
    
    Agent must read match results and update bracket_state correctly.
    Returns 1.0 if the action updates bracket_state to match expected solution, 0.0 otherwise.
    """
    if not action.update_matches:
        return 0.0
    
    # Expected solution based on match results (updated to current schema)
    expected_updates = {
        "M1": "Team_Alpha"  # Based on alert: Team_Alpha defeated Team_Beta
    }
    
    # Check if the action contains the correct updates
    for match_id, expected_winner in expected_updates.items():
        if action.update_matches.get(match_id) != expected_winner:
            return 0.0
    
    return 1.0


def grade_medium_conflict(action: Action, current_state: Dict[str, Any]) -> float:
    """
    Grade Task 2: Server conflict resolution.
    
    +0.5 for correctly reallocating server without double-booking
    +0.5 for providing broadcast message
    Total between 0.0 and 1.0
    """
    score = 0.0
    
    # Extract expected solution from state
    expected = current_state.get("expected_solution", {})
    target_match = expected.get("conflict_match")
    valid_servers = expected.get("valid_servers", [])
    
    # Fallback to hardcoded values if expected_solution not present (backward compatibility)
    if not target_match:
        target_match = "M3"
        valid_servers = ["eu-west-2", "eu-west-3"]
    
    # +0.5 for correct server reallocation
    if action.reallocate_servers and target_match in action.reallocate_servers:
        reallocated_server = action.reallocate_servers[target_match]
        server_availability = current_state.get("server_availability", {})
        
        # Check if reallocated to a valid available server
        if (reallocated_server in valid_servers and 
            server_availability.get(reallocated_server, False)):
            score += 0.5
    
    # +0.5 for broadcast message
    if action.broadcast_message and len(action.broadcast_message.strip()) > 0:
        score += 0.5
    
    return min(score, 1.0)


def grade_hard_dropout(action: Action, current_state: Dict[str, Any]) -> float:
    """
    Grade Task 3: Team dropout handling.
    
    +0.4 for correctly updating match winner (forfeit)
    +0.6 for exact correct math on prize pool adjustment
    Total between 0.0 and 1.0
    """
    score = 0.0
    
    # +0.4 for correctly updating match winner (forfeit to Team_Solid)
    if action.update_matches and "M4" in action.update_matches:
        if action.update_matches["M4"] == "Team_Solid":
            score += 0.4
    
    # +0.6 for correct prize pool math
    if action.adjust_prize_pool:
        # Expected: Team_Liquid's 3000 divided among 3 remaining teams
        # Each gets 3000/3 = 1000 additional
        # Original amounts: Team_Solid=1000, Team_Spirit=1000, Team_Falcon=1000
        # New amounts: 1000 + 1000 = 2000 each
        expected_amounts = {
            "Team_Liquid": 0.0,  # loses their allocation
            "Team_Solid": 2000.0,
            "Team_Spirit": 2000.0,
            "Team_Falcon": 2000.0
        }
        
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