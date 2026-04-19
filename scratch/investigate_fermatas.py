import music21
from music21.expressions import Fermata

search_results = music21.corpus.search('bach', 'composer')
print(f"Total Bach works: {len(search_results)}")

for sr in search_results[:20]:
    try:
        s = sr.parse()
        f = len(s.recurse().getElementsByClass(Fermata))
        print(f"Work: {sr.sourcePath} -> {f} fermatas")
    except Exception as e:
        print(f"Error parsing {sr}: {e}")
