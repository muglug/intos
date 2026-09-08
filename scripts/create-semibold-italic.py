#!/usr/bin/env python3
"""Create the Intos Semibold Italic review master.

The Italic and Bold Italic masters are blended at 2/3 (weight 600 between 400 and 700) with the
Italic's node structure kept: every Italic segment becomes one segment of the result, its ends
blended with the arc-length-corresponding points of the Bold Italic and its handle fitted to the
blended curve, so the master has the same small node counts as the italics it comes from (a
straight replay of Inter's semibold through a recovered deformation, as used for the upright,
scattered hundreds of nodes over the italics and extrapolated badly).  Advances, vertical metrics
and kerning come from Aptos SemiBold Italic.  Then, as in the other italics: the i/j dots are centred
on Aptos SemiBold Italic's dots, and the g family is built from the upright Semibold g with the
two-storey italic shear (whole glyph 9.5 deg, upper storey sheared back 2 deg about its centre, ear
keeps the global slant), placed like the Italic/Bold Italic g's relative to Aptos.  Existing masters
are never serialized back; only the new master's blocks are spliced into the native package files.
"""
import argparse,copy,importlib.util,json,math,re,unicodedata
from pathlib import Path
import numpy as np
from glyphsLib import GSFont,GSLayer,GSPath,GSNode,GSAnchor
from glyphsLib.types import Point
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen,DecomposingRecordingPen
from fontTools.pens.cu2quPen import Cu2QuPen
from glyph_source import format_coordinate
from semibold_geometry import CubicContours,descriptor,length_data,sample

ROOT=Path(__file__).resolve().parent.parent
_spec=importlib.util.spec_from_file_location('create_semibold',ROOT/'scripts'/'create-semibold.py')
cs=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(cs)
PathPen,recording,bounds,block_span,top_entries,append_entry=cs.PathPen,cs.recording,cs.bounds,cs.block_span,cs.top_entries,cs.append_entry

MASTER_ID='7E2F5C1A-9B3D-4F6E-8A1C-5D2B7E9F3C41'
UPRIGHT_ID=cs.MASTER_ID              # the Semibold master the g family is sheared from
WEIGHT=2/3
NAME='Semibold Italic'
G_FAMILY=['g','gcircumflex','gbreve','gdotaccent','gcommaaccent','gcaron','gacute','gmacron']
DOTTED=['i','j','ij','ibar','idotbelow','iogonek','itildebelow','jcrosstail','fi','f_j']
GLOBAL,TOP_BACK=9.5,2.0
T12=math.tan(math.radians(12))


# ---- italic g construction (as rework_g.py / gshear.py used for the Italic and Bold Italic g) ----
def bbox(path):
    xs=[n.position.x for n in path.nodes];ys=[n.position.y for n in path.nodes];return min(xs),min(ys),max(xs),max(ys)

def is_accent(b):return b[1]>1000 or b[3]<-380

def signed_area(path):
    pts=[(n.position.x,n.position.y) for n in path.nodes]
    return sum(x0*y1-x1*y0 for (x0,y0),(x1,y1) in zip(pts,pts[1:]+pts[:1]))/2

def storeys(body):
    """(upper counter bbox, top y of the lower storey's interior); an open lower storey links at the baseline."""
    outer=max(body,key=lambda p:abs(signed_area(p)))
    counters=[p for p in body if p is not outer and signed_area(p)*signed_area(outer)<0]
    upper=max(counters,key=lambda p:bbox(p)[1]);lower=[p for p in counters if p is not upper]
    return bbox(upper),(max(bbox(p)[3] for p in lower) if lower else 0)

def copy_path(path,fn=lambda p:p):
    q=GSPath();q.closed=path.closed
    for n in path.nodes:
        m=GSNode();m.type=n.type;m.smooth=n.smooth;x,y=fn((n.position.x,n.position.y));m.position=Point(round(x),round(y));q.nodes.append(m)
    return q

def explicit_oncurves(path):
    """all-off-curve path -> explicit implied on-curve nodes (Glyphs needs them)"""
    if sum(1 for n in path.nodes if n.type!='offcurve')>1:return path
    offs=[n for n in path.nodes if n.type=='offcurve'];q=GSPath();q.closed=True
    for a,b in zip(offs,offs[1:]+offs[:1]):
        o=GSNode();o.type='offcurve';o.position=Point(a.position.x,a.position.y);q.nodes.append(o)
        m=GSNode();m.type='qcurve';m.smooth=True;m.position=Point(round((a.position.x+b.position.x)/2),round((a.position.y+b.position.y)/2));q.nodes.append(m)
    return q

def smoothstep(y,y0,y1):
    if y<=y0:return 0.0
    if y>=y1:return 1.0
    t=(y-y0)/(y1-y0);return t*t*(3-2*t)

def make_g_transform(global_deg,top_back_deg,bottom_back_deg,y_top_centre,y_bottom_centre,link,ear_fade):
    tA=math.tan(math.radians(global_deg));dt=tA-math.tan(math.radians(global_deg-top_back_deg));db=tA-math.tan(math.radians(global_deg-bottom_back_deg))
    def fn(p):
        x,y=p;w=smoothstep(y,*link);top_back=-dt*(y-y_top_centre)*(1.0-smoothstep(y,*ear_fade))
        return (x+y*tA+w*top_back+(1-w)*(-db*(y-y_bottom_centre)),y)
    return fn

def layer_xmin(layer):return min(n.position.x for p in layer.paths for n in p.nodes)

def build_g_family(font,new,aptos,aptos_cmap,italic_refs):
    """Shear the upright Semibold g family; accents come from the Italic/Bold Italic blend already in
    `new`, re-centred over the sheared upper bowl; anchors are the upright's, sheared."""
    up_g=font.glyphs['g'].layers[UPRIGHT_ID];body=[p for p in up_g.paths if not is_accent(bbox(p))]
    ub,lower_top=storeys(body)
    fn=make_g_transform(GLOBAL,TOP_BACK,0.0,y_top_centre=(ub[1]+ub[3])/2,y_bottom_centre=0.0,link=(lower_top+40,ub[1]-10),ear_fade=(ub[3]-50,ub[3]+50))
    # place like the existing italics: Aptos's g xMin plus the blended Intos-minus-Aptos offset
    offsets=[layer_xmin(l)-TTFont(p)['glyf'][TTFont(p).getBestCmap()[0x67]].xMin for l,p in italic_refs]
    target=aptos['glyf'][aptos_cmap[0x67]].xMin+(1-WEIGHT)*offsets[0]+WEIGHT*offsets[1]
    dx=target-min(fn((n.position.x,n.position.y))[0] for p in body for n in p.nodes)
    print(f'italic g: upper counter y {ub[1]:.0f}-{ub[3]:.0f}, lower interior top {lower_top:.0f}, xMin {target:.0f} (Aptos {aptos["glyf"][aptos_cmap[0x67]].xMin}, offsets {[round(o,1) for o in offsets]})')
    for name in G_FAMILY:
        up,cur=font.glyphs[name].layers[UPRIGHT_ID],new[name]
        moved=[explicit_oncurves(copy_path(p,lambda q:(fn(q)[0]+dx,q[1]))) for p in up.paths if not is_accent(bbox(p))]
        accents=[p for p in cur.paths if is_accent(bbox(p))]
        if accents:
            ubx,_=storeys(moved);bowl_cx,bowl_cy=(ubx[0]+ubx[2])/2,(ubx[1]+ubx[3])/2
            for a in accents:
                ab=bbox(a);acc_cy=(ab[1]+ab[3])/2;adx=bowl_cx+(acc_cy-bowl_cy)*T12-(ab[0]+ab[2])/2
                moved.append(copy_path(a,lambda q,adx=adx:(q[0]+adx,q[1])))
        cur.paths=moved;cur.components=[]
        cur.anchors=[GSAnchor(an.name,Point(round(fn((an.position.x,an.position.y))[0]+dx),round(an.position.y))) for an in up.anchors]
        print(f'   {name:13s} paths {len(moved)} width {cur.width} accents {len(accents)}')


# ---- i/j dots centred on Aptos's, as in the Italic and Bold Italic masters ----
def is_dot(b):return b[1]>1050 and b[3]-b[1]<350 and b[2]-b[0]<400

def aptos_dots(aptos,name):
    gs=aptos.getGlyphSet();rp=DecomposingRecordingPen(gs);gs[name].draw(rp);contours=[];cur=[]
    for op,args in rp.value:
        if op=='moveTo':cur=[args[0]]
        elif op=='lineTo':cur.append(args[0])
        elif op=='qCurveTo':cur.extend(a for a in args if a is not None)
        elif op=='closePath':contours.append(cur)
    out=[]
    for c in contours:
        xs=[p[0] for p in c];ys=[p[1] for p in c];b=(min(xs),min(ys),max(xs),max(ys))
        if is_dot(b):out.append(((b[0]+b[2])/2,(b[1]+b[3])/2))
    return out

def align_dots(new,aptos,aptos_cmap,unicodes):
    """Centre every dot on Aptos SemiBold Italic's; glyphs Aptos lacks (or whose Aptos form has no
    dot) get the shift measured on their base letter (i, or j for j-derived glyphs and f_j)."""
    deltas={}
    for name in ['i','j']+[n for n in DOTTED if n not in ('i','j')]:
        layer=new.get(name)
        if layer is None:continue
        cps=[int(u,16) for u in unicodes.get(name,[])]
        an=next((aptos_cmap[c] for c in cps if c in aptos_cmap),None) or (name if name in aptos.getGlyphSet() else None)
        tg=aptos_dots(aptos,an) if an else []
        base='j' if name.startswith('j') or name=='f_j' else 'i';moved=[]
        for p in layer.paths:
            b=bbox(p)
            if not is_dot(b):continue
            cx,cy=(b[0]+b[2])/2,(b[1]+b[3])/2
            if tg:tx,ty=min(tg,key=lambda t:(t[0]-cx)**2+(t[1]-cy)**2);d=(tx-cx,ty-cy)
            elif base in deltas:d=deltas[base]
            else:continue
            for n in p.nodes:n.position=Point(float(format_coordinate(n.position.x+d[0])),float(format_coordinate(n.position.y+d[1])))
            moved.append((round(d[0],1),round(d[1],1)))
        if name in ('i','j') and moved:deltas[name]=moved[0]
        print(f'   dots {name:13s} {"Aptos "+an if tg else "base "+base+" shift"}: moved by {moved}')
# ---- structure-preserving blend of two masters ----
def is_line_segment(seg):
    p0,p1,p2,p3=seg;return np.linalg.norm(p1-(2*p0+p3)/3)<1e-6 and np.linalg.norm(p2-(p0+2*p3)/3)<1e-6

def point_at(contour,data,v):
    ts,tables,bounds,total=data;j=min(len(contour)-1,max(0,int(np.searchsorted(bounds,v,side='right'))-1))
    t=float(np.interp((v-bounds[j])*total,tables[j],ts));return sample(contour[j],[t])[0]

def dense_samples(contour,per_segment=24):
    """Points at equal arc-length steps along a cubic contour with their arc-length fractions in [0, 1)."""
    ts,tables,bounds,total=length_data(contour);N=max(240,per_segment*len(contour));S=np.linspace(0,1,N,endpoint=False);P=[]
    for v in S:
        j=min(len(contour)-1,max(0,int(np.searchsorted(bounds,v,side='right'))-1))
        t=float(np.interp((v-bounds[j])*total,tables[j],ts)) if total else 0.0;P.append(sample(contour[j],[t])[0])
    return np.array(P),S

def joint_angles(c):
    """turning angle (deg) at the start of every segment of a cubic contour"""
    out=[]
    for k,seg in enumerate(c):
        prev=c[k-1];d_in=prev[3]-prev[2]
        if np.linalg.norm(d_in)<1e-6:d_in=prev[3]-prev[0]
        d_out=seg[1]-seg[0]
        if np.linalg.norm(d_out)<1e-6:d_out=seg[3]-seg[0]
        den=np.linalg.norm(d_in)*np.linalg.norm(d_out)
        out.append(math.degrees(math.acos(max(-1,min(1,np.dot(d_in,d_out)/den)))) if den else 0.0)
    return out

def correspond(a,b,corner_deg=25.0):
    """Arc-length position on `b` for every joint of `a`.  Corners of `a` are anchored on `b` (nearest
    point in bbox-normalised coordinates, with `b`'s own corners attracting, walked monotonically with an
    arc-length prior; best of five starts); joints between anchors follow arc length proportionally.
    Robust to differing node structures, and corners do not slide along edges."""
    box_a,_=descriptor(a);box_b,_=descriptor(b);norm=lambda P,box:(P-box[:2])/np.maximum(box[2:]-box[:2],1)
    Pb,Sb=dense_samples(b);Bn=norm(Pb,box_b);N=len(Pb)
    An=norm(np.array([seg[0] for seg in a]),box_a);n=len(a)
    _,_,bounds_a,_=length_data(a);_,_,bounds_b,_=length_data(b)
    ang_a,ang_b=joint_angles(a),joint_angles(b)
    anchors=[k for k in range(n) if ang_a[k]>corner_deg] or [0]
    corners_b=[j for j in range(len(b)) if ang_b[j]>corner_deg]
    m=len(anchors);frac=[(bounds_a[anchors[(i+1)%m]]-bounds_a[anchors[i]])%1.0 or 1.0 for i in range(m)]
    exact={}
    if len(corners_b)==m and ang_a[anchors[0]]>corner_deg:
        # same corner count: corners correspond in order; pick the rotation with the least normalised distance
        Cb=norm(np.array([b[j][0] for j in corners_b]),box_b);Ca=An[anchors]
        costs=[np.linalg.norm(Ca-np.roll(Cb,-r,axis=0),axis=1).sum() for r in range(m)];r=int(np.argmin(costs))
        S_anchor=[bounds_b[corners_b[(r+i)%m]] for i in range(m)];exact={anchors[i]:b[corners_b[(r+i)%m]][0] for i in range(m)}
        for i in range(1,m):
            while S_anchor[i]<=S_anchor[i-1]:S_anchor[i]+=1.0
    else:
        is_corner=np.zeros(N,bool)
        for j in corners_b:
            i=int(round(bounds_b[j]*N))%N;is_corner[[(i-1)%N,i,(i+1)%N]]=True
        D=np.linalg.norm(An[anchors][:,None,:]-Bn[None,:,:],axis=2)
        best=None
        for i0 in np.argsort(D[0])[:5]:
            idx=[int(i0)];cost=D[0,i0]
            for k in range(1,m):
                centre=idx[-1]+frac[k-1]*N;lo=max(idx[-1]+1,int(centre-0.2*N-1));hi=min(idx[0]+N-(m-k),int(centre+0.2*N+1))
                if hi<lo:hi=lo
                cand=np.arange(lo,hi+1);cc=cand[is_corner[cand%N]] if ang_a[anchors[k]]>corner_deg else cand[:0]
                if len(cc) and D[k,cc%N].min()<0.25:cand=cc      # a corner of `a` prefers a corner of `b` when one is near
                i=int(cand[np.argmin(D[k,cand%N])]);idx.append(i);cost+=D[k,i%N]
            if best is None or cost<best[0]:best=(cost,idx)
        S_anchor=[best[1][i]/N for i in range(m)]
        for i in range(m):                        # a corner snapped onto one of b's corners takes it exactly
            for j in corners_b:
                if abs(((bounds_b[j]-S_anchor[i]+0.5)%1.0)-0.5)*N<=1.5:exact[anchors[i]]=b[j][0]
    S=np.zeros(n)
    for i in range(m):
        k0,k1=anchors[i],anchors[(i+1)%m];s0=S_anchor[i];s1=S_anchor[(i+1)%m]+(1.0 if i==m-1 else 0.0)
        if s1<=s0:s1+=1.0
        span=(bounds_a[k1]-bounds_a[k0])%1.0 or 1.0
        k=k0
        while True:
            S[k]=s0+(s1-s0)*(((bounds_a[k]-bounds_a[k0])%1.0)/span if k!=k0 else 0.0)
            k=(k+1)%n
            if k==k1:break
    for k in range(1,n):
        while S[k]<=S[k-1]:S[k]+=1.0
    targets=[exact.get(k,point_on(Pb,Sb,S[k])) for k in range(n)]
    return Pb,Sb,S,targets

def point_on(Pb,Sb,s):
    """point of the dense contour at (cyclic) arc-length fraction s"""
    s=s%1.0;i=int(np.searchsorted(Sb,s,side='right'))-1;j=(i+1)%len(Sb)
    s0=Sb[i];s1=Sb[j] if j else 1.0+Sb[0]
    t=(s-s0)/(s1-s0) if s1>s0 else 0.0;return Pb[i]*(1-t)+Pb[j]*t

def blend_contour(a,b,weight,explicit):
    """One piece per segment of `a`: its ends blended with their counterparts on `b`, quadratic handles
    fitted to the blended curve, straight segments kept straight.  Joints that are implied on-curves in
    the source (not in `explicit`) stay implied: the handles of such a run are fitted jointly under the
    TrueType midpoint constraint.  Returns (start, pieces); a piece is ('line',P1,implied_end) or
    ('q',C,P1,implied_end)."""
    Pb,Sb,S,targets=correspond(a,b);n=len(a)
    ends=[(1-weight)*a[k][0]+weight*targets[k] for k in range(n)]
    implied=[not any(np.linalg.norm(a[k][0]-e)<0.05 for e in explicit) for k in range(n)]   # joint at start of segment k
    ts,tables,bounds,total=length_data(a);segs=[]
    for k,seg in enumerate(a):
        P0,P1=ends[k],ends[(k+1)%n]
        if is_line_segment(seg):segs.append(('line',P0,P1,None,None));continue
        s0,s1=S[k],(S[k+1] if k+1<n else S[0]+1.0)
        u=np.linspace(0,1,13)[1:-1];pa=sample(seg,u);la=np.interp(u,ts,tables[k]);tau=la/tables[k][-1] if tables[k][-1]>0 else u
        pts=np.array([(1-weight)*pa[m]+weight*point_on(Pb,Sb,s0+(s1-s0)*tau[m]) for m in range(len(u))])
        chord=np.r_[0,np.cumsum(np.linalg.norm(np.diff(np.vstack([P0,pts,P1]),axis=0),axis=1))];t=chord[1:-1]/chord[-1] if chord[-1]>0 else u
        segs.append(('q',P0,P1,pts,t))
    controls=[None]*n
    def fit_run(run):                          # run: consecutive 'q' segment indices sharing implied joints
        num=np.zeros(2);den=0.0;e=np.zeros(2);sigma=1.0;es=[];sig=[]
        for j,k in enumerate(run):
            _,P0,P1,pts,t=segs[k];es.append(e.copy());sig.append(sigma)
            beta=2*(1-t)*t;R=pts-((1-t)**2)[:,None]*P0-(t**2)[:,None]*P1
            num+=(beta[:,None]*sigma*(R-beta[:,None]*e)).sum(0);den+=(beta**2).sum()
            e=2*P1-e;sigma=-sigma
        c=num/den if den>0 else (segs[run[0]][1]+segs[run[0]][2])/2
        for j,k in enumerate(run):controls[k]=sig[j]*c+es[j]
    q=[k for k in range(n) if segs[k][0]=='q']
    if q and all(segs[k][0]=='q' and implied[k] for k in range(n)):   # a closed all-implied loop: keep one joint explicit
        implied[0]=False
    done=set()
    for k in q:
        if k in done:continue
        if implied[k] and segs[(k-1)%n][0]=='q':continue            # will be reached from the run start
        run=[k];j=(k+1)%n
        while j not in run and segs[j][0]=='q' and implied[j]:run.append(j);j=(j+1)%n
        fit_run(run);done.update(run)
    pieces=[]
    for k in range(n):
        kind,P0,P1,_,_=segs[k];end_implied=implied[(k+1)%n] and kind=='q' and segs[(k+1)%n][0]=='q'
        pieces.append(('line',P1,False) if kind=='line' else ('q',controls[k],P1,end_implied))
    return ends[0],pieces

def match_contours(a,b):
    """Pairs (contour of a, contour of b or None) by bbox/area as interpolate_outlines does."""
    unused=set(range(len(b)));pairs=[]
    for c in a:
        box,area=descriptor(c);options=[]
        for i in unused:
            ob,oa=descriptor(b[i])
            if area*oa>0:options.append((np.linalg.norm(box-ob)+abs(abs(area)**.5-abs(oa)**.5),i))
        if options:_,i=min(options);unused.remove(i);pairs.append((c,b[i]))
        else:pairs.append((c,None))
    return pairs,[b[i] for i in sorted(unused)]

def path_from_pieces(start,pieces):
    nodes=[]
    for piece in pieces:
        if piece[0]=='line':nodes.append(GSNode(tuple(piece[1]),type='line'))
        else:
            nodes.append(GSNode(tuple(piece[1]),type='offcurve'))
            if not piece[3]:nodes.append(GSNode(tuple(piece[2]),type='qcurve'))
    path=GSPath();path.closed=True;path.nodes=nodes;n=len(nodes)
    for i,node in enumerate(nodes):           # smooth where the tangents agree; then make them exactly collinear
        if node.type=='offcurve':continue
        a=np.array(nodes[i-1].position,float);b=np.array(node.position,float);c=np.array(nodes[(i+1)%n].position,float)
        den=np.linalg.norm(b-a)*np.linalg.norm(c-b)
        if den and np.dot(b-a,c-b)/den>.995:
            node.smooth=True
            if nodes[i-1].type=='offcurve' and nodes[(i+1)%n].type=='offcurve':
                d=(b-a)/np.linalg.norm(b-a)+(c-b)/np.linalg.norm(c-b);d/=np.linalg.norm(d)
                nodes[i-1].position=tuple(b-d*np.linalg.norm(b-a));nodes[(i+1)%n].position=tuple(b+d*np.linalg.norm(c-b))
    return path

def path_samples(paths,per=8):
    """dense points along each GSPath (quadratic, implied on-curves honoured): list of arrays"""
    out=[]
    for path in paths:
        nodes=path.nodes
        pts=[(np.array(nd.position,float),nd.type=='offcurve') for nd in nodes]
        seq=[]
        for i,(P,off) in enumerate(pts):
            prev=pts[i-1]
            if off and prev[1]:seq.append(((prev[0]+P)/2,False))
            seq.append((P,off))
        ons=[i for i,(P,off) in enumerate(seq) if not off]
        if not ons:continue
        m=len(seq);cur=[]
        for a,b in zip(ons,ons[1:]+[ons[0]+m]):
            P0=seq[a%m][0];P1=seq[b%m][0];mids=[seq[i%m][0] for i in range(a+1,b)]
            t=np.linspace(0,1,per,endpoint=False)[:,None]
            cur.append(P0+(P1-P0)*t if not mids else (1-t)**2*P0+2*(1-t)*t*mids[0]+t*t*P1)
        out.append(np.concatenate(cur))
    return out

def dense_contour(c,step=6.0):
    out=[]
    for seg in c:
        L=np.linalg.norm(np.diff(sample(seg,np.linspace(0,1,9)),axis=0),axis=1).sum();out.append(sample(seg,np.linspace(0,1,max(2,int(L/step)+1),endpoint=False)))
    return np.concatenate(out)

def poly_area(P):
    return abs(np.sum(P[:,0]*np.roll(P[:,1],-1)-P[:,1]*np.roll(P[:,0],-1)))/2

def plausible(paths,A,B,weight,tol=300.0):
    """Every point of a genuine blend lies within weight*|A-B| of the first master and (1-weight)*|A-B|
    of the second; reject results with points far from both, or with a bbox / area outside the masters'."""
    parts=path_samples(paths,per=12)
    if not parts:return False
    P=np.concatenate(parts);DA=[dense_contour(c) for c in A];DB=[dense_contour(c) for c in B];da,db=np.concatenate(DA),np.concatenate(DB)
    def mind(Q,R):
        out=np.empty(len(Q))
        for i in range(0,len(Q),256):
            d=np.linalg.norm(Q[i:i+256,None,:]-R[None,:,:],axis=2);out[i:i+256]=d.min(1)
        return out
    if np.minimum(mind(P,da)/weight,mind(P,db)/(1-weight)).max()>tol:return False
    boxes=[np.r_[Q.min(0),Q.max(0)] for Q in (da,db)];lo=np.minimum(*boxes);hi=np.maximum(*boxes);bp=np.r_[P.min(0),P.max(0)]
    if (bp[:2]<lo[:2]-6).any() or (bp[2:]>hi[2:]+6).any():return False
    ar=sum(poly_area(q) for q in parts);aa,ab=sum(poly_area(q) for q in DA),sum(poly_area(q) for q in DB)
    return min(aa,ab)*0.92-100<=ar<=max(aa,ab)*1.08+100

def structured(A,B,explicit,weight):
    paths=[];partial=False
    for ca,cb in match_contours(A,B)[0]:
        if cb is None:
            box,_=descriptor(ca);centre=(box[:2]+box[2:])/2;cb=centre+(ca-centre)*1e-7;partial=True
        start,pieces=blend_contour(ca,cb,weight,explicit)
        path=path_from_pieces(start,pieces)
        if abs(signed_area(path))>=100:paths.append(path)
    return paths,partial

def copy_paths(paths):
    out=[]
    for p in paths:
        q=GSPath();q.closed=p.closed
        for nd in p.nodes:
            m=GSNode(tuple(nd.position),type=nd.type);m.smooth=nd.smooth;q.nodes.append(m)
        out.append(q)
    return out

def explicit_points(layer):
    return [np.array(n.position,float) for p in layer.paths for n in p.nodes if n.type!='offcurve']

def structured_blend(a_layer,b_layer,layers_a,layers_b,weight):
    """GSPaths for the blend of two layers.  First with the first layer's node structure, else with the
    second's, else the arc-length interpolation of semibold_geometry; each candidate must be plausible."""
    pa=CubicContours(layers_a);a_layer.draw(pa);pb=CubicContours(layers_b);b_layer.draw(pb)
    A,B=pa.contours,pb.contours
    if not A and not B:return [],'empty'
    if not A or not B:return [],'one-sided'
    paths,partial=structured(A,B,explicit_points(a_layer),weight)
    if plausible(paths,A,B,weight):return paths,('partial' if partial else 'blend')
    paths,partial=structured(B,A,explicit_points(b_layer),1-weight)
    if plausible(paths,A,B,weight):return paths,'blend-bold-structure'
    try:
        from semibold_geometry import interpolate_outlines,draw_contours
        rec=RecordingPen();draw_contours(interpolate_outlines(A,B,weight),rec);pen=PathPen();rec.replay(Cu2QuPen(pen,max_err=.5,reverse_direction=False))
        if plausible(pen.paths,A,B,weight):return pen.paths,'arc-length'
    except ValueError:pass
    return copy_paths(a_layer.paths),'unblended'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replace-review-master',action='store_true',help='Regenerate only the new, unreviewed Semibold Italic master')
    parser.add_argument('--aptos',type=Path,required=True,help='Aptos SemiBold Italic TTF (Aptos-Italic.ttf and Aptos-Bold-Italic.ttf beside it)')
    args=parser.parse_args();work=ROOT/'build/semibold-italic';work.mkdir(parents=True,exist_ok=True)
    source=ROOT/'Intos.glyphspackage';font=GSFont(str(source))
    if any(m.name==NAME for m in font.masters):
        if not args.replace_review_master:raise ValueError(NAME+' already exists; do not overwrite reviewed edits')
        del font.masters[next(i for i,m in enumerate(font.masters) if m.name==NAME)]
        for i in range(len(font.instances)-1,-1,-1):
            if font.instances[i].name==NAME:del font.instances[i]
    if not any(m.id==UPRIGHT_ID for m in font.masters):raise ValueError('The upright Semibold master is required')
    italic=next(m for m in font.masters if m.name=='Italic');bold=next(m for m in font.masters if m.name=='Bold Italic')
    layers=[{g.name:g.layers[m.id] for g in font.glyphs} for m in [italic,bold]]
    aptos=TTFont(args.aptos);ags=aptos.getGlyphSet();aptos_cmap=aptos.getBestCmap()
    master=copy.deepcopy(italic);master.id=MASTER_ID;master.name=NAME;master.axes=[600,1];master.xHeight=aptos['OS/2'].sxHeight;master.capHeight=aptos['OS/2'].sCapHeight
    master.customParameters['postscriptFullName']='Intos Semibold Italic';master.customParameters['postscriptFontName']='Intos-SemiboldItalic';master.customParameters['weightClass']=600
    font.masters.append(master)
    rows=[];metric_map={};new={}
    for index,g in enumerate(font.glyphs):
        if index%400==0:print('Blending glyph',index,'of',len(font.glyphs),flush=True)
        an=next((aptos_cmap[int(u,16)] for u in g.unicodes if int(u,16) in aptos_cmap),None) or (g.name if g.name in ags else None)
        if an:metric_map.setdefault(an,[]).append(g.name)
        a,b=layers[0][g.name],layers[1][g.name]
        paths,mode=structured_blend(a,b,layers[0],layers[1],WEIGHT)
        if mode=='one-sided':                     # an alternate drawn in one italic only: take it as it is
            src=a if a.paths else b;paths=copy_paths(src.paths)
        if mode in ('unblended','arc-length','blend-bold-structure','partial'):print('   ',g.name,mode,flush=True)
        blended_width=(1-WEIGHT)*a.width+WEIGHT*b.width
        advance=aptos['hmtx'][an][0] if an else round(blended_width)
        shift=(advance-blended_width)/2           # keep the blend's sidebearing balance inside Aptos's advance
        layer=GSLayer();layer.layerId=MASTER_ID;layer.associatedMasterId=MASTER_ID;layer.width=advance;layer.paths=paths
        for path in layer.paths:
            for node in path.nodes:node.position=(float(format_coordinate(node.position[0]+shift)),float(format_coordinate(node.position[1])))
        ba={x.name:x for x in b.anchors}
        for anchor in a.anchors:
            other=ba.get(anchor.name,anchor);pos=tuple((1-WEIGHT)*x+WEIGHT*y for x,y in zip(anchor.position,other.position));layer.anchors.append(GSAnchor(anchor.name,Point(float(format_coordinate(pos[0]+shift)),float(format_coordinate(pos[1])))))
        g.layers[MASTER_ID]=layer;new[g.name]=layer
        rows.append(dict(glyph=g.name,mode=mode,aptos=an,width=layer.width,contours=len(layer.paths),nodes=sum(len(p.nodes) for p in layer.paths),italic_nodes=sum(len(p.nodes) for p in a.paths),bold_italic_nodes=sum(len(p.nodes) for p in b.paths)))
    print('Aligning i/j dots on Aptos SemiBold Italic',flush=True)
    align_dots(new,aptos,aptos_cmap,{g.name:g.unicodes for g in font.glyphs})
    print('Building the italic g family from the upright Semibold g',flush=True)
    italic_refs=[(layers[0]['g'],str(args.aptos.with_name('Aptos-Italic.ttf'))),(layers[1]['g'],str(args.aptos.with_name('Aptos-Bold-Italic.ttf')))]
    build_g_family(font,new,aptos,aptos_cmap,italic_refs)
    # Aptos SemiBold Italic's kerning as explicit glyph pairs (as for the upright Semibold).
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
    template=next(i for i in font.instances if i.name=='Italic')
    instance=copy.deepcopy(template);instance.name=NAME;instance.axes=[600,1];instance.weight=600;instance.isBold=False;instance.isItalic=True;instance.customParameters['postscriptFontName']='Intos-SemiboldItalic';instance.instanceInterpolations={MASTER_ID:1};font.instances.append(instance)
    prepared=work/'prepared.glyphs';font.save(str(prepared))
    generated_info=prepared.read_text()
    generated_glyphs={re.search(r'glyphname = ([^;]+);',entry)[1].strip(chr(34)):entry for entry in top_entries(generated_info,'glyphs')}
    edits={}
    for path in (source/'glyphs').glob('*.glyph'):
        raw=path.read_text();name=re.search(r'glyphname = ([^;]+);',raw)[1].strip(chr(34));entries=top_entries(generated_glyphs[name],'layers');entry=next(e for e in entries if MASTER_ID in e)
        old_entry=next((e for e in top_entries(raw,'layers') if MASTER_ID in e),None)
        edits[path]=raw.replace(old_entry,entry,1) if old_entry else append_entry(raw,'layers',entry)
    original_info=(source/'fontinfo.plist').read_text();info=original_info
    for key in ['fontMaster','instances']:
        entry=next(e for e in top_entries(generated_info,key) if MASTER_ID in e);old_entry=next((e for e in top_entries(info,key) if MASTER_ID in e),None);info=info.replace(old_entry,entry,1) if old_entry else append_entry(info,key,entry)
    ka,kb=block_span(generated_info,'"'+MASTER_ID+'"','{');kerning_entry='"'+MASTER_ID+'" = '+generated_info[ka:kb]+';'
    if '"'+MASTER_ID+'" = {' in info:
        start,end=block_span(info,'"'+MASTER_ID+'"','{');info=info[:start]+generated_info[ka:kb]+info[end:]
    else:
        start,end=block_span(info,'kerningLTR','{');info=info[:end-1]+kerning_entry+'\n'+info[end-1:]
    edits[source/'fontinfo.plist']=info
    for path,new_text in edits.items():
        backup=work/'before'/path.relative_to(source);backup.parent.mkdir(parents=True,exist_ok=True)
        if not backup.exists():backup.write_bytes(path.read_bytes())
        path.write_text(new_text)
    (work/'provenance.json').write_text(json.dumps(dict(weight=600,italic=1,blend=WEIGHT,master=MASTER_ID,aptos=str(args.aptos),kerning_pairs=sum(len(v) for v in kern.values()),glyphs=rows),indent=2))
    import collections;print('Added',NAME+':',len(rows),'glyphs;',dict(collections.Counter(r['mode'] for r in rows)),';',sum(len(v) for v in kern.values()),'kerning pairs.',flush=True)

if __name__=='__main__':main()
