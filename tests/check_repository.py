from pathlib import Path
import ast
root = Path(__file__).resolve().parents[1]
source = (root / 'main.py').read_text(encoding='utf-8')
ast.parse(source)
for filename in ['README.md', 'requirements.txt', '.gitignore']:
    assert (root / filename).exists(), filename
assert 'OPENAI_API_KEY' in source
print('Estructura y sintaxis verificadas')
