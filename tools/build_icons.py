from pathlib import Path
import sys,xml.etree.ElementTree as E
import cairosvg
from PIL import Image
r=Path(__file__).resolve().parents[1]
source=r/'assets/AutoCrop_Reference.svg'
E.register_namespace('', 'http://www.w3.org/2000/svg')
svg=E.parse(source).getroot()
ns='{http://www.w3.org/2000/svg}'
groups=svg.findall(ns+'g')
frame=groups[0]
# Reuse the exact frame path coordinates and paint from AutoCrop. The motion
# artwork is confined inside it, so frame rasterization matches at every size.
root=E.Element(ns+'svg',width='1254',height='1254',viewBox='0 0 1254 1254')
E.SubElement(root,ns+'title').text='BKID GIF Maker Icon'
E.SubElement(root,ns+'desc').text='Exact AutoCrop cobalt frame with a moving silver cube, ghost and speed lines.'
root.append(frame)
import copy
for transform,opacity in [('translate(200 260) scale(.50)','0.30'),('translate(230 160) scale(.72)','1')]:
 g=E.SubElement(root,ns+'g',transform=transform,opacity=opacity)
 for part in groups[1:]:g.append(copy.deepcopy(part))
lines=E.SubElement(root,ns+'g',fill='#0645F5')
for x,y,w in [(300,570,175),(285,620,190),(310,670,165)]:
 E.SubElement(lines,ns+'rect',x=str(x),y=str(y),width=str(w),height='24')
asset=r/'assets/BKID_GifMaker_Icon.svg'
asset.write_bytes(E.tostring(root,encoding='utf-8',xml_declaration=True))
for size in (16,24,32,64,1254):
 path=r/'assets'/('BKID_GifMaker.png' if size==1254 else 'icon_%s.png'%size)
 cairosvg.svg2png(url=str(asset),write_to=str(path),output_width=size,output_height=size)
Image.open(r/'assets/BKID_GifMaker.png').save(r/'assets/BKID_GifMaker.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(256,256)])
# Verify the entire top/bottom frame bands against the original vector at each
# toolbar size. Those bands include transparent padding and antialiasing.
frame_svg=E.Element(ns+'svg',width='1254',height='1254',viewBox='0 0 1254 1254')
frame_svg.append(copy.deepcopy(frame))
for size in (16,24,32,64):
 import io
 reference=Image.open(io.BytesIO(cairosvg.svg2png(bytestring=E.tostring(frame_svg),output_width=size,output_height=size))).convert('RGBA')
 actual=Image.open(r/'assets'/('icon_%s.png'%size)).convert('RGBA')
 for y in range(size):
  for x in range(size):
   if reference.getpixel((x,y))[3]:
    assert reference.getpixel((x,y))==actual.getpixel((x,y)),(size,x,y)
 print('Every frame pixel matches AutoCrop:',size)
