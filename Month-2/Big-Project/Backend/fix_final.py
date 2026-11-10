base = r'D:\Cybernaut intern\Big project (month-2)'
fname = f'{base}/app.py'

with open(fname, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix line 561 (0-indexed: 560): change '),' to '                ],),'  
# This matches the airline selectbox pattern

# The current line 561 (idx 560) is: '),\r'
# Change to: '                ],),\r'  (16 spaces + ],)

lines[560] = '                ],),\r'

# Verify the help line is correct at 16 spaces
# Line 562 (idx 561) should be: '                help="..."'
# Already checked this is correct

# Verify line 563 (idx 562) - dest selectbox start
# Should be at 12 spaces indent (inside with col1:)
# Current line 563 (idx 562): '            dest = st.selectbox(' - 12 spaces

# Write back
with open(fname, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('Fixed app.py line 561')