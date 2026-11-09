base = r'D:\Cybernaut intern\Big project (month-2)'
fname = f'{base}/app.py'

with open(fname, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the CSS definition line and add dotenv import before it
for i, line in enumerate(lines):
    if 'CSS = """' in line:
        # Insert dotenv import and load before CSS
        # Shift the CSS line down
        css_line = lines[i]
        lines[i] = '\nimport dotenv\nimport os\n\ndotenv.load_dotenv()\n'
        # Now the CSS line needs to stay, but we've added before it
        print(f'Added dotenv at line {i}')
        break

with open(fname, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('dotenv added to app.py')