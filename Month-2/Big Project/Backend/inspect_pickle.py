import os, joblib, pickle

base = r'D:\Cybernaut intern\Big project (month-2)'
preprocessor_path = os.path.join(base, 'artifacts', 'models', 'preprocessor.joblib')

# Load with pickle to inspect
with open(preprocessor_path, 'rb') as f:
    data = f.read()

# Look for GLOBAL/STACK_GLOBAL patterns
for pattern in [b'GLOBAL ', b'STACK_GLOBAL']:
    idx = 0
    while True:
        idx = data.find(pattern, idx)
        if idx == -1:
            break
        start = idx + len(pattern)
        segment = data[start:start+200]
        print(f"Found {pattern.decode()}: ", end="")
        print(repr(segment[:100]))
        idx += 1

# Also try loading with joblib and checking attributes
print("\n--- Trying joblib.load ---")
try:
    proc = joblib.load(preprocessor_path)
    print("Type:", type(proc).__name__)
    print("MRO:", [c.__name__ for c in type(proc).__mro__])
    if hasattr(proc, 'transformers_'):
        print("Has transformers_ attribute")
    if hasattr(proc, 'named_steps'):
        print("Has named_steps attribute")
        print("Steps:", list(proc.named_steps.keys()))
except Exception as e:
    print("Error loading with joblib:", e)

# Try to see what the pickle contains by examining opcodes
print("\n--- Pickle opcodes ---")
f = open(preprocessor_path, 'rb')
import pickletools
pickletools.dis(f)
f.close()