import re
from pythainlp import word_tokenize
from pythainlp.tokenize import syllable_tokenize as _syl_tok

# ─── consonant / vowel tables (borrowed from setup_python nlp_engine) ─────────

TONE_MARKS = set('่้๊๋')
THAI_CONS = set('กขฃคฅฆงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ')
LEADING_VOWELS = set('เแโไใ')
TRAIL_VOWELS = set('าิีึืุูัะำๅ')

# Final consonant → แม่ตัวสะกด (phoneme class)
FINAL_CLASS = {
    'ก': 'กก', 'ข': 'กก', 'ค': 'กก', 'ฆ': 'กก',
    'ง': 'กง',
    'จ': 'กด', 'ช': 'กด', 'ซ': 'กด', 'ฌ': 'กด',
    'ด': 'กด', 'ต': 'กด', 'ถ': 'กด', 'ท': 'กด', 'ธ': 'กด',
    'ฎ': 'กด', 'ฏ': 'กด', 'ฐ': 'กด', 'ฑ': 'กด', 'ฒ': 'กด',
    'ส': 'กด', 'ศ': 'กด', 'ษ': 'กด',
    'บ': 'กบ', 'ป': 'กบ', 'พ': 'กบ', 'ภ': 'กบ',
    'ฝ': 'กบ', 'ผ': 'กบ', 'ฟ': 'กบ',
    'น': 'กน', 'ณ': 'กน', 'ร': 'กน', 'ล': 'กน', 'ฬ': 'กน', 'ญ': 'กน',
    'ม': 'กม',
    'ย': 'เกย',
    'ว': 'เกอว',
}

# Vowel patterns → vowel name (adapted from setup_python VOWEL_RULES)
_C = r'[ก-ฮ]'
_T = r'[่-๋]?'
VOWEL_RULES: list[tuple[re.Pattern, str]] = [ ###
    (re.compile(rf'แ{_C}{_T}ะ'),            'แอะ'),
    (re.compile(rf'โ{_C}{_T}ะ'),            'โอะ'),
    (re.compile(rf'เ{_C}{_T}ะ'),            'เอะ'),
    (re.compile(rf'เ{_C}{_T}็'),            'เอะ'),
    (re.compile(rf'เ{_C}{{1,2}}{_T}ีย'),   'เอีย'),
    (re.compile(rf'เ{_C}{{1,2}}{_T}ือ'),   'เอือ'),
    (re.compile(rf'เ{_C}{{1,2}}{_T}ืน'),   'เอือ'),
    (re.compile(rf'{_C}{_T}ัว'),            'อัว'),
    (re.compile(rf'เ{_C}{_T}า'),            'เอา'),
    (re.compile(rf'เ{_C}{_T}อ'), 'เออ'),
    (re.compile(rf'เ{_C}{{1,2}}{_T}{_C}{{1,2}}(?:์)?'), 'เอะ'),
    (re.compile(r'ะ'),  'อะ'),
    (re.compile(r'ั'),  'อะ'),   # sara a ย่อ (กัน วัน มัน) — เสียงเดียวกับ ะ ก่อนตัวสะกด
    (re.compile(r'า'),  'อา'),
    (re.compile(r'ิ'),  'อิ'),
    (re.compile(r'ี'),  'อี'),
    (re.compile(r'ึ'),  'อึ'),
    (re.compile(r'ื'),  'อือ'),
    (re.compile(r'ุ'),  'อุ'),
    (re.compile(r'ู'),  'อู'),
    (re.compile(r'เ'),  'เอ'),
    (re.compile(r'แ'),  'แอ'),
    (re.compile(r'โ'),  'โอ'),
    (re.compile(r'ำ'),  'อำ'),
    (re.compile(r'[ไใ]'), 'ไอ'),
    (re.compile(r'็'),  'โอะ'),
]

HALF_NAMES = ['วรรคสดับ', 'วรรครับ', 'วรรครอง', 'วรรคส่ง']

# ─── consonant cluster table (for syllable counting) ─────────────────────────

CLUSTERS = { ###ตัวแปลควบกล้ำ
    ('ก','ร'),('ก','ล'),('ก','ว'),
    ('ข','ร'),('ข','ล'),('ข','ว'),
    ('ค','ร'),('ค','ล'),('ค','ว'),
    ('ป','ร'),('ป','ล'),
    ('ผ','ล'),('พ','ร'),('พ','ล'),('พ','ว'),
    ('ส','ร'),('ต','ร'),
}

# อักษรต่ำ — ตัวที่รับ อักษรนำ ได้ (เสมือน, สมาน, สยาม ฯลฯ)
_LOW_CLASS = set('งคฅฆชซฌญฑณทธนพฟภมยรลวฬ')


# ─── rhyme key ────────────────────────────────────────────────────────────────

def _strip_silent(s: str) -> str:
    """Strip tone marks and thanthakhat-silenced chars (X์ = silent)."""
    chars = [c for c in s if c not in TONE_MARKS]
    out, i = [], 0
    while i < len(chars):
        if i + 1 < len(chars) and chars[i + 1] == '์':
            i += 2
        else:
            out.append(chars[i])
            i += 1
    return ''.join(out)


def _vowel_of(syl: str) -> str:
    """Return vowel name of a syllable using VOWEL_RULES."""
    for pat, name in VOWEL_RULES:
        if pat.search(syl):
            return name
    return 'โอะ'   # implied short-o (CVC with no explicit vowel)


_OPEN_TRAIL = set('าิีึืุูะ็ำๅ')   # trailing vowel marks → open syllable

def _final_class_of(syl: str) -> str:
    """Return แม่ตัวสะกด of a syllable (last Thai consonant, mapped to class).

    Handles ห นำ (e.g. หนา, หมา, หยา) and leading-vowel syllables (เก, ใจ):
    both are open syllables with no final consonant.
    """
    if not syl:
        return ''
    # Trailing vowel mark → open syllable regardless of preceding consonants
    # e.g. หนา (ห นำ + น + า) → า at end → open, key = อา  (not อากน)
    if syl[-1] in _OPEN_TRAIL:
        return ''
    # Find last Thai consonant
    for ch in reversed(syl):
        if ch in THAI_CONS:
            # Leading-vowel syllable with only one consonant → open
            # e.g. เก, แก, ใจ, ไท  (consonant is initial, not final)
            if syl[0] in LEADING_VOWELS and sum(1 for c in syl if c in THAI_CONS) <= 1:
                return ''
            return FINAL_CLASS.get(ch, ch)
    return ''   # open syllable (no final consonant)


def _get_rhyme_key(syl: str) -> str:
    """Rhyme key = vowel_name + final_class.
    e.g. สุด → ('อุ', 'กด') → 'อุกด'
         หนด → implied short-o + กด → 'โอะกด'   (matches ลด ✓)
         มนุษย์ (strip ย์) → นุษ → อุ + กด → 'อุกด'  (matches สุด ✓)
    """
    if not syl:
        return ''
    s = _strip_silent(syl)
    if not s:
        return ''
    vowel = _vowel_of(s)
    final = _final_class_of(s)
    return vowel + final


def _rhymes(a: str, b: str) -> bool:
    if not a or not b:
        return False
    ka, kb = _get_rhyme_key(a), _get_rhyme_key(b)
    return bool(ka) and ka == kb


# ─── syllable tokenizer ───────────────────────────────────────────────────────

def _syllabify(text: str) -> list[str]:##ตัดคำ
    """Tokenize Thai text into syllables using engine='dict'.
    Post-processes to merge single-consonant fragments back into preceding syllable
    (mirrors the logic in setup_python/nlp_engine.py count_syllables_list).
    """
    if not text.strip():
        return []
    try:
        raw = _syl_tok(text, engine='dict') ##ตัดพยางค์ดิบจาก pythaiNLP มาจาก  pythainlp.tokenize.syllable_tokenize มันจะตัดข้อความให้เป็นพยางค์ดิบก่อน (import มาจาก core.py)
        raw = [s for s in raw if s.strip()]
    except Exception:
        words = word_tokenize(text, engine='newmm', keep_whitespace=False)
        return [w for w in words if w.strip()]

    VOWELS = set('ะาิีึืุูเแโใไำ็')
    ALL_FINALS = set(FINAL_CLASS.keys())  # consonants that can be ตัวสะกด

    expanded: list[tuple[str, bool]] = []
    for s in raw:
        # ดักจับคำที่ขึ้นต้นด้วยสระนำหน้าและสั้นความยาว 3 ตัว
        # เช่น 'เจอ', 'เธอ', 'เผลอ', 'เขย', 'แดง', 'โตน' 
        # เพื่อป้องกันไม่ให้คำเหล่านี้ไหลลงไปโดนหั่นแยกพยัญชนะในเงื่อนไขด้านล่าง
        if len(s) == 3 and s[0] in LEADING_VOWELS:
            expanded.append((s, False))
            continue

        # อักษรนำ + leading vowel: เ/แ/โ/ไ/ใ + อักษรนำ + อักษรต่ำ + (มีสระ)
        # เช่น เสมือน → ส + เมือน, เสมอ, เสนาะ
        if (len(s) >= 4 and s[0] in LEADING_VOWELS and s[1] in THAI_CONS
                and s[1] not in ('ห', 'อ') and s[2] in _LOW_CLASS
                and (s[1], s[2]) not in CLUSTERS
                and any(v in s[2:] for v in VOWELS)):
            expanded.append((s[1], True))
            expanded.append((s[0] + s[2:], False))
            
        # Split syllables that begin with leading-vowel + two non-cluster consonants.
        # Guard: skip if len==3 and last char is a valid final consonant —
        # that means it IS a proper single syllable like แสน เกด โจน.
        elif (len(s) >= 3 and s[0] in LEADING_VOWELS and s[1] in THAI_CONS
                and s[1] != 'ห' and s[2] in THAI_CONS
                and (s[1], s[2]) not in CLUSTERS
                and not any(v in s[1:] for v in VOWELS)
                and (len(s) >= 4 or s[-1] not in ALL_FINALS)):
            expanded.append((s[1], True))
            expanded.append((s[0] + s[2:], False))
            
        # Split syllables: consonant + leading-vowel + consonant (อักษรนำ)
        elif (len(s) >= 3 and s[0] in THAI_CONS and s[1] in LEADING_VOWELS
                and s[2] in THAI_CONS and s[1] != 'อ' and s[2] != 'อ'):
            expanded.append((s[0], True))
            expanded.append((s[1:], False))
            
        # Split two-consonant onset that isn't a valid cluster
        elif (len(s) >= 3 and s[0] in THAI_CONS and s[1] in THAI_CONS
              and s[0] not in ('ห', 'อ') and s[1] != 'อ'
              and '์' not in s[0:2] and (s[0], s[1]) not in CLUSTERS):
            expanded.append((s[0], True))
            expanded.append((s[1:], False))
        else:
            expanded.append((s, False))

    # Merge consonant-only fragments into previous syllable
    merged: list[str] = []
    for s, is_split in expanded:
        has_vowel = any(v in s for v in VOWELS)
        cons_only = not has_vowel and sum(1 for c in s if c in THAI_CONS) <= 1
        if cons_only and merged and not is_split:
            merged[-1] = merged[-1] + s
        else:
            merged.append(s)

    return merged ##ลิสต์พยางค์ที่ตัดเสร็จแล้วแสดงออกที่ตัวแปรนี้


# ─── half-line splitter ───────────────────────────────────────────────────────

def _split_halves(line: str) -> tuple[str, str]:
    """Split a line into two วรรค.  User separates halves with 2+ spaces / tab / | / /."""
    m = re.search(r'\s{2,}|\t|[|/]', line) ##แบ่งวรรค
    if m:
        return line[:m.start()].strip(), line[m.end():].strip()
    syls = _syllabify(line)
    for i in range(7, min(10, len(syls))):
        right = syls[i:]
        if len(right) >= 7:
            return ''.join(syls[:i]), ''.join(right)
    return ''.join(syls), ''    
    # mid = len(syls) // 2
    # return ''.join(syls[:mid]), ''.join(syls[mid:])


# ─── rhyme position check ─────────────────────────────────────────────────────

def _check_syl_pos(from_syl: str, to_syls: list[str]) -> tuple[bool, int]:
    """Check if from_syl rhymes with พยางค์ that 3 or 5 (index 2 or 4) of to_syls."""
    for idx in [2, 4]: ##ตัวเมื่อกี้ ir1_ok, ir1_idx ส่งตัวท้ายบทแรกมาเช็คสัมผัสกับวรรคที่ 2 วนตั้งแต่ตำแหน่ง 2-3
        if idx < len(to_syls) and _rhymes(from_syl, to_syls[idx]):
            return True, idx 
    return False, -1 


# ─── main analysis ────────────────────────────────────────────────────────────

def analyze(text: str) -> dict: ###นับจำนวนพยางค์แต่ละวรรค 
    """
    กลอนแปด rules (syllable-level):
      Rule 1 (สัมผัสใน):  H1[-1] → H2[พยางค์ที่ 3 หรือ 5]
      Rule 2 (สัมผัสนอก): H2[-1] ↔ H3[-1]
      Rule 3 (สัมผัสใน):  H3[-1] → H4[พยางค์ที่ 3 หรือ 5]
      Rule 4 (ระหว่างบท): H4[-1] ↔ H2[-1] บทถัดไป
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    stanzas = []
    prev_h4_syl = None

    for si in range(0, len(lines), 2):
        line1 = lines[si] if si < len(lines) else ''
        line2 = lines[si + 1] if si + 1 < len(lines) else ''

        halves_text = [*_split_halves(line1), *_split_halves(line2)] ##แบ่งวรรค
        h_syls = [_syllabify(t) for t in halves_text] ##เก็บวรรค
        last = [s[-1] if s else '' for s in h_syls] ##lastเก็บตัวท้ายของทุกวรรค h_sylsเก็บวรรคทั้งวรรค

        ir1_ok, ir1_idx = _check_syl_pos(last[0], h_syls[1]) ##เช็คสัมผัสแล้วส่งมาเป็นสถานะ คำสุดท้ายของวรรคแรกและวรรคที่สองทั้งวรรค
        nok_ok = _rhymes(last[1], last[2]) ##คำสุดท้ายของวรรคที่ 2 กับคำสุดท้ายของวรรคที 3
        ir3_ok, ir3_idx = _check_syl_pos(last[2], h_syls[3]) ##คำสุดท้ายของวรรคที่ 3 กับคำที่ 3 ของวรรคสุดท้าย
        carry_ok = _rhymes(prev_h4_syl, last[1]) if prev_h4_syl else None ##คำสุดท้ายของวรรคที่ 4 จะไปสัมผัสกับบทถัดไป

        issues = []
        if last[0] and len(h_syls[1]) > 2 and not ir1_ok:
            issues.append({'type': 'err',
                           'message': f'สัมผัสนอก: "{last[0]}" (ท้ายวรรคสดับ) ควรสัมผัสกับพยางค์ที่ 3 หรือ 5 ของวรรครับ'})
        if last[1] and last[2] and not nok_ok:
            issues.append({'type': 'err',
                           'message': f'สัมผัสนอก: "{last[1]}" (ท้ายวรรครับ) ไม่สัมผัสกับ "{last[2]}" (ท้ายวรรครอง)'})
        if last[2] and len(h_syls[3]) > 2 and not ir3_ok:
            issues.append({'type': 'err',
                           'message': f'สัมผัสนอก: "{last[2]}" (ท้ายวรรครอง) ควรสัมผัสกับพยางค์ที่ 3 หรือ 5 ของวรรคส่ง'})
        if carry_ok is False:
            issues.append({'type': 'warn',
                           'message': f'ส่งระหว่างบท: "{prev_h4_syl}" ควรสัมผัสกับ "{last[1]}" (ท้ายวรรครับ)'})
        for i, syls in enumerate(h_syls):
            n = len(syls)
            if n < 7 or n > 9:
                issues.append({'type': 'warn',
                               'message': f'{HALF_NAMES[i]}: {n} พยางค์ (ควร 7–9 พยางค์)'})

        # Pre-compute tooltip texts for r-bad positions
        tip_h1 = (f'ท้ายวรรคสดับ "{last[0]}" ควรสัมผัสกับพยางค์ที่ 3 หรือ 5 ของวรรครับ'
                  if not ir1_ok and last[0] else '')

        tip_h2_parts = []
        if carry_ok is False and prev_h4_syl:
            tip_h2_parts.append(f'ควรสัมผัสกับท้ายวรรคส่งบทก่อน "{prev_h4_syl}"')
        if not nok_ok and last[2]:
            tip_h2_parts.append(f'ควรสัมผัสกับท้ายวรรครอง "{last[2]}"')
        tip_h2 = ' และ'.join(tip_h2_parts) if tip_h2_parts else ''
        if tip_h2:
            tip_h2 = f'ท้ายวรรครับ "{last[1]}" ' + tip_h2

        tip_h3 = (f'ท้ายวรรครอง "{last[2]}" ควรสัมผัสกับท้ายวรรครับ "{last[1]}"'
                  if not nok_ok and last[1] and last[2] else '')

        # If carry_ok is False → mark previous stanza's H4[-1] as bad + tooltip
        if carry_ok is False and stanzas:
            prev_h4_ann = stanzas[-1]['annotations'][3]
            if prev_h4_ann:
                prev_h4_ann[-1]['cls'] = 'r-bad'
                prev_h4_ann[-1]['tip'] = (
                    f'ท้ายวรรคส่ง "{prev_h4_syl}" ควรสัมผัสกับท้ายวรรครับบทถัดไป "{last[1]}"'
                )

        annotations = []
        for hi, syls in enumerate(h_syls):
            ann = []
            for wi, s in enumerate(syls):
                cls = None
                tip = ''
                is_last = (wi == len(syls) - 1)
                if is_last:
                    if hi == 0:
                        cls = 'r-sut' if ir1_ok else 'r-bad'
                        if not ir1_ok:
                            tip = tip_h1
                    elif hi == 1:
                        cls = 'r-nai' if (nok_ok and carry_ok is not False) else 'r-bad'
                        if cls == 'r-bad':
                            tip = tip_h2
                        elif carry_ok is True:
                            cls = 'r-carry-recv'   # รับสัมผัสระหว่างบทจากบทก่อนหน้า
                        else:
                            cls = 'r-nai'
                    elif hi == 2:
                        cls = 'r-nai' if nok_ok else 'r-bad'
                        if not nok_ok:
                            tip = tip_h3
                    else:
                        cls = 'r-son'
                if hi == 1 and ir1_ok and wi == ir1_idx:
                    cls = 'r-ton'
                if hi == 3 and ir3_ok and wi == ir3_idx:
                    cls = 'r-ton'
                ann.append({'word': s, 'cls': cls, 'tip': tip}) 
            annotations.append(ann)

        stanzas.append({
            'index': si // 2,
            'halves': [
                 {'name': HALF_NAMES[i], 'syllables': h_syls[i], 'count': len(h_syls[i])} 
                for i in range(4)
            ],
            'last_syls': last,
            'rhyme_keys': [_get_rhyme_key(s) for s in last],
            'nok_ok': nok_ok,
            'ir1': {'ok': ir1_ok, 'recv_idx': ir1_idx},
            'ir3': {'ok': ir3_ok, 'recv_idx': ir3_idx},
            'carry_ok': carry_ok,
            'issues': issues,
            'annotations': annotations,
        })

        prev_h4_syl = last[3]

    return {'stanzas': stanzas}
