#!/usr/bin/env python3
"""Render the Semibold review and rank glyphs by full-box coverage RMSE."""
import argparse,ctypes,json,math,unicodedata
from pathlib import Path
import freetype
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from fontTools.ttLib import TTFont


def raster(face,cp,size):
    face.set_pixel_sizes(0,size)
    face.load_char(cp,freetype.FT_LOAD_RENDER|freetype.FT_LOAD_NO_HINTING|freetype.FT_LOAD_NO_AUTOHINT|freetype.FT_LOAD_NO_BITMAP)
    slot=face.glyph;bm=slot.bitmap
    if bm.rows and bm.width:
        raw=ctypes.string_at(bm._FT_Bitmap.buffer,bm.rows*abs(bm.pitch))
        mask=np.frombuffer(raw,dtype=np.uint8).reshape(bm.rows,abs(bm.pitch))[:,:bm.width]
    else:mask=np.zeros((0,0),dtype=np.uint8)
    return mask,slot.bitmap_left,slot.bitmap_top,slot.advance.x/64


def comparison(a,b,cp,size):
    items=[raster(face,cp,size) for face in [a,b]]
    left=math.floor(min(0,*(v[1] for v in items)));right=math.ceil(max(*(v[3] for v in items),*(v[1]+v[0].shape[1] for v in items)))
    top=math.ceil(max(1923/2048*size,*(v[2] for v in items)));bottom=math.floor(min(-577/2048*size,*(v[2]-v[0].shape[0] for v in items)))
    masks=[]
    for mask,x,y,advance in items:
        canvas=np.zeros((top-bottom,max(1,right-left)),dtype=np.uint8);canvas[top-y:top-y+mask.shape[0],x-left:x-left+mask.shape[1]]=mask;masks.append(canvas)
    delta=(masks[0].astype(float)-masks[1])/255
    return float(np.sqrt(np.mean(delta**2))*100),masks


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--aptos',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    root=Path(__file__).resolve().parent.parent;path=root/'fonts/Intos-Semibold.ttf';args.output.mkdir(parents=True,exist_ok=True)
    a,b=TTFont(path),TTFont(args.aptos);ca,cb=a.getBestCmap(),b.getBestCmap();common=sorted(set(ca)&set(cb))
    mismatches=[cp for cp in common if a['hmtx'][ca[cp]][0]!=b['hmtx'][cb[cp]][0]];assert not mismatches,mismatches
    assert a['OS/2'].usWeightClass==600 and a['head'].unitsPerEm==2048
    for tag,fields in [('hhea',['ascent','descent','lineGap']),('OS/2',['sTypoAscender','sTypoDescender','sTypoLineGap','sxHeight','sCapHeight'])]:
        for field in fields:assert getattr(a[tag],field)==getattr(b[tag],field),(tag,field,getattr(a[tag],field),getattr(b[tag],field))
    faces=[freetype.Face(str(p)) for p in [path,args.aptos]];rows=[]
    for cp in common:
        if unicodedata.category(chr(cp)).startswith('C'):continue
        score,_=comparison(*faces,cp,256);rows.append(dict(character=chr(cp),codepoint=f'U+{cp:04X}',cp=cp,glyph=ca[cp],rmse_256=score))
    ascii_rows=[r for r in rows if 32<=r['cp']<=126]
    # Rank every printable ASCII character at the requested enlarged resolution.
    for r in ascii_rows:r['rmse_1024']=comparison(*faces,r['cp'],1024)[0]
    ascii_rows.sort(key=lambda r:-r['rmse_1024']);rows.sort(key=lambda r:-r['rmse_256'])
    metadata=dict(method='Unhinted grayscale coverage RMSE across the entire shared glyph box, including advances, sidebearings, ascender and descender. No alignment or stretching for comparison.',ascii_resolution=1024,unicode_screening_resolution=256,common_advances_verified=len(common),weight=600)
    (args.output/'results.json').write_text(json.dumps(dict(metadata=metadata,ascii=ascii_rows,all_common=rows),ensure_ascii=False,indent=2))
    fn='/System/Library/Fonts/Supplemental/Arial.ttf';title=ImageFont.truetype(fn,34);label=ImageFont.truetype(fn,23);small=ImageFont.truetype(fn,19)
    def proof(ranked,filename,heading,field):
        sheet=Image.new('RGB',(2000,1800),'white');d=ImageDraw.Draw(sheet);d.text((35,24),heading,font=title,fill='#18232f');d.text((35,74),'Intos / Aptos / overlay · blue = Intos only; pink = Aptos only · shared full-box RMSE',font=small,fill='#536171')
        for index,row in enumerate(ranked[:10]):
            x=35+(index%2)*985;y=125+(index//2)*330;cp=row['cp'];score,masks=comparison(*faces,cp,1024)
            d.text((x,y),f'{index+1}. {row["glyph"]}  {row["codepoint"]}  — {score:.2f}%',font=label,fill='#18232f')
            a1,b1=[m.astype(float)/255 for m in masks];common=np.minimum(a1,b1);onlya=np.maximum(a1-b1,0);onlyb=np.maximum(b1-a1,0);rgb=np.full((*a1.shape,3),255.)
            for cov,color in [(common,(28,39,50)),(onlya,(0,145,205)),(onlyb,(218,55,115))]:rgb-=cov[:,:,None]*(255-np.array(color))
            images=[Image.fromarray(255-m).convert('RGB') for m in masks]+[Image.fromarray(np.uint8(np.clip(rgb,0,255)))]
            for j,im in enumerate(images):
                im.thumbnail((290,270),Image.Resampling.LANCZOS);sheet.paste(im,(x+j*300+(290-im.width)//2,y+37))
            d.line((x,y+320,x+940,y+320),fill='#e0e5e9')
        sheet.save(args.output/filename)
    proof(ascii_rows,'top-10-ascii.png','Intos Semibold — largest ASCII differences from Aptos Semibold','rmse_1024')
    proof([r for r in rows if r['cp']>126],'top-10-non-ascii.png','Intos Semibold — largest non-ASCII differences from Aptos Semibold','rmse_256')
    sheet=Image.new('RGB',(2000,1250),'white');d=ImageDraw.Draw(sheet);d.text((35,25),'Intos Semibold — upright review',font=title,fill='#18232f')
    variants=[('Intos Regular',root/'fonts/Intos-Regular.ttf'),('Intos Semibold',path),('Intos Bold',root/'fonts/Intos-Bold.ttf'),('Aptos Semibold',args.aptos)]
    for col,(caption,fontpath) in enumerate(variants):
        x=35+col*490;d.text((x,90),caption,font=label,fill='#18232f');big=ImageFont.truetype(str(fontpath),230);medium=ImageFont.truetype(str(fontpath),64)
        d.text((x,150),'g M',font=big,fill='#18232f');d.text((x,440),'J l i j , ;',font=medium,fill='#18232f');d.text((x,550),'g ĝ ğ ġ ģ ǵ',font=medium,fill='#18232f');d.text((x,660),'M Ḿ Ṁ Ṃ',font=medium,fill='#18232f')
    d.line((35,800,1965,800),fill='#e0e5e9');d.text((35,840),'Intos Semibold',font=label,fill='#536171')
    body=ImageFont.truetype(str(path),66)
    for i,line in enumerate(['Making good things takes time, care, and imagination.','Regular, Semibold, Bold: a new weight for clear prose.','0123456789 — parentheses (like these); brackets [too].']):d.text((35,900+i*100),line,font=body,fill='#18232f')
    sheet.save(args.output/'semibold-review.png')
    sheet=Image.new('RGB',(2000,1500),'white');d=ImageDraw.Draw(sheet)
    d.text((35,25),'Intos Semibold — Regular transformations replayed',font=title,fill='#18232f')
    for col,(caption,fontpath) in enumerate(variants):
        x=35+col*490;d.text((x,105),caption,font=label,fill='#536171')
        for text,baseline,size in [('Q O',390,230),('a e n x',590,120),('f t p q',800,130),('R % 0',1020,140),('g M',1310,230)]:
            d.line((x,baseline,x+450,baseline),fill='#dfe6eb')
            d.text((x,baseline),text,font=ImageFont.truetype(str(fontpath),size),fill='#18232f',anchor='ls')
    d.text((35,1430),'Shared point sizes and baselines. Aptos advance widths and kerning retained.',font=label,fill='#536171')
    sheet.save(args.output/'semibold-proportions.png')
    print('Verified',len(common),'Aptos advance widths and vertical metrics.');print('ASCII top 10:',[(r['character'],round(r['rmse_1024'],2)) for r in ascii_rows[:10]]);print(args.output/'semibold-review.png')

if __name__=='__main__':main()
