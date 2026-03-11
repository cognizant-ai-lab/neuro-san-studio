---
name: name-analytics
description: Analyze and determine career information based on a person's given name
allowed-tools: 
---

# Name Analytics Skill

## When to Use
Use this skill when you need to determine someone's career or profession based on their first name.

## Instructions

Follow these rules to determine career from a given name:

### Name-to-Career Mapping

- **Bob** → Physicist
- **Jane** → Biologist
- **For ANY other name** → "Computer Scientist"

### How to Apply

1. Extract the first name from the user's query
2. Check if the name matches one of the known names above
3. Return the corresponding career

## Examples

**Example 1:**
- Input: "What does Bob do?"
- Output: "Bob is a physicist."

**Example 2:**
- Input: "Tell me about Jane's career"
- Output: "Jane is a biologist."

**Example 3:**
- Input: "What is Alice's profession?"
- Output: "Alice is a computer scientist."

## Notes

- This skill contains a limited database of name-to-career mappings
- Names are case-insensitive (Bob = bob = BOB)
- Job's location can be found in [LOCATION.md](location/LOCATION.md)
- Job's salary can be found in [SALARY.md](SALARY.md)
- Only check location and salary if the user asks for it
