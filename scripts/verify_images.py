#!/usr/bin/env python3
"""Check every kuji image; cache only verified actual raster photos in the repository."""
import json,re,os,io,hashlib,urllib.request,urllib.error,collections
from pathlib import Path
from PIL import Image,UnidentifiedImageError

html=Path("index.html")
source=html.read_text(encoding="utf-8")
prizes={}
for m in re.finditer(r"const (\w+Prizes)=(\[[\s\S]*?\]);",source):
    prizes[m.group(1)]=json.loads(m.group(2))
if not prizes: raise SystemExit("No prize data parsed")
out=Path("assets/prizes");out.mkdir(parents=True,exist_ok=True)
report=[];changed=0;broken=[];duplicates=[]
for theme,items in prizes.items():
    seen={}
    for p in items:
        grade=p["g"];url=p.get("url","")
        if not url: continue
        if url in seen: duplicates.append(f"{theme}: {seen[url]} and {grade} same source URL")
        else:seen[url]=grade
        if url.startswith("assets/prizes/"):
            file=Path(url)
            if file.exists():
                try:
                    with Image.open(file) as im:im.verify()
                    report.append((theme,grade,"cached",url));continue
                except Exception: pass
            broken.append((theme,grade,url,"local file missing or invalid"));continue
        if not url.startswith("https://"):
            broken.append((theme,grade,url,"not HTTPS"));continue
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; KujiImageAudit/1.0)","Accept":"image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8"})
            with urllib.request.urlopen(req,timeout=15) as resp:
                data=resp.read(9*1024*1024)
            with Image.open(io.BytesIO(data)) as im:
                im.verify()
            with Image.open(io.BytesIO(data)) as im:
                im=im.convert("RGB")
                if min(im.size)<90:raise ValueError("too small")
                file=out/(theme.removesuffix("Prizes")+"-"+grade.lower()+".jpg")
                im.thumbnail((1000,1000))
                im.save(file,"JPEG",quality=86,optimize=True)
            p["url"]=file.as_posix();changed+=1
            report.append((theme,grade,"downloaded",file.as_posix()))
        except Exception as exc:
            broken.append((theme,grade,url,str(exc)[:160]))
for theme,items in prizes.items():
    pattern=r"(const "+re.escape(theme)+r"=)\[[\s\S]*?\](;)"
    source,n=re.subn(pattern,lambda m:m.group(1)+json.dumps(items,ensure_ascii=False,indent=2)+m.group(2),source,count=1)
    if n!=1:raise RuntimeError(theme)
html.write_text(source,encoding="utf-8")
lines=["# Kuji image audit","",f"Themes: {len(prizes)}. Images cached this run: {changed}. Broken: {len(broken)}. Duplicate URLs: {len(duplicates)}.","","## Unavailable images"]
lines += ["- "+ " / ".join(map(str,r)) for r in broken] or ["None"]
lines += ["","## Duplicate photo sources"]
lines += ["- "+v for v in duplicates] or ["None"]
Path("IMAGE_AUDIT.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
print("\n".join(lines))
