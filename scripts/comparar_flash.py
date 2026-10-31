import sys
a=open(sys.argv[1],'rb').read(); b=open(sys.argv[2],'rb').read()
SEC=4096; dif=[]
for i in range(0,len(a),SEC):
    if a[i:i+SEC]!=b[i:i+SEC]:
        n=sum(x!=y for x,y in zip(a[i:i+SEC],b[i:i+SEC])); dif.append((i,n))
print("setores diferentes:",len(dif),"de",len(a)//SEC)
for i,n in dif: print(hex(i), n, "bytes")
# limites do firmware: ultimo byte nao-FF antes da regiao de dados
def ff(s,i): return s[i:i+SEC]==b'\xff'*SEC
used=[i for i in range(0,len(a),SEC) if not ff(a,i)]
# imprime faixas usadas
r=[];st=used[0];pv=used[0]
for i in used[1:]:
    if i!=pv+SEC: r.append((st,pv+SEC)); st=i
    pv=i
r.append((st,pv+SEC)); print("faixas nao-vazias (backup):",[(hex(x),hex(y)) for x,y in r])
