#!/usr/bin/env python3
"""
Simple test runner script to verify the game engine implementation.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

# Import test functions
from tests.test_commands.test_movement import (
    test_seed_world_fixture_creates_expected_rooms,
    test_player_can_move_north_from_town_square,
    test_look_command_returns_room_description,
)

def run_tests():
    """Run the test suite manually."""
    tests = [
        ("test_seed_world_fixture_creates_expected_rooms", test_seed_world_fixture_creates_expected_rooms),
        ("test_player_can_move_north_from_town_square", test_player_can_move_north_from_town_square),
        ("test_look_command_returns_room_description", test_look_command_returns_room_description),
    ]
    
    passed = 0
    failed = 0
    
    print("=" * 70)
    print("Running MUD Game Engine Tests")
    print("=" * 70)
    
    for test_name, test_func in tests:
        try:
            test_func()
            print(f"✓ {test_name} PASSED")
            passed += 1
        except AssertionError as e:
            print(f"✗ {test_name} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test_name} ERROR: {e}")
            failed += 1
    
    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)
