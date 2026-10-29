import re, sys, pathlib, random, json
root = pathlib.Path(sys.argv[1])
fx = root/'apps/web/src/mocks/fixtures.ts'
names = re.findall(r"p\('[^']+', (\"[^\"]+\"|'[^']+'),", fx.read_text())
names = [n[1:-1] for n in names]
firsts = ["Marcus","Dante","Theo","Kendrick","Rashad","Jonah","Malik","Elias","Desmond","Andre","Corey","Isaiah","Tobias","Jalen","Quentin","Darnell","Mateo","Silas","Reggie","Omar","Felix","Damon","Cyrus","Nico","Terrell","Grant","Xavier","Lamar","Emmett","Bryce","Caleb","Rowan","Tariq","Dorian","Julian","Kofi","Anton","Miles","Roman","Wesley"]
lasts = ["Okafor-Reyes","Lindqvist","Abernathy","Vasquez-Hill","Ndiaye","Halloran","Brightwater","Castellano","Mbeki","Thornbury","Delacroix","Ashworth","Kowalczyk","Pemberton","Oyelaran","Strickland","Varga","Holloway","Fairbanks","Quist","Achterberg","Rosales","Whitlock","Danforth","Ivanković","Sorensen","Calloway","Mbappé-Lowe","Garrity","Lockhart","Tremblay","Okonjo","Bellamy","Haddad","Stavros","Kingsley","Moreau","Adeyemi","Petrakis","Wainwright","Dunleavy-Cruz","Marchetti","Obi","Rasmussen","Faulkner","Echeverría","Sato","Brennan","Tavares","Volkov","Langford","Oduya","Ferreira","Bjork","Hargrove","Nakamura","Salcedo","Merriweather","Dragić-Hale","Coleridge","Amari","Ventura","Kessler","Thibodeaux","Mwangi","Lucero","Forsberg","Abara","Delgado","Whitfield"]
rnd = random.Random(7)
pairs=[(f,l) for f in firsts for l in lasts]; rnd.shuffle(pairs)
used_last=set(); mapping={}
for n in names:
    for f,l in pairs:
        if l not in used_last:
            used_last.add(l); mapping[n]=f"{f} {l}"; pairs.remove((f,l)); break
# last-name map for prose ("Jokić doubtful")
lastmap={}
for n,new in mapping.items():
    last=n.split(' ',1)[1] if ' ' in n else n
    lastmap[last]=new.split(' ',1)[1]
extra={"Wemby":mapping.get("Victor Wembanyama","").split(' ')[1] if "Victor Wembanyama" in mapping else "Wemby","Kawhi":mapping.get("Kawhi Leonard","Kawhi").split(' ')[0],"LeBron":mapping.get("LeBron James","LeBron").split(' ')[0],"Shai":mapping.get("Shai Gilgeous-Alexander","Shai").split(' ')[0],"Giannis":mapping.get("Giannis Antetokounmpo","Giannis").split(' ')[0]}
changed=0
for f in list((root/'apps/web/src').rglob('*.ts'))+list((root/'apps/web/src').rglob('*.tsx')):
    if '.test.' in f.name: continue
    t=f.read_text(); o=t
    for n in sorted(mapping,key=len,reverse=True): t=t.replace(n,mapping[n])
    if 'mocks' in str(f):
        for k,v in sorted(lastmap.items(),key=lambda kv:-len(kv[0])):
            if len(k)>=4: t=re.sub(rf"\b{re.escape(k)}\b",v,t)
        for k,v in extra.items(): t=re.sub(rf"\b{re.escape(k)}\b",v,t)
    if t!=o: f.write_text(t); changed+=1
json.dump(mapping,open(sys.argv[2],'w'),ensure_ascii=False,indent=1)
print(len(mapping),"names;",changed,"files changed")
