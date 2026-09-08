"""Recover and replay the Regular outline deformation, without Aptos outline fitting.

Corresponding corners and arc-length samples provide landmarks even when the
two Regular fonts use different quadratic subdivisions. A smooth coordinate
map then carries Inter's native weight changes through that deformation.
"""
import numpy as np
from semibold_geometry import (
 CubicContours, descriptor, section, length_data, sample, draw_contours,
)
from fontTools.misc.bezierTools import splitCubicAtT

def strong_corners(contour,degrees=30):
 result=[]
 for i,s in enumerate(contour):
  a=contour[i-1,3]-contour[i-1,2];b=s[1]-s[0];den=np.linalg.norm(a)*np.linalg.norm(b)
  if den and np.dot(a,b)/den<np.cos(np.deg2rad(degrees)):result.append(i)
 return result

def pairs(a,b,n=96):
 ca,cb=strong_corners(a),strong_corners(b)
 if len(ca)!=len(cb):
  for threshold in [10,20,40,50]:
   ca,cb=strong_corners(a,threshold),strong_corners(b,threshold)
   if len(ca)==len(cb):break
 ba,_=descriptor(a);bb,_=descriptor(b)
 norm=lambda p,box:(p-box[:2])/np.maximum(box[2:]-box[:2],1)
 if ca and len(ca)==len(cb):
  costs=[sum(np.linalg.norm(norm(a[i,0],ba)-norm(b[j,0],bb))**2 for i,j in zip(ca,cb[k:]+cb[:k])) for k in range(len(cb))]
  k=int(np.argmin(costs));cb=cb[k:]+cb[:k]
  sections=[(section(a,i,ca[(k+1)%len(ca)]),section(b,j,cb[(k+1)%len(cb)])) for k,(i,j) in enumerate(zip(ca,cb))]
 else:
  if bool(ca)!=bool(cb) or len(ca)!=len(cb):raise ValueError(f'corner mismatch {len(ca)} {len(cb)}')
  def start(c,box):
   p=norm(c[:,0],box);return int(np.argmin(p[:,0]+.01*abs(p[:,1]-.5)))
  sections=[(np.roll(a,-start(a,ba),axis=0),np.roll(b,-start(b,bb),axis=0))]
 result=[]
 for aa,bb in sections:
  samples=[]
  for c in [aa,bb]:
   ts,tables,ends,total=length_data(c);positions=np.linspace(0,1,max(3,n//len(sections)),endpoint=False);points=[]
   for v in positions:
    j=min(len(c)-1,np.searchsorted(ends,v,side='right')-1);t=np.interp((v-ends[j])*total,tables[j],ts);points.append(sample(c[j],[t])[0])
   samples.append(points)
  result.extend(zip(*samples))
 return result

def kernel(a,b):
 r2=((a[:,None,:]-b[None,:,:])**2).sum(2);return r2*np.log(np.maximum(r2,1e-30))
class Map:
 def __init__(self,a,b):
  self.a=np.asarray(a)/1000;dst=np.asarray(b)/1000;n=len(a);P=np.c_[np.ones(n),self.a];K=kernel(self.a,self.a)
  L=np.block([[K+np.eye(n)*1e-7,P],[P.T,np.zeros((3,3))]])
  self.coef=np.linalg.solve(L,np.r_[dst,np.zeros((3,2))])
 def apply(self,p):
  p=np.asarray(p)/1000;return np.c_[kernel(p,self.a),np.ones(len(p)),p]@self.coef*1000

 def warp(self,contours,pre_x=0,post_x=0):
  result=[]
  def transform(points):return self.apply(points+[pre_x,0])+[post_x,0]
  def warp_segment(s,depth=0):
   mapped=transform(s)
   actual=transform(sample(s,[.25,.5,.75]))
   error=np.max(np.linalg.norm(sample(mapped,[.25,.5,.75])-actual,axis=1))
   if error>.25 and depth<7:
    a,b=splitCubicAtT(*map(tuple,s),.5)
    return warp_segment(np.array(a),depth+1)+warp_segment(np.array(b),depth+1)
   return [mapped]
  for c in contours:
   result.append(np.array([part for s in c for part in warp_segment(s)]))
  # A recovered deformation must not fold the Semibold outline over itself.
  points=np.concatenate([c[:,0] for c in contours])+[pre_x,0]
  fx=(self.apply(points+[.1,0])-self.apply(points-[.1,0]))/.2
  fy=(self.apply(points+[0,.1])-self.apply(points-[0,.1]))/.2
  determinant=fx[:,0]*fy[:,1]-fx[:,1]*fy[:,0]
  if determinant.min()<.1:raise ValueError('Recovered map folds the Semibold outline')
  return result

def recover(source,target):
 """Resolve contour unions only in temporary geometry used for correspondence."""
 try:return mapping(source,target)
 except ValueError:
  from booleanOperations.booleanGlyph import BooleanGlyph
  cleaned=[]
  for contours in [source,target]:
   bg=BooleanGlyph();draw_contours(contours,bg.getPen());p=CubicContours()
   bg.removeOverlap().draw(p);cleaned.append(p.contours)
  return mapping(*cleaned)

def mapping(a,b,density=96):
 if len(a)!=len(b):raise ValueError('contour mismatch')
 unused=set(range(len(b)));ps=[];matched=[]
 for ac in a:
  ba,area=descriptor(ac);choices=[]
  for j in unused:
   bb,ab=descriptor(b[j]);
   if area*ab>0:choices.append((np.linalg.norm(ba*.91-bb),j))
  if not choices:raise ValueError('winding')
  _,j=min(choices);unused.remove(j);ps.extend(pairs(ac,b[j],min(density,max(24,density*4//len(a)))));matched.append((ac,b[j]))
 aa,bb=zip(*ps);mp=Map(aa,bb)
 # Independent, denser samples check reconstruction between training landmarks.
 validation=[p for ac,bc in matched for p in pairs(ac,bc,373)]
 x,y=map(np.array,zip(*validation));errors=np.linalg.norm(mp.apply(x)-y,axis=1)
 mp.error=float(errors.max());mp.rms=float(np.sqrt(np.mean(errors**2)))
 if mp.error>3 and density<288:return mapping(a,b,288)
 if mp.error>8:raise ValueError(f'Regular reconstruction error {mp.error:.2f}')
 return mp
