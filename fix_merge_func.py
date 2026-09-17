#!/usr/bin/env python3
"""Replace the body of _merge_rich_detail_into_bond using file-based approach."""
path = 'backend/services/bonds/bond_service.py'

with open(path, 'r') as f:
    lines = f.readlines()

# Find start and end of the old function
start_idx = None
end_idx = None
for i, line in enumerate(lines):
    if line.startswith('def _merge_rich_detail_into_bond'):
        start_idx = i
    if start_idx is not None and i > start_idx and line.strip() == 'return bond':
        end_idx = i + 1  # include the return bond line
        break

if start_idx is None or end_idx is None:
    print(f'ERROR: start={start_idx} end={end_idx}')
    exit(1)

print(f'Replacing lines {start_idx+1} to {end_idx}')

# Read new function from a separate file
with open('/home/abmul/projects/Market-Analysis/new_merge_body.txt', 'r') as f:
    new_body = f.read()

new_lines = lines[:start_idx] + [new_body] + lines[end_idx:]
with open(path, 'w') as f:
    f.writelines(new_lines)
print('Done - function replaced')
