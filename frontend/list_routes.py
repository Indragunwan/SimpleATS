with open('../backend/server.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Let's print out all route lines
lines = text.split('\n')
for idx, line in enumerate(lines):
    if '@api.' in line:
        print(f'{idx+1}: {line}')
