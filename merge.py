import ast
import re
from collections import defaultdict

# ===== Parse data.csv =====
csv_data = []  # list of (word, pos, synonyms_set)

with open('data.csv', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for line in lines[1:]:  # skip header
    line = line.strip()
    if not line:
        continue
    parts = line.split(',', 2)
    if len(parts) >= 3:
        word = parts[0].strip()
        pos = parts[1].strip()
        syns = set(s.strip() for s in parts[2].split('|') if s.strip())
        csv_data.append((word, pos, syns))

# ===== Parse synonym.py =====
with open('synonym.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Strip Python comments before parsing
clean = re.sub(r'#[^\n]*', '', content)
py_groups = ast.literal_eval(clean.strip())
print(f"Loaded {len(csv_data)} entries from data.csv")
print(f"Loaded {len(py_groups)} groups from synonym.py")

# ===== Build lookup: word -> set of synonym.py group indices =====
py_word_to_groups = defaultdict(set)
for gi, group in enumerate(py_groups):
    for w in group:
        py_word_to_groups[w].add(gi)

# ===== Merge: for each data.csv entry, find synonym.py groups containing the main word =====
csv_map = {}   # word -> [pos, mutable_syns_set]
csv_order = []

for word, pos, syns in csv_data:
    csv_map[word] = [pos, set(syns)]
    csv_order.append(word)

consumed_py_groups = set()
merge_count = 0

for word in csv_order:
    pos, syns = csv_map[word]
    matched = py_word_to_groups.get(word, set())
    for gi in matched:
        if gi not in consumed_py_groups:
            consumed_py_groups.add(gi)
            new_words = set(py_groups[gi]) - {word}
            added = new_words - syns
            if added:
                syns.update(added)
                merge_count += 1

print(f"Merged synonym.py data into {merge_count} data.csv entries")

# ===== Collect unconsumed synonym.py groups as new entries =====
new_entries = 0
for gi, group in enumerate(py_groups):
    if gi not in consumed_py_groups and group:
        canonical = group[0]
        syns = set(group[1:])
        csv_map[canonical] = ['n', syns]
        csv_order.append(canonical)
        new_entries += 1

print(f"Added {new_entries} new entries from synonym.py")

# ===== Write merged.csv =====
with open('merged.csv', 'w', encoding='utf-8') as f:
    f.write('word,pos,synonym\n')
    for word in csv_order:
        pos, syns = csv_map[word]
        f.write(f'{word},{pos},{"|".join(sorted(syns))}\n')

print(f"Written {len(csv_order)} total entries to merged.csv")
