from .repository import SynonymRepository
from api.poem.service import _rhymes, _syllabify #อันนี้เอามาทำ tag แนะนำคำไวพจน์สีเขียวจุดที่ 1

def _is_recommended(source, candidate):#อันนี้เอามาทำ tag แนะนำคำไวพจน์สีเขียวจุดที่ 2
    src_syls = _syllabify(source)
    cand_syls = _syllabify(candidate)
    if not src_syls or not cand_syls:
        return False
    if len(src_syls) != len(cand_syls):
        return False
    return _rhymes(src_syls[-1], cand_syls[-1]) #อันนี้เอามาทำ tag แนะนำคำไวพจน์สีเขียวจุดที่ 2
class SynonymService:
    def __init__(self, repo: SynonymRepository):
        self._repo = repo

    def lookup(self, word: str) -> dict: ##อันนี้คือช่อง search หน้าหลัก
        syns = self._repo.get_synonyms(word)
        if syns is not None:
            ##syns = syns[:5] #อันนี้เพิ่มเข้ามาเพื่อตัดเอาคำศัพท์แค่ 5 คำ
            return {"word": word, "synonyms": syns, "recommended": [s for s in syns if _is_recommended(word, s)]} 
            # return {"word": word, "synonyms": syns} 
        canonical = self._repo.get_canonical(word) ## canonical คำหลัก
    # src_syls = _syllabify(source)
        # canonical = self._repo.get_canonical(word)
        if canonical is not None: ##ถ้าสมมติว่าคำหลักมีคำศัพท์อื่น ๆ มันก็จะแสดงคำพ้องอื่น ๆ มาให้ในบรรทักที่ 26
            all_syns = self._repo.get_synonyms(canonical) ## all_syns ดาต้าที่อยู่ในกลุ่มเดียวกัน
            synonyms = [s for s in all_syns if s != word] ## synonym เรียกคำศัพท์ทีละคำ
            # return {"word": word, "synonyms": [canonical] + synonyms}
            return {"word": word, "synonyms": [canonical] + synonyms, "recommended": [s for s in synonyms if _is_recommended(word, s)]} 
        return {"word": word, "synonyms": [], "recommended": []} #อันนี้เอามาทำ tag แนะนำคำไวพจน์สีเขียวจุดที่ 6
        # return {"word": word, "synonyms": []}
        
        