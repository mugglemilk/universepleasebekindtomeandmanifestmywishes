import sqlite3
import os
from collections import defaultdict


class SynonymRepository:
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'synonyms.db')
        self._db_path = os.path.abspath(db_path)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)

    def get_synonyms(self, word: str) -> list[str] | None: ##get_synonyms ส่งคำพ้อง (จุดดึงข้อมูลดิบจาก database)

        cur = self._conn.execute(
            '''SELECT DISTINCT wm2.word 
               FROM word_mappings wm1
               JOIN word_mappings wm2 ON wm1.group_id = wm2.group_id 
               WHERE wm1.word = ? AND wm2.word != ?''', 
               ##wm2.word ดึงคำมาโชว์
               ##word_mappings wm1 คำที่พิมพ์มาอยู่กลุ่มไหน
               ##word_mappings wm2 คำอื่น ๆ ที่อยู่ในกลุ่มเดียวกันกับ wm1 มีคำว่าอะไรบ้าง
               ##JOIN เชื่อมเป็นกลุ่มเดียวกัน
               ##WHERE เอาคำที่พิมพ์มาเป็นตัวตั้งต้น ##word ที่ส่งมาอยู่ใน group_id ไหน  
               ##AND ไม่เอาคำตั้งต้นมาเป็นคำไวพจน์
            (word, word)
        )
        rows = cur.fetchall()
        if rows:
            return [row[0] for row in rows]
        exists = self._conn.execute(
            'SELECT 1 FROM word_mappings WHERE word = ? LIMIT 1', (word,)
        ).fetchone()
        return [] if exists else None

    def get_canonical(self, word: str) -> str | None:
        cur = self._conn.execute(
            '''SELECT wm2.word
               FROM word_mappings wm1
               JOIN word_mappings wm2 ON wm1.group_id = wm2.group_id
               WHERE wm1.word = ? AND wm2.is_canonical = 1
               LIMIT 1''',
            (word,)
        )
        row = cur.fetchone()
        return row[0] if row else None

    def get_all(self) -> dict[str, list[str]]:
        cur = self._conn.execute(
            '''SELECT wm1.word, wm2.word
               FROM word_mappings wm1
               JOIN word_mappings wm2 ON wm1.group_id = wm2.group_id AND wm1.word != wm2.word
               WHERE wm1.is_canonical = 1'''
        )
        result: dict[str, list[str]] = defaultdict(list)
        for word, synonym in cur.fetchall():
            result[word].append(synonym)
        return dict(result)

    def entry_count(self) -> int:
        cur = self._conn.execute('SELECT COUNT(DISTINCT word) FROM word_mappings')
        return cur.fetchone()[0]
