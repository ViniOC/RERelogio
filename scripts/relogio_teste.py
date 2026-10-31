"""Teste: desenha um painel 240x240 e envia para o relógio como file1.jpg."""
import io
import sys
import urllib.request
import uuid
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

IP = "192.168.1.5"
FONTE = "/usr/share/fonts/julietaula-montserrat-fonts/Montserrat-Bold.otf"
PCT = 63  # valor de demonstração, não é o uso real


def f(tam):
    return ImageFont.truetype(FONTE, tam)


img = Image.new("RGB", (240, 240), (18, 18, 24))
d = ImageDraw.Draw(img)
d.text((120, 22), "TESTE", font=f(14), fill=(255, 170, 60), anchor="mm")
d.text((120, 52), "Claude", font=f(26), fill=(217, 119, 87), anchor="mm")
d.text((120, 105), f"{PCT}%", font=f(52), fill=(240, 240, 240), anchor="mm")
d.rounded_rectangle((20, 145, 220, 165), radius=10, fill=(50, 50, 60))
d.rounded_rectangle((20, 145, 20 + 2 * PCT, 165), radius=10, fill=(217, 119, 87))
d.text((120, 190), "janela de 5h (demo)", font=f(15), fill=(170, 170, 180), anchor="mm")
d.text((120, 218), datetime.now().strftime("%H:%M"), font=f(18), fill=(120, 200, 140), anchor="mm")

buf = io.BytesIO()
img.save(buf, "JPEG", quality=85)
img.save(sys.argv[1] if len(sys.argv) > 1 else "/dev/null", "JPEG", quality=85)

b = uuid.uuid4().hex
corpo = (
    f"--{b}\r\nContent-Disposition: form-data; name=\"imageFile\"; filename=\"file1.jpg\"\r\n"
    f"Content-Type: image/jpeg\r\n\r\n"
).encode() + buf.getvalue() + f"\r\n--{b}--\r\n".encode()
req = urllib.request.Request(f"http://{IP}/upload", data=corpo,
                             headers={"Content-Type": f"multipart/form-data; boundary={b}"})
print("upload:", urllib.request.urlopen(req, timeout=15).status)
for p in ("file1-switch?getstate=1", "themeselect?getstate=2"):
    print(p, urllib.request.urlopen(f"http://{IP}/{p}", timeout=10).status)
