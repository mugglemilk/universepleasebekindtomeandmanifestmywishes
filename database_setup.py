import ast
import re
import sqlite3
import unicodedata
from collections import defaultdict


def load_csv(path):
    data = []
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split(',', 2)
        if len(parts) >= 3:
            word = parts[0].strip()
            pos = parts[1].strip()
            syns = set(s.strip() for s in parts[2].split('|') if s.strip())
            data.append((word, pos, syns))
    return data

def load_synonym_py(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    clean = re.sub(r'#[^\n]*', '', content)
    return ast.literal_eval(clean.strip())


def merge(csv_data, py_groups):
    py_word_to_groups = defaultdict(set)
    for gi, group in enumerate(py_groups):
        for w in group:
            py_word_to_groups[w].add(gi)

    csv_map = {}
    csv_order = []
    for word, pos, syns in csv_data:
        csv_map[word] = [pos, set(syns)]
        csv_order.append(word)

    consumed = set()
    for word in csv_order:
        pos, syns = csv_map[word]
        for gi in py_word_to_groups.get(word, set()):
            if gi not in consumed:
                consumed.add(gi)
                syns.update(set(py_groups[gi]) - {word})
    duplicates = []
    for gi, group in enumerate(py_groups):
        if gi not in consumed and group:
            canonical = group[0]
            csv_map[canonical] = ['n', set(group[1:])]
            csv_order.append(canonical)

    return csv_map, csv_order


def create_db():
    print("โหลดข้อมูลจาก data.csv ...")
    csv_data = load_csv('data.csv')
    print(f"  {len(csv_data)} entries")

    print("โหลดข้อมูลจาก synonym.py ...")
    py_groups = load_synonym_py('synonym.py')
    print(f"  {len(py_groups)} groups")

    print("Merge ข้อมูล ...")
    csv_map, csv_order = merge(csv_data, py_groups)
    print(f"  {len(csv_order)} total entries after merge")

    conn = sqlite3.connect('synonyms.db')
    cursor = conn.cursor()

    cursor.execute('DROP TABLE IF EXISTS word_mappings')
    cursor.execute('DROP TABLE IF EXISTS synonym_groups')
    cursor.execute('''
        CREATE TABLE synonym_groups (
            group_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE word_mappings (
            word TEXT,
            group_id INTEGER,
            is_canonical INTEGER DEFAULT 0,
            FOREIGN KEY (group_id) REFERENCES synonym_groups(group_id),
            PRIMARY KEY (word, group_id)
        )
    ''')

    print("บันทึกลง SQLite ...")
    for word in csv_order:
        pos, syns = csv_map[word]
        all_words = [word] + list(syns)
        cursor.execute('INSERT INTO synonym_groups (source) VALUES (?)', (pos,))
        group_id = cursor.lastrowid
        for i, w in enumerate(all_words):
            cursor.execute(
                'INSERT OR IGNORE INTO word_mappings (word, group_id, is_canonical) VALUES (?, ?, ?)',
                (w, group_id, 1 if i == 0 else 0)
            )

    print("สร้าง INDEX ...")
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_word ON word_mappings(word)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_group_id ON word_mappings(group_id)')

    print("ลบคำ blacklist ...")
    try:
        with open('blacklist.txt', 'r', encoding='utf-8') as f:
            blacklist = [line.strip() for line in f if line.strip()]
        removed = 0
        for w in blacklist:
            cursor.execute('DELETE FROM word_mappings WHERE word = ?', (w,))
            removed += cursor.rowcount
        print(f"  ลบออก {removed} คำ")
    except FileNotFoundError:
        print("  ไม่พบ blacklist.txt ข้ามขั้นตอนนี้")

    conn.commit()
    conn.close()
    print("\nสร้างฐานข้อมูลเสร็จสิ้น!")

# ══════════════════════════════════════════

def thai_sort_key(text):
    return unicodedata.normalize("NFC", str(text)) if text else ""

def sort_db(db_path="synonyms.db"):
    """
    เรียง group_id ใหม่ให้ canonical word ของแต่ละกลุ่ม
    เรียงตามตัวอักษรไทย ก-ฮ โดยสร้างตารางใหม่แทนที่ของเดิม
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # ดึง canonical word ของแต่ละกลุ่ม พร้อม source
    cursor.execute("""
        SELECT sg.group_id, sg.source, wm.word AS canonical_word
        FROM synonym_groups sg
        LEFT JOIN word_mappings wm
            ON sg.group_id = wm.group_id AND wm.is_canonical = 1
        ORDER BY sg.group_id
    """)
    groups = cursor.fetchall()  # [(group_id, source, canonical_word), ...]

    # เรียงตาม canonical_word ก-ฮ
    groups_sorted = sorted(
        groups,
        key=lambda r: thai_sort_key(r[2] or "")
    )

    # ดึง word_mappings ทั้งหมด
    cursor.execute("SELECT word, group_id, is_canonical FROM word_mappings")
    mappings = cursor.fetchall()

    # สร้าง mapping: old_group_id → all rows
    old_group_to_rows = defaultdict(list)
    for word, gid, is_can in mappings:
        old_group_to_rows[gid].append((word, is_can))

    # สร้าง old_group_id → new_group_id ตามลำดับที่เรียงแล้ว
    old_to_new = {
        old_gid: new_gid
        for new_gid, (old_gid, _, _) in enumerate(groups_sorted, start=1)
    }

    # สร้างตารางใหม่แทน
    cursor.execute("DROP TABLE IF EXISTS word_mappings")
    cursor.execute("DROP TABLE IF EXISTS synonym_groups")

    cursor.execute("""
        CREATE TABLE synonym_groups (
            group_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE word_mappings (
            word TEXT,
            group_id INTEGER,
            is_canonical INTEGER DEFAULT 0,
            FOREIGN KEY (group_id) REFERENCES synonym_groups(group_id),
            PRIMARY KEY (word, group_id)
        )
    """)

    # Insert ตามลำดับที่เรียงใหม่
    for old_gid, source, canonical_word in groups_sorted:
        cursor.execute("INSERT INTO synonym_groups (source) VALUES (?)", (source,))
        new_gid = cursor.lastrowid

        for word, is_can in old_group_to_rows[old_gid]:
            cursor.execute(
                "INSERT OR IGNORE INTO word_mappings (word, group_id, is_canonical) VALUES (?, ?, ?)",
                (word, new_gid, is_can)
            )

    # สร้าง INDEX คืน
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_word ON word_mappings(word)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_group_id ON word_mappings(group_id)")

    conn.commit()
    conn.close()
    print(f"เรียงข้อมูลเสร็จสิ้น! ({len(groups_sorted)} กลุ่ม)")


# ───────────────────────────────────────────────
# 2. ตรวจจับคำซ้ำใน word_mappings
# ───────────────────────────────────────────────

def detect_duplicates(db_path="synonyms.db"):
    """
    ตรวจจับ 2 ประเภท:
      A) คำเดียวกันอยู่ใน > 1 กลุ่ม (word ซ้ำข้ามกลุ่ม)
      B) กลุ่มที่มี canonical word เหมือนกัน (กลุ่มซ้ำ)
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("=" * 50)
    print("ตรวจหาคำซ้ำในฐานข้อมูล")
    print("=" * 50)

    # ── A: คำที่ปรากฏใน > 1 กลุ่ม ──
    cursor.execute("""
        SELECT word, COUNT(DISTINCT group_id) AS grp_count,
               GROUP_CONCAT(group_id ORDER BY group_id) AS group_ids
        FROM word_mappings
        GROUP BY LOWER(TRIM(word))
        HAVING COUNT(DISTINCT group_id) > 1
        ORDER BY grp_count DESC, word
    """)
    word_dups = cursor.fetchall()

    print(f"\n[A] คำที่ซ้ำข้ามกลุ่ม: {len(word_dups)} คำ")
    if word_dups:
        for word, count, gids in word_dups:
            print(f"  '{word}' → อยู่ใน {count} กลุ่ม (group_id: {gids})")
    else:
        print("  ✓ ไม่พบ")

    # ── B: กลุ่มที่มี canonical word เหมือนกัน ──
    cursor.execute("""
        SELECT word, COUNT(*) AS cnt,
               GROUP_CONCAT(group_id ORDER BY group_id) AS group_ids
        FROM word_mappings
        WHERE is_canonical = 1
        GROUP BY LOWER(TRIM(word))
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC, word
    """)
    canon_dups = cursor.fetchall()

    print(f"\n[B] Canonical word ซ้ำกัน: {len(canon_dups)} คำ")
    if canon_dups:
        for word, count, gids in canon_dups:
            print(f"  '{word}' → เป็น canonical ใน {count} กลุ่ม (group_id: {gids})")
    else:
        print("  ✓ ไม่พบ")

    conn.close()
    print("\n" + "=" * 50)

    return {"word_duplicates": word_dups, "canonical_duplicates": canon_dups}

def remove_duplicates(db_path="synonyms.db", dry_run=True):
    """
    ลบ word ที่ซ้ำข้ามกลุ่ม โดยเก็บไว้แค่ใน group_id ที่น้อยที่สุด
    dry_run=True  → แสดงตัวอย่างเท่านั้น ไม่ลบจริง
    dry_run=False → ลบจริง
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT word, GROUP_CONCAT(group_id ORDER BY group_id) AS group_ids
        FROM word_mappings
        GROUP BY LOWER(TRIM(word))
        HAVING COUNT(DISTINCT group_id) > 1
    """)
    dups = cursor.fetchall()

    if not dups:
        print("ไม่พบคำซ้ำ ✓")
        conn.close()
        return

    label = "[DRY RUN] " if dry_run else ""
    print(f"{label}จะลบคำซ้ำ {len(dups)} คำ (เก็บ group_id ต่ำสุดไว้):\n")

    for word, gids_str in dups:
        gids = list(map(int, gids_str.split(",")))
        keep, *remove_gids = gids
        print(f"  '{word}' → เก็บ group {keep}, ลบออกจากกลุ่ม {remove_gids}")
        if not dry_run:
            for gid in remove_gids:
                cursor.execute(
                    "DELETE FROM word_mappings WHERE LOWER(TRIM(word)) = LOWER(TRIM(?)) AND group_id = ?",
                    (word, gid)
                )
    if dry_run:
        print("\n[DRY RUN] ไม่มีการลบจริง — ใช้ dry_run=False เพื่อลบจริง")
    else:
        conn.commit()
        print("\nลบคำซ้ำเสร็จสิ้น! ✓")

    conn.close()

if __name__ == "__main__":
    create_db()
# เรียก sort และ detect หลัง create เสร็จ
    sort_db("synonyms.db")
    detect_duplicates("synonyms.db")
