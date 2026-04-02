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
    Returns 1.0 if bracket_state matches expected solution exactly, 0.0 otherwise.
    """
    if not action.update_matches:
        return 0.0
    
    # Expected solution based on match results
    expected_bracket = {
        "QF1": "team_alpha",  # team_alpha (16) > team_beta (12)
        "QF2": "team_gamma",  # team_gamma (18) > team_delta (14)
        "SF1": "pending",
        "SF2": "pending", 
        "FINAL": "pending"
    }
    
    current_bracket = current_state.get("bracket_state", {})
    
    # Check if bracket state matches expected solution exactly
    for match_id, expected_winner in expected_bracket.items():
        if current_bracket.get(match_id) != expected_winner:
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
    
    # +0.5 for correct server reallocation
    if action.reallocate_servers:
        if "SF2" in action.reallocate_servers:
            reallocated_server = action.reallocate_servers["SF2"]
            server_availability = current_state.get("server_availability", {})
            
            # Check if reallocated to a backup server and it's available
            if (reallocated_server in ["backup_server_1", "backup_server_2"] and 
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
    
    # +0.4 for correctly updating match winner (forfeit)
    if action.update_matches and "SF1" in action.update_matches:
        if action.update_matches["SF1"] == "team_gamma":
            score += 0.4
    
    # +0.6 for correct prize pool math
    if action.adjust_prize_pool:
        # Expected: team_alpha's 5000 divided among 3 remaining teams
        # Each gets 5000/3 = 1666.67 additional
        # Original amounts: team_beta=2500, team_gamma=2500, team_delta=2500
        # New amounts: 2500 + 1666.67 = 4166.67 each
        expected_amounts = {
            "team_alpha": 0.0,  # loses their allocation
            "team_beta": 4166.67,
            "team_gamma": 4166.67,
            "team_delta": 4166.67
        }
        
        tolerance = 0.01  # Allow small floating point differences
        correct_adjustments = 0
        total_adjustments = len(expected_amounts)
        
        for team_id, expected_amount in expected_amounts.items():
            if team_id in action.adjust_prize_pool:
                actual_amount = action.adjust_prize_pool[team_id]
                if abs(actual_amount - expected_amount) <= tolerance:
                    correct_adjustments += 1
        
        if correct_adjustments == total_adjustments:
            score += 0.6
    
    return min(score, 1.0)