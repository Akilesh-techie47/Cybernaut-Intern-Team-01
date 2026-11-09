base = r'D:\\Cybernaut intern\\Big project (month-2)'
with open(f'{base}/tests/test_app.py', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Print the test class content
lines = content.split('\n')
in_test_class = False
test_funcs = []
brace_count = 0
for i, line in enumerate(lines):
    if 'class Test' in line and 'test_app' in line.lower():
        in_test_class = True
    if in_test_class:
        print(f"{i+1}: {line[:80]}")
    # Stop after we've seen enough
    if i > 100 and in_test_class and 'def test_' not in line and i > 50:
        # Just print first 100 lines of test class
        if i == 51:
            print(f"... ({len(lines) - 51} more lines)")
            break