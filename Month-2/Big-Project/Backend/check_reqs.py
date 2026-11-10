import os
path = r'D:\Cybernaut intern\Big project (month-2)\requirements.txt'
with open(path, 'rb') as f:
    raw = f.read()
print(f"File size: {len(raw)} bytes")
print(f"First 200 bytes: {raw[:200]}")
PYEOF