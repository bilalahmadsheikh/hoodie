"""
Parametric editable pullover hoodie starter model.
All parts are intentionally independent triangle meshes for Blender editing.
Units: 1 Blender unit = 1 metre.
Run: python build_oatmeal_hoodie.py
Requires: numpy, trimesh, plotly (optional HTML preview).
"""
from __future__ import annotations
import os, json, math, zipfile
from pathlib import Path
import numpy as np
import trimesh
from trimesh.visual.material import PBRMaterial
from trimesh.visual import TextureVisuals

OUT = Path(__file__).resolve().parent
SCALE = 0.50
COLORS = {
    'body': '#C7B6A1',
    'ribbing': '#BCA991',
    'pocket': '#C7B6A1',
    'hood': '#C8B8A4',
    'hood_lining': '#AC9987',
    'stitching': '#A99782',
    'drawstrings': '#E0D2BD',
    'aglets': '#938371',
    'eyelets': '#AA9A84',
}

def hexrgb(s):
    return tuple(int(s.lstrip('#')[i:i+2],16) for i in (0,2,4))

MATERIALS = {}
for label, code in COLORS.items():
    rgb = hexrgb(code)
    MATERIALS[label] = PBRMaterial(name=label.replace('_',' ').title(), baseColorFactor=np.array([*rgb,255],dtype=np.uint8), metallicFactor=0.0 if label not in ('eyelets','aglets') else .28, roughnessFactor=.96 if label not in ('eyelets','aglets') else .65, doubleSided=True)

scene = trimesh.Scene()
meshes = {}

def make_mesh(name, vertices, faces, material, uvs=None):
    vertices = np.array(vertices,dtype=float)*SCALE
    faces = np.array(faces,dtype=np.int64)
    m=trimesh.Trimesh(vertices=vertices, faces=faces, process=False, validate=False)
    if uvs is not None:
        m.visual = TextureVisuals(uv=np.asarray(uvs, dtype=float), material=MATERIALS[material])
    else:
        m.visual = TextureVisuals(material=MATERIALS[material])
    meshes[name] = m
    scene.add_geometry(m, geom_name=name, node_name=name)
    return m

def grid_mesh(name, v, material, wrap_u=False, wrap_v=False, uv=None):
    v=np.asarray(v); a,b,_=v.shape
    faces=[]
    for i in range(a if wrap_u else a-1):
        ii=(i+1)%a
        for j in range(b if wrap_v else b-1):
            jj=(j+1)%b
            p=i*b+j; q=ii*b+j; r=ii*b+jj; s=i*b+jj
            faces.append([p,q,r]); faces.append([p,r,s])
    return make_mesh(name,v.reshape(-1,3),faces,material,uvs=uv.reshape(-1,2) if uv is not None else None)

def superellipse(t, exponent=2.65):
    return np.sign(np.cos(t)) * np.abs(np.cos(t))**(2/exponent), np.sign(np.sin(t))*np.abs(np.sin(t))**(2/exponent)

# main torso front/back surface: separate and UV-ready for future decals and embroidery
Y=np.linspace(.155,1.635,65)
RADII=np.array([
[.11,.595,.309],[.20,.618,.320],[.35,.631,.328],[.58,.640,.343],
[.84,.647,.348],[1.10,.660,.345],[1.30,.647,.335],[1.42,.615,.317],
[1.49,.550,.293],[1.55,.428,.246],[1.60,.265,.188],[1.635,.205,.162]])

def shape_at(y):
    return np.interp(y,RADII[:,0],RADII[:,1]),np.interp(y,RADII[:,0],RADII[:,2])

def body_coord(x,y,offset=0):
    rx,rz=shape_at(y)
    q=min(.999999,abs(x)/rx)
    zz=rz*(1-q**2.65)**(1/2.65)
    # small drape creases at outer upper chest
    zz += .010*np.exp(-((abs(x)-.45)/.11)**2)*np.sin(y*12.0)
    zz += .004*np.sin(8*y+8*x)*np.exp(-((y-.65)/.35)**2)
    return zz+offset

for panel, t0,t1 in [('Front_Panel_Print_Ready',0,np.pi),('Back_Panel_Print_Ready',np.pi,2*np.pi)]:
    T=np.linspace(t0,t1,81)
    v=np.zeros((len(Y),len(T),3)); uv=np.zeros((len(Y),len(T),2))
    for i,y in enumerate(Y):
        rx,rz=shape_at(y)
        for j,t in enumerate(T):
            xx,zz=superellipse(t)
            # subtle fabric surface pleats, mainly near the side seams
            pleat=(.006*np.sin(7*t+4*y)+.003*np.sin(15*t+6*y))*max(0,1-abs(y-.95)/1.0)
            v[i,j]=[rx*xx*(1+pleat),y,rz*zz*(1+pleat)]
            uv[i,j]=[j/(len(T)-1), (y-Y[0])/(Y[-1]-Y[0])]
    grid_mesh(panel,v,'body',uv=uv)

# ribbed waistband tubular mesh
def ribbed_oval_band(name,y0,y1,rx0,rx1,rz0,rz1,material,ridge_count=64):
    angles=np.linspace(0,2*np.pi,193,endpoint=False); heights=np.linspace(y0,y1,15)
    v=np.zeros((len(heights),len(angles),3))
    for i,y in enumerate(heights):
        t=(y-y0)/(y1-y0)
        rx=rx0+(rx1-rx0)*t
        rz=rz0+(rz1-rz0)*t
        for j,a in enumerate(angles):
            xx,zz=superellipse(a)
            rib=.0028*np.cos(ridge_count*a)*(np.sin(np.pi*t)**.3)
            v[i,j]=[(rx+rib)*xx,y,(rz+rib)*zz]
    grid_mesh(name,v,material,wrap_v=True)

ribbed_oval_band('Ribbed_Bottom_Hem',.04,.205,.610,.618,.316,.325,'ribbing')

# sleeve segment profile, separately editable for each arm
SLEEVE_PTS=np.array([[.320,1.295,-.010],[.585,1.405,.002],[.760,1.135,.018],[.855,.900,.032],[.962,.650,.053],[1.075,.383,.078]])
SLEEVE_R=np.array([.105,.249,.231,.210,.193,.176])
SLEEVE_D=np.array([.105,.245,.225,.207,.189,.172])

def catmull(arr,t):
    # locally weighted interpolation with scipy if available; fallback to linear
    from scipy.interpolate import CubicSpline
    u=np.linspace(0,1,len(arr))
    return CubicSpline(u,arr,axis=0,bc_type='natural')(t)

def sleeve_surface(sign,name):
    tvals=np.linspace(0,1,64)
    pts=catmull(SLEEVE_PTS,tvals)
    radii=catmull(SLEEVE_R,tvals)
    depths=catmull(SLEEVE_D,tvals)
    angles=np.linspace(0,2*np.pi,65,endpoint=False)
    v=np.zeros((len(tvals),len(angles),3))
    for i,t in enumerate(tvals):
        der=(pts[min(i+1,len(pts)-1)]-pts[max(i-1,0)])
        der/=np.linalg.norm(der)
        u=np.array([der[1],-der[0],0.]);u/=np.linalg.norm(u)
        for j,a in enumerate(angles):
            wave=.008*np.sin(5*a+18*t)*np.exp(-((t-.70)/.23)**2)+.0035*np.cos(8*a+23*t)
            pos=pts[i]+(radii[i]+wave)*np.cos(a)*u+(depths[i]+.5*wave)*np.sin(a)*np.array([0,0,1])
            pos[0]*=sign
            v[i,j]=pos
    grid_mesh(name,v,'body',wrap_v=True)
    return pts,radii,depths

for sign,side in [(1,'Right'),(-1,'Left')]:
    sleeve_surface(sign,f'{side}_Sleeve')

# cuff separate rib-knit, oriented along the sloping arm axis
for sign,side in [(1,'Right'),(-1,'Left')]:
    p0=np.array([1.071,.392,.076]);p1=np.array([1.135,.245,.100]);d=p1-p0;d/=np.linalg.norm(d)
    u=np.array([d[1],-d[0],0]);u/=np.linalg.norm(u)
    ang=np.linspace(0,2*np.pi,97,endpoint=False)
    h=np.linspace(0,1,19)
    v=np.zeros((len(h),len(ang),3))
    for i,t in enumerate(h):
        p=(1-t)*p0+t*p1
        for j,a in enumerate(ang):
            rib=.0025*np.cos(44*a)*np.sin(np.pi*t)**.2
            rup=.174-.012*t+rib
            rz=.169-.009*t+rib
            pp=p+rup*np.cos(a)*u+rz*np.sin(a)*np.array([0,0,1])
            pp[0]*=sign
            v[i,j]=pp
    grid_mesh(f'{side}_Ribbed_Cuff',v,'ribbing',wrap_v=True)

# hood: exterior and independent dark interior, preserving usable front opening
W=np.linspace(0,1,49)
T=np.linspace(0,2*np.pi,101,endpoint=False)
H_CTRL=np.array([
    [0.00,.306,.358,2.015,.370],
    [.10,.365,.403,2.004,.299],
    [.25,.412,.435,1.994,.175],
    [.48,.432,.450,1.982,-.025],
    [.66,.421,.432,1.972,-.188],
    [.83,.330,.355,1.963,-.333],
    [.95,.155,.183,1.963,-.426],
    [1.00,.009,.013,1.962,-.460]])
# interp for clean monotonic rear contour
v=np.zeros((len(W),len(T),3))
for i,w in enumerate(W):
    rx,ry,cy,zz=[np.interp(w,H_CTRL[:,0],H_CTRL[:,j]) for j in (1,2,3,4)]
    for j,a in enumerate(T):
        # hoodie puffy slightly asymmetrical weave / drape
        xx=rx*np.cos(a)*(1+.013*np.sin(6*a+8*w))
        yy=cy+ry*np.sin(a)
        yshift=.014*np.cos(2*a)*w*(1-w)
        v[i,j]=[xx,yy+yshift,zz+.018*np.cos(a)**2*np.sin(np.pi*w)]
grid_mesh('Hood_Outer_Shell',v,'hood',wrap_v=True)
# Close the tiny rear apex opening so the model does not have a pinhole.
make_mesh('Hood_Back_Apex_Cap',np.vstack([v[-1],np.array([[0.,1.962,-.461]])]),[[j,(j+1)%len(T),len(T)] for j in range(len(T))],'hood')

# lining under front opening, inset 12–35mm, shows contrast and interior depth
N=15
v=np.zeros((N,len(T),3))
for i,h in enumerate(np.linspace(0,1,N)):
    for j,a in enumerate(T):
        v[i,j]=[(.303+.055*h)*np.cos(a),2.015+(.348+.045*h)*np.sin(a),.364-.230*h]
grid_mesh('Hood_Inner_Lining',v,'hood_lining',wrap_v=True)

# Utility for smooth tube/cylindrical stitching and drawstrings.
def curve_tube(name,pts, radius,material,sides=9):
    pts=np.asarray(pts,dtype=float)
    if pts.shape[0]<2:return
    # remove tiny duplicates
    pts=pts[np.r_[True, np.linalg.norm(np.diff(pts,axis=0),axis=1)>.000001]]
    v=[]
    for i,p in enumerate(pts):
        tangent=pts[min(i+1,len(pts)-1)]-pts[max(i-1,0)]
        tangent/=np.linalg.norm(tangent)
        ref=np.array([0.,0.,1.]) if abs(tangent[2])<.88 else np.array([0.,1.,0.])
        u=np.cross(tangent,ref);u/=np.linalg.norm(u)
        w=np.cross(tangent,u)
        for j,a in enumerate(np.linspace(0,2*np.pi,sides,endpoint=False)):
            v.append(p+radius*(u*np.cos(a)+w*np.sin(a)))
    f=[]
    for i in range(len(pts)-1):
        for j in range(sides):
            k=(j+1)%sides
            f.extend([[i*sides+j,(i+1)*sides+j,(i+1)*sides+k],
                      [i*sides+j,(i+1)*sides+k,i*sides+k]])
    # cap both ends
    for j in range(1,sides-1):
        f.append([0,j+1,j]); last=(len(pts)-1)*sides
        f.append([last,last+j,last+j+1])
    return make_mesh(name,v,f,material)

# pronounced thickness around the hood opening and face seam
front_rim=np.array([[.307*np.cos(a),2.015+.359*np.sin(a),.376] for a in np.linspace(0,2*np.pi,99)])
curve_tube('Hood_Front_Rim_Piping',front_rim,.017,'hood',sides=12)

# hood center back decorative sewn seam (slight pinch line)
points=[]
for w in np.linspace(.40,1,42):
    rx,ry,cy,zz=[np.interp(w,H_CTRL[:,0],H_CTRL[:,j]) for j in (1,2,3,4)]
    points.append([.003,cy+ry+.003,zz])
# The crown seam is omitted to keep the opening clean for a blank design base.

# kangaroo pocket — individual front overlay with subtle extra cloth volume
y_levels=np.linspace(.405,.878,37)
xs=np.linspace(-1,1,75)
v=np.zeros((len(y_levels),len(xs),3))
for i,y in enumerate(y_levels):
    width=np.interp(y,[.405,.525,.660,.878],[.415,.441,.385,.311])
    for j,xn in enumerate(xs):
        x=width*xn
        bulge=.011+.019*np.sin(np.pi*(y-.405)/(.878-.405))*(1-xn*xn)
        v[i,j]=[x,y,body_coord(x,y,bulge)]
grid_mesh('Kangaroo_Pocket_Editable',v,'pocket')

# raised edge seams on patch perimeter and pocket entrances
for side in (-1,1):
    edge=[]
    for y in y_levels:
        width=np.interp(y,[.405,.525,.660,.878],[.415,.441,.385,.311])
        x=side*width
        edge.append([x,y,body_coord(x,y,.015)])
    curve_tube(f'Pocket_{"L" if side==-1 else "R"}_Side_Edge_Stitch',edge,.0029,'stitching',6)
    opening=[]
    for p in np.linspace(0,1,35):
        x=side*(.440+( .310-.440)*p)
        y=.524+(.850-.524)*p
        z=body_coord(x,y,.028)+.006
        opening.append([x,y,z])
    curve_tube(f'Pocket_{"L" if side==-1 else "R"}_Opening_Seam',opening,.0054,'stitching',7)

for nm,y,w in [('Pocket_Top_Stitch',.875,.310),('Pocket_Bottom_Stitch',.410,.411)]:
    curve_tube(nm,[[x,y,body_coord(x,y,.025)] for x in np.linspace(-w,w,63)],.0032,'stitching',6)

# front side seams of torso (under sleeve down to hem)
for sign,side in [(1,'Right'),(-1,'Left')]:
    pts=[]
    for y in np.linspace(.22,1.27,60):
        rx,rz=shape_at(y)
        pts.append([sign*(rx+.002),y,.012])
    curve_tube(f'{side}_Body_Side_Stitch',pts,.0024,'stitching',6)

# shoulder construction seams over top of trapezoidal front shoulder for each side
for sign,side in [(1,'Right'),(-1,'Left')]:
    pts=[]
    for u in np.linspace(0,1,32):
        x=sign*(.20+.34*u)
        y=1.625-.150*u
        z=.128+.048*u
        pts.append([x,y,z])
    curve_tube(f'{side}_Shoulder_Seam',pts,.0030,'stitching',6)

# collar ring blends the body neckline with the hood base
collar_t=np.linspace(0,2*np.pi,99)
collar_pts=[[.210*np.cos(t),1.620+.017*np.cos(t),.165*np.sin(t)] for t in collar_t]
curve_tube('Neckline_Collar_Rib',collar_pts,.023,'ribbing',10)

# two hanging drawstrings, each with grommet and tipped aglet
for sign, side in [(-1,'Left'),(1,'Right')]:
    cx=sign*.159
    # grommet ring on front at neck / top chest; in XY plane, Z facing front
    gy=1.552; gz=.294
    eye=np.array([[cx+.023*np.cos(t),gy+.023*np.sin(t),gz] for t in np.linspace(0,2*np.pi,39)])
    curve_tube(f'{side}_Drawstring_Eyelet',eye,.0051,'eyelets',sides=8)
    path=[]
    for u in np.linspace(0,1,65):
        y=1.553-.525*u
        x=cx+sign*(.013*np.sin(np.pi*u)+.010*u)
        z=.330+.028*np.sin(np.pi*u)+.009*u
        path.append([x,y,z])
    curve_tube(f'{side}_Drawstring_Cord',path,.0102,'drawstrings',12)
    tip=[]
    for i in range(9):
        u=i/8
        tip.append([path[-1][0],path[-1][1]-.055*u,path[-1][2]])
    curve_tube(f'{side}_Drawstring_Metal_Tip',tip,.0109,'aglets',12)

# around the cuffs add a sewn hem line to visually separate knit from sleeve
for sign,side in [(1,'Right'),(-1,'Left')]:
    p=np.array([1.073,.390,.078]);d=np.array([.064,-.147,.023]);d/=np.linalg.norm(d)
    ux=np.array([d[1],-d[0],0]);ux/=np.linalg.norm(ux)
    pp=[]
    for a in np.linspace(0,2*np.pi,78):
        xyz=p+.177*np.cos(a)*ux+.172*np.sin(a)*np.array([0,0,1]);xyz[0]*=sign
        pp.append(xyz)
    curve_tube(f'{side}_Cuff_Seam',pp,.003,'stitching',7)

# metadata and export: GLB, OBJ/MTL, and a self-contained HTML 3D viewer
metadata={'model':'Blank Pullover Hoodie — Oatmeal Beige / Warm Taupe',
          'color_hex':COLORS['body'],
          'format':'Separate editable meshes for front/back, sleeves, pocket, hood, cuffs, drawstrings and stitching',
          'units':'metres',
          'editable_in':['Blender','Maya','Cinema 4D','other software supporting glTF/OBJ'],
          'design_note':'Front_Panel_Print_Ready and Back_Panel_Print_Ready are standalone UV-ready meshes for artwork and material editing',
          'mesh_names':list(meshes)}
(OUT/'hoodie_model_info.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')

GLB=OUT/'oatmeal_taupe_hoodie_editable.glb'
scene.export(GLB,file_type='glb')

OBJ=OUT/'oatmeal_taupe_hoodie_editable.obj'
obj_str, assets=trimesh.exchange.obj.export_obj(scene, include_normals=True, include_color=True, include_texture=True, return_texture=True)
OBJ.write_text(obj_str,encoding='utf-8')
for filename,payload in assets.items():
    f=OUT/filename
    if isinstance(payload,str):f.write_text(payload,encoding='utf-8')
    else:f.write_bytes(payload)

# Use Plotly offline 3D (can rotate and zoom), with compressed triangle sample for file performance.
try:
    import plotly.graph_objects as go
    from plotly.offline import plot
    fig=go.Figure()
    # group decorative parts into fewer plot traces is unnecessary when viewing; each section remains selectable
    for name,m in meshes.items():
        color='rgb(%d,%d,%d)'%hexrgb(COLORS[
            ('body' if name.startswith(('Front','Back','Left_Sleeve','Right_Sleeve')) else
            'ribbing' if 'Cuff' in name or 'Hem' in name or 'Collar' in name else
            'pocket' if name=='Kangaroo_Pocket_Editable' else
            'hood' if name in ('Hood_Outer_Shell','Hood_Front_Rim_Piping','Hood_Back_Apex_Cap') else
            'hood_lining' if name=='Hood_Inner_Lining' else
            'drawstrings' if 'Cord' in name else
            'aglets' if 'Metal_Tip' in name else
            'eyelets' if 'Eyelet' in name else 'stitching')])
        v=m.vertices; f=m.faces
        fig.add_trace(go.Mesh3d(
            x=v[:,0],y=v[:,1],z=v[:,2],
            i=f[:,0],j=f[:,1],k=f[:,2],name=name,
            color=color,opacity=1,flatshading=False,
            lighting=dict(ambient=.70,diffuse=.76,specular=.045,roughness=.91,fresnel=.05),
            lightposition=dict(x=-50,y=100,z=200),
            hoverinfo='name',showlegend=False))
    fig.update_layout(
        title=dict(text='Oatmeal / Warm Taupe — Editable Hoodie Preview',x=.5,font=dict(size=19)),
        paper_bgcolor='#F6F3EF',plot_bgcolor='#F6F3EF',
        scene=dict(
            xaxis=dict(visible=False), yaxis=dict(visible=False),zaxis=dict(visible=False),
            bgcolor='#F6F3EF',aspectmode='data',
            camera=dict(eye=dict(x=1.35,y=.62,z=1.6),center=dict(x=0,y=0,z=0),up=dict(x=0,y=1,z=0)),
        ),height=820,margin=dict(l=0,r=0,t=60,b=0),
        annotations=[dict(text='Drag to rotate · Scroll to zoom · Editable model is in the .GLB / .OBJ files',x=.5,y=.02,xref='paper',yref='paper',showarrow=False,font=dict(size=12,color='#6B6055'))])
    fig.write_html(OUT/'hoodie_3d_interactive_preview.html',include_plotlyjs=True,full_html=True)
except Exception as e:
    print('HTML preview skipped:',e)

readme='''OATMEAL BEIGE / WARM TAUPE — BLANK HOODIE 3D DESIGN BASE
==========================================================
PRIMARY 3D MODEL: oatmeal_taupe_hoodie_editable.glb
ALTERNATIVE FORMAT: oatmeal_taupe_hoodie_editable.obj (with .mtl file)
INTERACTIVE PREVIEW: hoodie_3d_interactive_preview.html (open in browser)
MODEL GENERATOR: build_oatmeal_hoodie.py (edit proportions and material colors)

EDIT IN BLENDER:
1. Open Blender.
2. File > Import > glTF 2.0 (.glb/.gltf).
3. Select oatmeal_taupe_hoodie_editable.glb.
4. In the Outliner, choose Front_Panel_Print_Ready for front graphics,
   Back_Panel_Print_Ready for back graphics, or edit other separate parts.
5. Apply your own image textures via the Material Properties / Shader Editor,
   or add text, logos, decals, embroidery or patterns.
6. Save as your own .blend project.

Color: warm oatmeal taupe #C7B6A1. Materials are individual and editable.
Scale: 1 model unit = 1 metre. Pullover hoodie; not rigged or simulation-ready.
This is a clean stylized garment base mesh, not a scanned sewing pattern.
'''
(OUT/'README_HOODIE.txt').write_text(readme,encoding='utf-8')

filenames=['oatmeal_taupe_hoodie_editable.glb','oatmeal_taupe_hoodie_editable.obj','hoodie_3d_interactive_preview.html','build_oatmeal_hoodie.py','hoodie_model_info.json','README_HOODIE.txt']+[p.name for p in OUT.glob('*.mtl')]
with zipfile.ZipFile(OUT/'Oatmeal_Taupe_Hoodie_3D_Editable_Kit.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for name in filenames:
        if (OUT/name).exists():z.write(OUT/name,name)

print('meshes:',len(meshes),'vertices:',sum(len(m.vertices) for m in meshes.values()),'faces:',sum(len(m.faces) for m in meshes.values()))
for name in filenames+['Oatmeal_Taupe_Hoodie_3D_Editable_Kit.zip']:
 p=OUT/name
 if p.exists():print(name,round(p.stat().st_size/1024/1024,2),'MB')
