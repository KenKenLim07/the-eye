#!/usr/bin/env python3
"""
Remove the duplicate/broken function and keep only the fixed one
"""

# Read the current main.py
with open('backend/app/main.py', 'r') as f:
    content = f.read()

# Find the first function (lines 67-148 approximately)
lines = content.split('\n')
start_line = 67  # First function starts at line 67
end_line = 148   # Second function starts at line 149

# Remove the first function (broken one)
new_lines = lines[:start_line-1] + lines[end_line-1:]

# Write back to file
with open('backend/app/main.py', 'w') as f:
    f.write('\n'.join(new_lines))

print("✅ Removed duplicate function!")
print("🎯 Now using only the fixed version")
