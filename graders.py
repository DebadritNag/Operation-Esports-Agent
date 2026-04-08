"""
Grading functions for the Esports Tournament Operations Manager environment.
This file contains the core grading logic used by the environment.
"""
from typing import Dict, Any
from models import Action


def grade_easy_bracket(action: Action, current_state: Dict[str, Any]) -> float:
    """
    Grade Task 1: Match processing.
    
    Easy task with multiple scoring levels:
    - 0.85-0.90: Perfect execution with correct match update
    - 0.70-0.80: Correct match but with extra unnecessary fields
    - 0.50-0.60: Partially correct (right concept, wrong details)
    - 0.20-0.30: Attempted but mostly wrong
    - 0.0: No valid attempt
    """
    if not action.update_matches:
        return 0.01  # Minimum score instead of 0.0
    
    # Expected solution based on match results
    expected_updates = {
        "M1": "Team_Alpha"  # Based on alert: Team_Alpha defeated Team_Beta
    }
    
    score = 0.0
    
    # Check if the action contains the correct updates
    correct_matches = 0
    total_expected = len(expected_updates)
    
    for match_id, expected_winner in expected_updates.items():
        if match_id in action.update_matches:
            if action.update_matches[match_id] == expected_winner:
                correct_matches += 1
            else:
                # Wrong winner for this match
                score += 0.25  # Partial credit for attempting the right match
    
    if correct_matches == total_expected:
        # Perfect match updates
        base_score = 0.87  # High score for easy task
        
        # Small deductions for unnecessary fields
        if action.reallocate_servers:
            base_score -= 0.05  # Unnecessary server reallocation
        if action.broadcast_message:
            base_score -= 0.03  # Unnecessary broadcast
        if action.adjust_prize_pool:
            base_score -= 0.05  # Unnecessary prize adjustment
            
        return max(base_score, 0.75)  # Minimum 0.75 for correct answer
    
    elif correct_matches > 0:
        # Some correct matches
        return 0.55 + (correct_matches / total_expected) * 0.15
    
    elif len(action.update_matches) > 0:
        # Attempted but all wrong
        return 0.25
    
    return 0.01  # Minimum score instead of 0.0


def grade_medium_conflict(action: Action, current_state: Dict[str, Any]) -> float:
    """
    Grade Task 2: Server conflict resolution (multi-step required).
    
    Medium task requiring 2-3 steps for full completion:
    Phase 1 (0.20-0.30): Initial server reallocation only
    Phase 2 (0.40-0.50): Broadcast notification (requires previous reallocation)
    Phase 3 (0.60-0.72): Follow-up verification and confirmation
    
    Actions with both server reallocation AND broadcast in step 1 are penalized
    to encourage proper multi-step workflow.
    """
    score = 0.0
    server_score = 0.0
    message_score = 0.0
    
    # Get step count from current state (environment should track this)
    step_count = current_state.get("step_count", 1)
    
    # Server reallocation scoring (Phase 1)
    if action.reallocate_servers:
        server_availability = current_state.get("server_availability", {})
        for match_id, server_id in action.reallocate_servers.items():
            if server_availability.get(server_id) is True:
                server_score = 0.25  # Base server reallocation score
                break
            elif server_id in server_availability:
                server_score = 0.12  # Attempted but chose unavailable server
            else:
                server_score = 0.08  # Attempted but invalid server
    
    # Message scoring (Phase 2)
    if action.broadcast_message and action.broadcast_message.strip():
        message = action.broadcast_message.lower()
        message_length = len(action.broadcast_message.strip())
        
        # Base message score
        message_score = 0.20
        
        # Bonus for relevant keywords
        relevant_keywords = ['delay', 'conflict', 'server', 'reallocate', 'reschedule', 'technical']
        keyword_count = sum(1 for keyword in relevant_keywords if keyword in message)
        message_score += min(keyword_count * 0.04, 0.12)  # Up to 0.12 bonus
        
        # Bonus for appropriate length
        if 20 <= message_length <= 100:
            message_score += 0.04
        elif message_length < 10:
            message_score -= 0.08  # Too brief
        elif message_length > 150:
            message_score -= 0.04  # Too verbose
    
    base_score = server_score + message_score
    
    # Multi-step progression bonuses and penalties
    if step_count == 1:
        # First step: Penalize doing both actions at once
        if action.reallocate_servers and action.broadcast_message:
            # Penalty for trying to do everything in one step
            base_score *= 0.6  # 40% penalty for not following proper workflow
            return min(base_score, 0.35)  # Hard cap for single-step attempts
        elif server_score > 0:
            # Good: Server reallocation only in first step
            return min(base_score, 0.30)
        elif message_score > 0:
            # Suboptimal: Message without server reallocation first
            return min(base_score * 0.7, 0.25)
        return max(base_score, 0.01)  # Minimum 0.01
    
    elif step_count == 2:
        # Second step: Reward proper sequencing
        if server_score > 0 and message_score > 0:
            # Both components present - check if server was done in previous step
            base_score += 0.10  # Proper sequencing bonus
            return min(base_score, 0.58)
        elif message_score > 0:
            # Message only in second step (assuming server was done in step 1)
            base_score += 0.08  # Continuation bonus
            return min(base_score, 0.55)
        return max(min(base_score, 0.50), 0.01)  # Minimum 0.01
    
    elif step_count >= 3:
        # Third+ step: Full scoring potential unlocked
        if server_score > 0 and message_score > 0:
            base_score += 0.15  # Full completion bonus
            
            # Additional bonus for comprehensive approach
            if (action.reallocate_servers and action.broadcast_message and 
                len(action.broadcast_message.strip()) >= 30):
                base_score += 0.08  # Thoroughness bonus
                
        elif message_score > 0:
            # Follow-up message or verification
            base_score += 0.12  # Continuation bonus
            
        return max(min(base_score, 0.72), 0.01)  # Medium task max score, minimum 0.01
    
    return max(min(base_score, 0.72), 0.01)  # Minimum 0.01


def grade_hard_dropout(action: Action, current_state: Dict[str, Any]) -> float:
    """
    Grade Task 3: Team dropout handling (multi-step required).
    
    Hard task requiring 3-4 steps for full completion:
    Phase 1 (0.10-0.18): Initial match forfeit declaration
    Phase 2 (0.20-0.28): Prize pool analysis and partial redistribution
    Phase 3 (0.35-0.42): Complete prize pool redistribution
    Phase 4 (0.45-0.52): Final verification and cleanup
    
    Single-step attempts are capped at 0.25 to encourage multi-step approach.
    """
    score = 0.0
    match_score = 0.0
    prize_score = 0.0
    
    # Get step count from current state (environment should track this)
    step_count = current_state.get("step_count", 1)
    
    # Match update scoring (Phase 1)
    if action.update_matches and "M4" in action.update_matches:
        if action.update_matches["M4"] == "Team_Solid":
            match_score = 0.15  # Reduced base score to encourage multi-step
        else:
            match_score = 0.06  # Attempted but wrong winner
    elif action.update_matches:
        # Attempted match updates but wrong match ID
        match_score = 0.04
    
    # Prize pool scoring (Phase 2-4)
    if action.adjust_prize_pool:
        expected_amounts = {
            "Team_Liquid": 0.0,  # loses their allocation
            "Team_Solid": 2000.0,
            "Team_Spirit": 2000.0,
            "Team_Falcon": 2000.0
        }
        
        prize_attempts = 0
        correct_prizes = 0
        close_prizes = 0
        partial_prizes = 0
        
        for team_id, expected_amount in expected_amounts.items():
            if team_id in action.adjust_prize_pool:
                prize_attempts += 1
                actual_amount = action.adjust_prize_pool[team_id]
                
                if abs(actual_amount - expected_amount) < 0.01:
                    correct_prizes += 1
                elif abs(actual_amount - expected_amount) < 100:  # Close but not exact
                    close_prizes += 1
                elif actual_amount > 0:  # Some attempt at redistribution
                    partial_prizes += 1
        
        # Base score for attempting prize adjustments
        if prize_attempts > 0:
            prize_score = 0.06
            
            # Bonus for correct number of teams
            if prize_attempts == len(expected_amounts):
                prize_score += 0.04
            elif prize_attempts >= 2:
                prize_score += 0.02
            
            # Progressive scoring based on accuracy
            if correct_prizes == len(expected_amounts):
                prize_score += 0.15  # Perfect prize calculation
            elif correct_prizes > 0:
                prize_score += 0.10 * (correct_prizes / len(expected_amounts))
            elif close_prizes > 0:
                prize_score += 0.06 * (close_prizes / len(expected_amounts))
            elif partial_prizes > 0:
                prize_score += 0.03 * (partial_prizes / len(expected_amounts))
            
            # Bonus for zeroing out dropout team
            if "Team_Liquid" in action.adjust_prize_pool and action.adjust_prize_pool["Team_Liquid"] == 0.0:
                prize_score += 0.03
    
    base_score = match_score + prize_score
    
    # Multi-step progression system
    if step_count == 1:
        # First step: Heavily capped to encourage continuation
        if base_score > 0:
            return min(base_score, 0.25)
        return max(base_score, 0.01)  # Minimum 0.01
    
    elif step_count == 2:
        # Second step: Allow moderate progress
        if match_score > 0 and prize_score > 0:
            base_score += 0.05  # Multi-component bonus
        return max(min(base_score, 0.35), 0.01)  # Minimum 0.01
    
    elif step_count == 3:
        # Third step: Higher scoring potential
        if match_score > 0 and prize_score > 0:
            base_score += 0.08  # Progression bonus
            
            # Bonus for comprehensive prize handling
            if (action.adjust_prize_pool and 
                len(action.adjust_prize_pool) >= 3 and
                "Team_Liquid" in action.adjust_prize_pool):
                base_score += 0.04  # Thoroughness bonus
                
        return max(min(base_score, 0.45), 0.01)  # Minimum 0.01
    
    elif step_count >= 4:
        # Fourth+ step: Full scoring potential unlocked
        if match_score > 0 and prize_score > 0:
            base_score += 0.10  # Full completion bonus
            
            # Maximum bonus for perfect execution
            if (action.adjust_prize_pool and 
                len(action.adjust_prize_pool) == 4 and
                all(team in action.adjust_prize_pool for team in ["Team_Liquid", "Team_Solid", "Team_Spirit", "Team_Falcon"])):
                base_score += 0.06  # Perfect execution bonus
        
        # Small penalty for unnecessary fields in final steps
        if action.broadcast_message:
            base_score -= 0.01  # Small penalty for unnecessary broadcast
        if action.reallocate_servers:
            base_score -= 0.01  # Small penalty for unnecessary reallocation
            
        return max(min(base_score, 0.52), 0.01)  # Hard task max score, minimum 0.01
    
    return max(min(base_score, 0.52), 0.01)  # No negative scores, minimum 0.01