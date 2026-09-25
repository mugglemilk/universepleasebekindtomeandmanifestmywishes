import csv
import sys
import io

# Ensure UTF-8 I/O on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stdin  = io.TextIOWrapper(sys.stdin.buffer,  encoding='utf-8')

def load_data(path='merged.csv'):
    word_to_syns = {}   # word -> list of synonyms
    syn_to_word = {}    # synonym -> canonical word

    with open(path, encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            if len(row) < 2:
                continue
            word = row[0].strip()
            syns = [s.strip() for s in row[1].split('|') if s.strip()]
            word_to_syns[word] = syns
            for s in syns:
                syn_to_word[s] = word

    return word_to_syns, syn_to_word


def find_synonyms(query, word_to_syns, syn_to_word):
    # Direct match as canonical word
    if query in word_to_syns:
        return query, word_to_syns[query]

    # Query is a synonym — find its canonical word
    if query in syn_to_word:
        canonical = syn_to_word[query]
        syns = [s for s in word_to_syns[canonical] if s != query]
        syns = [canonical] + syns  # include canonical in results
        return query, syns

    return query, []


def main():
    word_to_syns, syn_to_word = load_data()
    print(f"Loaded {len(word_to_syns)} entries.")
    print("Enter a word to look up synonyms (or 'q' to quit).\n")

    while True:
        query = input("คำ: ").strip()
        if query.lower() == 'q':
            break
        if not query:
            continue

        _, syns = find_synonyms(query, word_to_syns, syn_to_word)
        if syns:
            print(f"คำไวพจน์: {' | '.join(syns)}\n")
        else:
            print(f"ไม่พบคำไวพจน์สำหรับ '{query}'\n")


if __name__ == '__main__':
    main()
