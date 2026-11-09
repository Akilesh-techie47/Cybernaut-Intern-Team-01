base = r'D:\\Cybernaut intern\\Big project (month-2)'
with open(f'{base}/tests/test_app.py', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

lines = content.split('\n')

for i, line in enumerate(lines):
    stripped = line.strip()
    if any(kw in stripped for kw in ['MODEL_PATH', 'PREPROCESSOR_PATH', 'EVALUATION_PATH', 'TARGET_COLUMN']):
        start = max(0, i-2)
        end = min(len(lines), i+3)
        print(f"Line {i+1}: {lines[i][:100]}")
        for j in range(start, end):
            print(f"  {j+1}: {lines[j][:80]}")
        print("---")