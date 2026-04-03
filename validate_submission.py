#!/usr/bin/env python3
"""
Pre-submission validation script for OpenEnv environments.
Checks all requirements from the submission checklist.
"""
import os
import sys
import json
import requests
import subprocess
from typing import Dict, Any, List

def check_hf_space(space_url: str) -> bool:
    """Check if HF Space deploys and responds correctly."""
    print("Checking HF Space deployment...")
    
    try:
        # Test basic connectivity
        response = requests.get(space_url, timeout=30)
        if response.status_code != 200:
            print(f"X Space URL returned {response.status_code}")
            return False
        
        # Test health endpoint
        health_response = requests.get(f"{space_url}/health", timeout=10)
        if health_response.status_code != 200:
            print(f"X Health endpoint returned {health_response.status_code}")
            return False
        
        # Test reset endpoint
        reset_response = requests.post(f"{space_url}/reset?task_id=task_easy_bracket", timeout=10)
        if reset_response.status_code != 200:
            print(f"X Reset endpoint returned {reset_response.status_code}")
            return False
        
        print("✓ HF Space deployment: PASSED")
        return True
        
    except Exception as e:
        print(f"X HF Space check failed: {e}")
        return False

def check_openenv_compliance() -> bool:
    """Check OpenEnv spec compliance."""
    print("Checking OpenEnv compliance...")
    
    try:
        result = subprocess.run(['openenv', 'validate'], 
                              capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("✓ OpenEnv compliance: PASSED")
            return True
        else:
            print(f"X OpenEnv validation failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"X OpenEnv validation error: {e}")
        return False

def check_inference_script() -> bool:
    """Check inference script compliance."""
    print("Checking inference script...")
    
    # Check file exists
    if not os.path.exists('inference.py'):
        print("X inference.py not found in root directory")
        return False
    
    # Check required variables
    with open('inference.py', 'r') as f:
        content = f.read()
        
    required_vars = ['API_BASE_URL', 'MODEL_NAME', 'HF_TOKEN']
    for var in required_vars:
        if var not in content:
            print(f"X Required variable {var} not found in inference.py")
            return False
    
    # Check OpenAI client usage
    if 'from openai import OpenAI' not in content:
        print("X Must use OpenAI client for LLM calls")
        return False
    
    # Check STDOUT format
    stdout_patterns = ['[START]', '[STEP]', '[END]']
    for pattern in stdout_patterns:
        if pattern not in content:
            print(f"X Required STDOUT pattern {pattern} not found")
            return False
    
    print("✓ Inference script: PASSED")
    return True

def check_tasks_and_graders() -> bool:
    """Check that 3+ tasks exist with graders."""
    print("Checking tasks and graders...")
    
    # Check openenv.yaml
    if not os.path.exists('openenv.yaml'):
        print("X openenv.yaml not found")
        return False
    
    # Check graders.py
    if not os.path.exists('graders.py'):
        print("X graders.py not found")
        return False
    
    # Check for at least 3 tasks
    with open('graders.py', 'r') as f:
        grader_content = f.read()
    
    task_functions = ['grade_easy_bracket', 'grade_medium_conflict', 'grade_hard_dropout']
    for func in task_functions:
        if func not in grader_content:
            print(f"X Grader function {func} not found")
            return False
    
    print("✓ Tasks and graders: PASSED")
    return True

def check_dockerfile() -> bool:
    """Check Dockerfile exists and is properly configured."""
    print("Checking Dockerfile...")
    
    if not os.path.exists('Dockerfile'):
        print("X Dockerfile not found")
        return False
    
    with open('Dockerfile', 'r') as f:
        dockerfile_content = f.read()
    
    # Check for port 7860 (HF Spaces requirement)
    if '7860' not in dockerfile_content:
        print("X Dockerfile must expose port 7860 for HF Spaces")
        return False
    
    print("✓ Dockerfile: PASSED")
    return True

def run_validation(space_url: str) -> bool:
    """Run complete validation suite."""
    print("Running Pre-Submission Validation")
    print("=" * 50)
    
    checks = [
        ("HF Space Deployment", lambda: check_hf_space(space_url)),
        ("OpenEnv Compliance", check_openenv_compliance),
        ("Inference Script", check_inference_script),
        ("Tasks & Graders", check_tasks_and_graders),
        ("Dockerfile", check_dockerfile),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append(result)
        except Exception as e:
            print(f"X {name} check failed with error: {e}")
            results.append(False)
        print()
    
    print("=" * 50)
    print("VALIDATION SUMMARY")
    print("=" * 50)
    
    for i, (name, _) in enumerate(checks):
        status = "✓ PASSED" if results[i] else "X FAILED"
        print(f"{name}: {status}")
    
    all_passed = all(results)
    print()
    if all_passed:
        print("ALL CHECKS PASSED - Ready for submission!")
    else:
        print("Some checks failed - Please fix before submitting")
    
    return all_passed

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python validate_submission.py <space_url>")
        print("Example: python validate_submission.py https://your-space.hf.space")
        sys.exit(1)
    
    space_url = sys.argv[1].rstrip('/')
    success = run_validation(space_url)
    sys.exit(0 if success else 1)