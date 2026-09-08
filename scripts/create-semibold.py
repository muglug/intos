#!/usr/bin/env python3
"""Create the upright Intos Semibold review master from supplied local fonts.

Install scripts/review-requirements.txt in a Python 3.12+ environment. Existing masters are never serialized back.
The detection report records which outlines came from Inter or were interpolated.
"""
import argparse,copy,json,re,unicodedata
from pathlib import Path
import numpy as np
from glyphsLib import GSFont,GSLayer,GSPath,GSNode,GSAnchor
from glyphsLib.types import Point
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen,DecomposingRecordingPen
from fontTools.pens.cu2quPen import Cu2QuPen
from glyph_source import format_coordinate
from semibold_geometry import CubicContours,interpolate_outlines,draw_contours
from semibold_replay import recover

ROOT=Path(__file__).resolve().parent.parent
MASTER_ID='B9A25D74-1E61-5F33-9694-888CE534227E'
WEIGHT=2/3

class PathPen:
    def __init__(self):self.paths=[]
    def moveTo(self,p):self.nodes=[GSNode(p,type='line')]
    def lineTo(self,p):self.nodes.append(GSNode(p,type='line'))
    def qCurveTo(self,*points):
        for p in points[:-1]:self.nodes.append(GSNode(p,type='offcurve'))
        self.nodes.append(GSNode(points[-1],type='qcurve'))
    def curveTo(self,*points):
        for p in points[:-1]:self.nodes.append(GSNode(p,type='offcurve'))
        self.nodes.append(GSNode(points[-1],type='curve'))
    def closePath(self):
        if tuple(self.nodes[-1].position)==tuple(self.nodes[0].position):
            self.nodes[0].type=self.nodes[-1].type;self.nodes.pop()
        path=GSPath();path.closed=True;path.nodes=self.nodes
        for i,n in enumerate(path.nodes):
            if n.type=='offcurve':continue
            a=np.array(path.nodes[i-1].position);b=np.array(n.position);c=np.array(path.nodes[(i+1)%len(path.nodes)].position)
            den=np.linalg.norm(b-a)*np.linalg.norm(c-b)
            if den and np.dot(b-a,c-b)/den>.999:n.smooth=True
        self.paths.append(path)
    def endPath(self):raise ValueError('Unexpected open path')


def recording(layer,layers):
    p=DecomposingRecordingPen(layers);layer.draw(p);return p


def bounds(rec):
    p=BoundsPen(None);rec.replay(p);return p.bounds


def block_span(text,key,opening='('):
    start=text.index(key+' = '+opening)+len(key+' = ')
    closing=')' if opening=='(' else '}';depth=0;quoted=False;escape=False
    for i in range(start,len(text)):
        c=text[i]
        if escape:escape=False;continue
        if c=='\\' and quoted:escape=True;continue
        if c=='"':quoted=not quoted;continue
        if quoted:continue
        if c==opening:depth+=1
        if c==closing:
            depth-=1
            if depth==0:return start,i+1
    raise ValueError('Unclosed '+key)


def top_entries(text,key):
    start,end=block_span(text,key);body=text[start+1:end-1];entries=[];depth=0;quoted=False
    for i,c in enumerate(body):
        if c=='"' and (i==0 or body[i-1]!='\\'):quoted=not quoted
        if quoted:continue
        if c=='{':
            if depth==0:a=i
            depth+=1
        if c=='}':
            depth-=1
            if depth==0:entries.append(body[a:i+1])
    return entries


def append_entry(text,key,entry):
    a,b=block_span(text,key);body=text[a+1:b-1].rstrip()
    return text[:a+1]+body+',\n'+entry+'\n'+text[b-1:]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replace-review-master',action='store_true',help='Regenerate only the new, unreviewed Semibold master')
    parser.add_argument('--inter',type=Path,required=True)
    parser.add_argument('--inter-regular',type=Path,help='Defaults to Inter-Regular.ttf beside --inter')
    parser.add_argument('--aptos',type=Path,required=True)
    parser.add_argument('--custom-glyphs',type=Path,default=ROOT/'design/semibold-custom-glyphs.json')
    args=parser.parse_args();work=ROOT/'build/semibold';work.mkdir(parents=True,exist_ok=True)
    source=ROOT/'Intos.glyphspackage';font=GSFont(str(source))
    if any(m.name=='Semibold' for m in font.masters):
        if not args.replace_review_master:raise ValueError('Semibold already exists; do not overwrite reviewed edits')
        del font.masters[next(i for i,m in enumerate(font.masters) if m.name=='Semibold')]
        for i in range(len(font.instances)-1,-1,-1):
            if font.instances[i].name=='Semibold':del font.instances[i]
    regular=next(m for m in font.masters if m.name=='Regular');bold=next(m for m in font.masters if m.name=='Bold')
    layers=[{g.name:g.layers[m.id] for g in font.glyphs} for m in [regular,bold]]
    inter=TTFont(args.inter);aptos=TTFont(args.aptos);igs=inter.getGlyphSet();ags=aptos.getGlyphSet()
    inter_cmap=inter.getBestCmap();aptos_cmap=aptos.getBestCmap()
    custom=set(json.loads(args.custom_glyphs.read_text())['glyphs'])
    reference=TTFont(args.inter_regular or args.inter.with_name('Inter-Regular.ttf'))
    rgs=reference.getGlyphSet();rcmap=reference.getBestCmap()
    source_cmap={int(u,16):g.name for g in font.glyphs for u in g.unicodes}
    replay_cache={};replay_notes={}
    def regular_name(g):
        return next((rcmap[int(u,16)] for u in g.unicodes if int(u,16) in rcmap),None) or (g.name if g.name in rgs else None)
    def replay_map(g,seen=()):
        if g.name in replay_cache:return replay_cache[g.name]
        if g.name in seen:raise ValueError('Cyclic base glyph reference')
        rn=regular_name(g)
        if not rn:raise ValueError('No Inter Regular counterpart')
        rp=CubicContours(rgs);rgs[rn].draw(rp)
        target=CubicContours(layers[0]);layers[0][g.name].draw(target)
        try:
            ib=BoundsPen(rgs);rgs[rn].draw(ib);ob=bounds(recording(layers[0][g.name],layers[0]))
            if ib.bounds and ob and abs((ob[1]+ob[3]-(ib.bounds[1]+ib.bounds[3])*regular.capHeight/reference['OS/2'].sCapHeight)/2)>500:
                raise ValueError('Regular source has an outlying vertical placement')
            mp=recover(rp.contours,target.contours);replay_notes[g.name]=dict(reference=g.name,regular_max_error=mp.error)
        except ValueError as error:
            candidates=[]
            for u in g.unicodes:
                char=chr(int(u,16));base=unicodedata.normalize('NFD',char)[0]
                if base!=char and ord(base) in source_cmap:candidates.append(source_cmap[ord(base)])
                label=unicodedata.name(char,'')
                if ' WITH ' in label:
                    try:base=unicodedata.lookup(label.split(' WITH ')[0])
                    except KeyError:continue
                    if ord(base) in source_cmap:candidates.append(source_cmap[ord(base)])
            if '.' in g.name:candidates.append(g.name.split('.')[0])
            for name in candidates:
                if name==g.name or name in seen or font.glyphs[name] is None:continue
                try:mp=replay_map(font.glyphs[name],seen+(g.name,));break
                except ValueError:continue
            else:raise ValueError(str(error))
            replay_notes[g.name]=dict(reference=replay_notes[name]['reference'],fallback_reason=str(error),regular_max_error=mp.error)
        replay_cache[g.name]=mp;return mp
    master=copy.deepcopy(regular);master.id=MASTER_ID;master.name='Semibold';master.axes=[600,0];master.xHeight=aptos['OS/2'].sxHeight;master.capHeight=aptos['OS/2'].sCapHeight
    font.masters.append(master)
    rows=[];metric_map={};records={}
    for index,g in enumerate(font.glyphs):
        if index%400==0:print('Preparing glyph',index,'of',len(font.glyphs),flush=True)
        an=next((aptos_cmap[int(u,16)] for u in g.unicodes if int(u,16) in aptos_cmap),None) or (g.name if g.name in ags else None)
        inn=next((inter_cmap[int(u,16)] for u in g.unicodes if int(u,16) in inter_cmap),None) or (g.name if g.name in igs else None)
        if an:metric_map.setdefault(an,[]).append(g.name)
        a,b=layers[0][g.name],layers[1][g.name];old=[recording(a,layers[0]),recording(b,layers[1])]
        use_custom=g.name in custom or not inn
        replayed=None;replay_failure=None
        if not use_custom:
            sp=CubicContours(igs);igs[inn].draw(sp)
            if sp.contours:
                try:
                    mp=replay_map(g);rn=regular_name(g)
                    advance=aptos['hmtx'][an][0] if an else round((1-WEIGHT)*a.width+WEIGHT*b.width)
                    pre_x=(reference['hmtx'][rn][0]-inter['hmtx'][inn][0])/2
                    post_x=(advance-a.width)/2
                    replayed=mp.warp(sp.contours,pre_x,post_x)
                except ValueError as error:
                    # Different constructions belong to the drawn-outline blend,
                    # rather than inventing a deformation of an unrelated shape.
                    use_custom=True;replay_failure=str(error)
        mode='inter';rec=RecordingPen()
        if use_custom:
            pens=[CubicContours() for _ in range(2)]
            for r,p in zip(old,pens):r.replay(p)
            if not pens[0].contours and not pens[1].contours:mode='empty'
            else:
                try: curves=interpolate_outlines(pens[0].contours,pens[1].contours,WEIGHT)
                except ValueError:
                    from booleanOperations.booleanGlyph import BooleanGlyph
                    cleaned=[]
                    for original in pens:
                        bg=BooleanGlyph();draw_contours(original.contours,bg.getPen());clean=CubicContours();bg.removeOverlap().draw(clean);cleaned.append(clean.contours)
                    try: curves=interpolate_outlines(cleaned[0],cleaned[1],WEIGHT)
                    except ValueError as e: raise ValueError(g.name+': '+str(e)) from e
                    print('Resolved overlap topology for',g.name,flush=True)
                draw_contours(curves,rec);mode='interpolated'
        else:
            if replayed is not None:draw_contours(replayed,rec);mode='inter-replayed'
            else:mode='empty'
        advance=aptos['hmtx'][an][0] if an else round((1-WEIGHT)*a.width+WEIGHT*b.width)
        # Custom drawings already use final Intos coordinates. No outline fitting
        # or scaling after interpolation, including for g and M.
        pen=PathPen();rec.replay(Cu2QuPen(pen,max_err=.08,reverse_direction=False))
        layer=GSLayer();layer.layerId=MASTER_ID;layer.associatedMasterId=MASTER_ID;layer.width=advance;layer.paths=pen.paths
        for path in layer.paths:
            for node in path.nodes:node.position=(float(format_coordinate(node.position.x)),float(format_coordinate(node.position.y)))
        ba={x.name:x for x in b.anchors}
        for anchor in a.anchors:
            other=ba.get(anchor.name,anchor);pos=tuple((1-WEIGHT)*x+WEIGHT*y for x,y in zip(anchor.position,other.position));layer.anchors.append(GSAnchor(anchor.name,Point(*(float(format_coordinate(v)) for v in pos))))
        g.layers[MASTER_ID]=layer
        rows.append(dict(glyph=g.name,mode=mode,inter=inn,aptos=an,width=layer.width,contours=len(layer.paths),replay=replay_notes.get(g.name),interpolation_reason=replay_failure))
    # Expand Aptos's kerning classes to explicit glyph pairs, preserving the
    # existing masters' global Glyphs kerning-group membership.
    kern={};gpos=aptos['GPOS'].table
    indices={i for fr in gpos.FeatureList.FeatureRecord if fr.FeatureTag=='kern' for i in fr.Feature.LookupListIndex}
    for li in sorted(indices):
        lookup=gpos.LookupList.Lookup[li];assert lookup.LookupType==2
        seen=set();pairs={}
        for sub in lookup.SubTable:
            assert sub.ValueFormat1==4 and sub.ValueFormat2==0
            if sub.Format==1:
                for left,ps in zip(sub.Coverage.glyphs,sub.PairSet):
                    for pv in ps.PairValueRecord:pairs[left,pv.SecondGlyph]=pv.Value1.XAdvance;seen.add((left,pv.SecondGlyph))
            else:
                byclass={}
                for right in metric_map:byclass.setdefault(sub.ClassDef2.classDefs.get(right,0),[]).append(right)
                for left in sub.Coverage.glyphs:
                    if left not in metric_map:continue
                    c=sub.ClassDef1.classDefs.get(left,0)
                    for ci,record in enumerate(sub.Class1Record[c].Class2Record):
                        value=record.Value1.XAdvance
                        if not value:continue
                        for right in byclass.get(ci,[]):
                            if (left,right) not in seen:pairs[left,right]=value
        for (left,right),value in pairs.items():
            if not value:continue
            for l in metric_map.get(left,[]):
                for r in metric_map.get(right,[]):kern.setdefault(l,{})[r]=kern.setdefault(l,{}).get(r,0)+value
    font.kerning[MASTER_ID]=kern
    instance=copy.deepcopy(font.instances[0]);instance.name='Semibold';instance.axes=[600,0];instance.weight=600;instance.isBold=False;instance.isItalic=False;instance.customParameters['postscriptFontName']='Intos-Semibold';instance.instanceInterpolations={MASTER_ID:1};font.instances.append(instance)
    prepared=work/'prepared.glyphs';font.save(str(prepared))
    generated_info=prepared.read_text()
    generated_glyphs={re.search(r'glyphname = ([^;]+);',entry)[1].strip(chr(34)):entry for entry in top_entries(generated_info,'glyphs')}
    # Splice only the new layer/master/instance/kerning blocks into native files.
    edits={}
    for path in (source/'glyphs').glob('*.glyph'):
        raw=path.read_text();name=re.search(r'glyphname = ([^;]+);',raw)[1].strip(chr(34));entries=top_entries(generated_glyphs[name],'layers');entry=next(e for e in entries if MASTER_ID in e)
        old_entry=next((e for e in top_entries(raw,'layers') if MASTER_ID in e),None)
        if old_entry and name in custom:
            # A reviewed custom Semibold layer may have been edited in Glyphs.
            # Replaying Inter transformations must not overwrite those drawings.
            continue
        edits[path]=raw.replace(old_entry,entry,1) if old_entry else append_entry(raw,'layers',entry)
    original_info=(source/'fontinfo.plist').read_text();info=original_info
    for key in ['fontMaster','instances']:
        entry=next(e for e in top_entries(generated_info,key) if MASTER_ID in e);old_entry=next((e for e in top_entries(info,key) if MASTER_ID in e),None);info=info.replace(old_entry,entry,1) if old_entry else append_entry(info,key,entry)
    ka,kb=block_span(generated_info,'"'+MASTER_ID+'"','{');kerning_entry='"'+MASTER_ID+'" = '+generated_info[ka:kb]+';'
    if '"'+MASTER_ID+'" = {' in info:
        start,end=block_span(info,'"'+MASTER_ID+'"','{');info=info[:start]+generated_info[ka:kb]+info[end:]
    else:
        start,end=block_span(info,'kerningLTR','{');info=info[:end-1]+kerning_entry+'\n'+info[end-1:]
    if MASTER_ID not in original_info:
        edits[source/'fontinfo.plist']=info
    # Retain original bytes for verification and an explicit rollback.
    for path,new in edits.items():
        backup=work/'before'/path.relative_to(source);backup.parent.mkdir(parents=True,exist_ok=True);
        if not backup.exists():backup.write_bytes(path.read_bytes())
        path.write_text(new)
    (work/'provenance.json').write_text(json.dumps(dict(weight=600,blend=WEIGHT,master=MASTER_ID,inter=str(args.inter),aptos=str(args.aptos),kerning_pairs=sum(len(v) for v in kern.values()),glyphs=rows),indent=2))
    print('Added Semibold:',len(rows),'glyphs;',sum(r['mode']=='interpolated' for r in rows),'interpolated;',sum(len(v) for v in kern.values()),'kerning pairs.',flush=True)

if __name__=='__main__':main()
