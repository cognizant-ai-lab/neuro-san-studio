#!/usr/bin/env python3
"""
Test Runner for Factory Sense New
Runs all test suites
"""

import sys
import os
import subprocess
from datetime import datetime

def run_test_file(test_file, description):
    """Run a test file and return results"""
    print(f"\n{'='*60}")
    print(f"RUNNING: {description}")
    print(f"File: {test_file}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run([sys.executable, test_file], 
                              capture_output=True, text=True, cwd=os.path.dirname(__file__))
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        return result.returncode == 0
    except Exception as e:
        print(f"Error running {test_file}: {e}")
        return False

def main():
    """Run all tests"""
    print("FACTORY SENSE NEW - TEST RUNNER")
    print("="*80)
    print(f"Started at: {datetime.now().isoformat()}")
    
    test_files = [
        ("test_individual_components.py", "Individual Component Tests"),
        ("test_factory_sense_new.py", "Comprehensive Test Suite"),
        ("demo_workflow.py", "Workflow Demo")
    ]
    
    results = []
    
    for test_file, description in test_files:
        if os.path.exists(test_file):
            success = run_test_file(test_file, description)
            results.append((test_file, description, success))
        else:
            print(f"⚠️  Test file not found: {test_file}")
            results.append((test_file, description, False))
    
    # Print summary
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")
    
    passed = 0
    total = len(results)
    
    for test_file, description, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status}: {description}")
        if success:
            passed += 1
    
    print(f"\nResults: {passed}/{total} tests passed")
    print(f"Completed at: {datetime.now().isoformat()}")
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 