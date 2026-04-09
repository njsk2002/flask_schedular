import sys, pathlib
hits=[]
for base in sys.path:
    p=pathlib.Path(base)/"pymysql"/"__init__.py"
    if p.exists():
        t=p.read_text(encoding="utf-8", errors="ignore")
        if '"1.4.6"' in t or "'1.4.6'" in t:
            hits.append(str(p))
print("\n".join(hits))
