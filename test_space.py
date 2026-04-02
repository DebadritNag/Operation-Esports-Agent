#!/usr/bin/env python3
"""
Test script for the deployed Esports Tournament Environment (no tokens)
"""
import requests
import json

def test_space():
    """Test the deployed Space without any API keys."""
    
    base_url = "https://Debadrit-esports-tournament-env.hf.space"
    
    print(f"🧪 Testing Space: {base_url}")
    
    # Test 1: Health Check
    print("\n1️⃣ Health Check...")
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("✅ Space is healthy!")
        else:
            print(f"❌ Health check failed")
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return
    
    # Test 2: Environment Info
    print("\n2️⃣ Environment Info...")
    try:
        response = requests.get(base_url, timeout=10)
        if response.status_code == 200:
            info = response.json()
            print(f"✅ Name: {info['name']}")
            print(f"   Tasks: {info['available_tasks']}")
        else:
            print(f"❌ Info failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Info error: {e}")
    
    # Test 3: Easy Task
    print("\n3️⃣ Testing Easy Task...")
    try:
        # Reset
        reset_response = requests.post(f"{base_url}/reset?task_id=task_easy_bracket", timeout=10)
        if reset_response.status_code == 200:
            observation = reset_response.json()
            print(f"✅ Reset successful")
            print(f"   Alert: {observation.get('active_alerts', [])}")
            
            # Execute action
            action = {"update_matches": {"M1": "Team_Alpha"}}
            step_response = requests.post(
                f"{base_url}/step",
                json=action,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if step_response.status_code == 200:
                result = step_response.json()
                print(f"✅ Action executed")
                print(f"   Reward: {result.get('reward', 0)}")
                print(f"   Done: {result.get('done', False)}")
            else:
                print(f"❌ Action failed: {step_response.status_code}")
        else:
            print(f"❌ Reset failed: {reset_response.status_code}")
    except Exception as e:
        print(f"❌ Easy task error: {e}")
    
    # Test 4: Medium Task
    print("\n4️⃣ Testing Medium Task...")
    try:
        # Reset
        reset_response = requests.post(f"{base_url}/reset?task_id=task_medium_conflict", timeout=10)
        if reset_response.status_code == 200:
            observation = reset_response.json()
            print(f"✅ Reset successful")
            
            # Execute action
            action = {
                "reallocate_servers": {"M3": "eu-west-2"},
                "broadcast_message": "Match M3 moved due to server conflict"
            }
            step_response = requests.post(
                f"{base_url}/step",
                json=action,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if step_response.status_code == 200:
                result = step_response.json()
                print(f"✅ Action executed")
                print(f"   Reward: {result.get('reward', 0)}")
                print(f"   Done: {result.get('done', False)}")
            else:
                print(f"❌ Action failed: {step_response.status_code}")
        else:
            print(f"❌ Reset failed: {reset_response.status_code}")
    except Exception as e:
        print(f"❌ Medium task error: {e}")
    
    # Test 5: Hard Task
    print("\n5️⃣ Testing Hard Task...")
    try:
        # Reset
        reset_response = requests.post(f"{base_url}/reset?task_id=task_hard_dropout", timeout=10)
        if reset_response.status_code == 200:
            observation = reset_response.json()
            print(f"✅ Reset successful")
            print(f"   Alert: {observation.get('active_alerts', [])}")
            
            # Execute action (team dropout handling)
            action = {
                "update_matches": {"M4": "Team_Solid"},
                "adjust_prize_pool": {
                    "Team_Liquid": 0.0,
                    "Team_Solid": 2000.0,
                    "Team_Spirit": 2000.0,
                    "Team_Falcon": 2000.0
                }
            }
            step_response = requests.post(
                f"{base_url}/step",
                json=action,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if step_response.status_code == 200:
                result = step_response.json()
                print(f"✅ Action executed")
                print(f"   Reward: {result.get('reward', 0)}")
                print(f"   Done: {result.get('done', False)}")
                
                # Show prize pool distribution
                if 'observation' in result:
                    prize_pool = result['observation'].get('prize_pool_status', {})
                    print(f"   Prize Pool: {prize_pool}")
            else:
                print(f"❌ Action failed: {step_response.status_code}")
        else:
            print(f"❌ Reset failed: {reset_response.status_code}")
    except Exception as e:
        print(f"❌ Hard task error: {e}")
    
    print("\n🎉 Testing complete!")
    print(f"🌐 Visit the interactive docs: {base_url}/docs")

if __name__ == "__main__":
    test_space()