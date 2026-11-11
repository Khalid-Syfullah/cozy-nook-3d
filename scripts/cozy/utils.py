"""Shared helpers: collections, mesh primitives, modifiers and animation keys.

Conventions (see docs/STANDARDS.md):
  * Units are metres, +Z up, -Y is the "front" of every asset.
  * Mesh geometry is built in object space with transforms left clean
    (scale 1, rotation 0) unless an object is deliberately posed in the set.
  * Object origins sit at the logical pivot (usually base-centre).
"""
import math
import random

import bmesh
import bpy
from bpy_extras import anim_utils
from mathutils import Matrix, Vector

TAU = math.tau


# --------------------------------------------------------------------------- #
# Scene / collections
# --------------------------------------------------------------------------- #
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    return scene


def collection(name, parent=None):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(col)
    return col


def link(obj, col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)
    return obj


def empty(name, col, loc=(0, 0, 0), display='PLAIN_AXES', size=0.25):
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = display
    obj.empty_display_size = size
    obj.location = loc
    col.objects.link(obj)
    return obj


def parent(child, par, keep_world=True):
    mw = child.matrix_world.copy()
    child.parent = par
    if keep_world:
        child.matrix_parent_inverse = par.matrix_world.inverted()
        child.matrix_world = mw
    return child


# --------------------------------------------------------------------------- #
# Mesh construction (bmesh based - no operator context needed)
# --------------------------------------------------------------------------- #
def mesh_object(name, bm, col, loc=(0, 0, 0), rot=(0, 0, 0), mat=None, smooth=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        me.shade_smooth()
    obj = bpy.data.objects.new(name, me)
    obj.location = loc
    obj.rotation_euler = rot
    col.objects.link(obj)
    if mat is not None:
        assign(obj, mat)
    return obj


def new_bm():
    bm = bmesh.new()
    bm.loops.layers.uv.new("UVMap")
    return bm


def _offset(bm, origin, half_h):
    """origin='bottom' moves geometry so z=0 is the base."""
    if origin == 'bottom':
        bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, half_h))
    elif origin == 'top':
        bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, -half_h))


def bm_box(size, origin='center', bm=None, offset=(0, 0, 0)):
    bm = bm or new_bm()
    res = bmesh.ops.create_cube(bm, size=1.0, calc_uvs=True)
    verts = res['verts']
    bmesh.ops.scale(bm, verts=verts, vec=size)
    if origin == 'bottom':
        bmesh.ops.translate(bm, verts=verts, vec=(0, 0, size[2] / 2))
    bmesh.ops.translate(bm, verts=verts, vec=offset)
    return bm


def bm_cyl(r1, depth, segs=32, r2=None, origin='bottom', bm=None, offset=(0, 0, 0), cap=True):
    bm = bm or new_bm()
    res = bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=segs,
                                radius1=r1, radius2=r1 if r2 is None else r2,
                                depth=depth, calc_uvs=True)
    verts = res['verts']
    if origin == 'bottom':
        bmesh.ops.translate(bm, verts=verts, vec=(0, 0, depth / 2))
    bmesh.ops.translate(bm, verts=verts, vec=offset)
    return bm


def bm_sphere(r, segs=32, rings=16, bm=None, offset=(0, 0, 0), scale=(1, 1, 1)):
    bm = bm or new_bm()
    res = bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r, calc_uvs=True)
    verts = res['verts']
    bmesh.ops.scale(bm, verts=verts, vec=scale)
    bmesh.ops.translate(bm, verts=verts, vec=offset)
    return bm


def bm_torus(R, r, segs=48, rsegs=16, bm=None, arc=TAU, offset=(0, 0, 0)):
    """Torus lying in XY plane. arc < TAU makes an open segment (for handles)."""
    bm = bm or new_bm()
    closed = arc >= TAU - 1e-6
    n = segs if closed else segs + 1
    rings = []
    for i in range(n):
        a = arc * i / segs
        ring = []
        for j in range(rsegs):
            b = TAU * j / rsegs
            x = (R + r * math.cos(b)) * math.cos(a)
            y = (R + r * math.cos(b)) * math.sin(a)
            z = r * math.sin(b)
            ring.append(bm.verts.new(Vector((x, y, z)) + Vector(offset)))
        rings.append(ring)
    pairs = range(n) if closed else range(n - 1)
    for i in pairs:
        a, b = rings[i], rings[(i + 1) % n]
        for j in range(rsegs):
            bm.faces.new((a[j], b[j], b[(j + 1) % rsegs], a[(j + 1) % rsegs]))
    if not closed:
        for ring in (rings[0], rings[-1]):
            bm.faces.new(ring)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def bm_grid(nx, ny, sx, sy, bm=None):
    bm = bm or new_bm()
    bmesh.ops.create_grid(bm, x_segments=nx, y_segments=ny, size=0.5, calc_uvs=True)
    bmesh.ops.scale(bm, verts=bm.verts, vec=(sx, sy, 1))
    return bm


def box(name, size, col, loc=(0, 0, 0), rot=(0, 0, 0), mat=None, bevel=0.0,
        segs=3, origin='center', subsurf=0):
    obj = mesh_object(name, bm_box(size, origin), col, loc, rot, mat)
    if bevel:
        add_bevel(obj, bevel, segs)
    if subsurf:
        add_subsurf(obj, subsurf)
    return obj


def cyl(name, r, depth, col, loc=(0, 0, 0), rot=(0, 0, 0), mat=None, segs=32,
        r2=None, bevel=0.0, bsegs=3, origin='bottom'):
    obj = mesh_object(name, bm_cyl(r, depth, segs, r2, origin), col, loc, rot, mat)
    if bevel:
        add_bevel(obj, bevel, bsegs)
    return obj


def sphere(name, r, col, loc=(0, 0, 0), rot=(0, 0, 0), mat=None, scale=(1, 1, 1),
           segs=32, rings=16):
    return mesh_object(name, bm_sphere(r, segs, rings, scale=scale), col, loc, rot, mat)


# --------------------------------------------------------------------------- #
# Modifiers / shading
# --------------------------------------------------------------------------- #
def add_bevel(obj, width, segs=3, angle=40, harden=True):
    m = obj.modifiers.new("Bevel", 'BEVEL')
    m.width = width
    m.segments = segs
    m.limit_method = 'ANGLE'
    m.angle_limit = math.radians(angle)
    m.harden_normals = harden
    m.miter_outer = 'MITER_ARC'
    return m


def add_subsurf(obj, levels=2, render=None):
    m = obj.modifiers.new("Subdivision", 'SUBSURF')
    m.levels = levels
    m.render_levels = render if render is not None else levels
    return m


def add_solidify(obj, thickness, offset=-1.0):
    m = obj.modifiers.new("Solidify", 'SOLIDIFY')
    m.thickness = thickness
    m.offset = offset
    return m


def add_weighted_normals(obj):
    m = obj.modifiers.new("WeightedNormal", 'WEIGHTED_NORMAL')
    m.keep_sharp = True
    return m


def assign(obj, *mats):
    obj.data.materials.clear()
    for m in mats:
        obj.data.materials.append(m)
    return obj


def jitter(bm, amount, seed=0):
    rnd = random.Random(seed)
    for v in bm.verts:
        v.co += Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * amount


# --------------------------------------------------------------------------- #
# Curves
# --------------------------------------------------------------------------- #
def curve_from_points(name, pts, col, depth=0.01, mat=None, res=4, kind='POLY'):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = depth
    cu.bevel_resolution = res
    cu.use_fill_caps = True
    sp = cu.splines.new(kind)
    sp.points.add(len(pts) - 1)
    for p, co in zip(sp.points, pts):
        p.co = (*co, 1.0)
    if kind == 'NURBS':
        sp.use_endpoint_u = True
        sp.order_u = 3
    obj = bpy.data.objects.new(name, cu)
    col.objects.link(obj)
    if mat:
        cu.materials.append(mat)
    return obj


# --------------------------------------------------------------------------- #
# Animation helpers (Blender 4.4+/5.x layered actions)
# --------------------------------------------------------------------------- #
def key(target, path, frame, value=None, index=-1, interp=None):
    """Insert a key. `target` may be an Object or PoseBone."""
    if value is not None:
        if index >= 0:
            getattr(target, path)[index] = value
        else:
            setattr(target, path, value)
    target.keyframe_insert(path, index=index, frame=frame)


def fcurves_of(id_data):
    ad = id_data.animation_data
    if not ad or not ad.action:
        return []
    bag = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    return list(bag.fcurves) if bag else []


def set_interpolation(id_data, interp='BEZIER', easing='AUTO', handle='AUTO_CLAMPED'):
    for fc in fcurves_of(id_data):
        for kp in fc.keyframe_points:
            kp.interpolation = interp
            kp.easing = easing
            kp.handle_left_type = handle
            kp.handle_right_type = handle


def add_cycle_modifier(id_data, path_prefix=""):
    for fc in fcurves_of(id_data):
        if fc.data_path.startswith(path_prefix):
            fc.modifiers.new('CYCLES')


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def bm_tube(points, radius, ring=10, bm=None, cap=True, flatten=1.0):
    """Sweep a circle along ``points``. ``radius`` is a float or f(t)->float.
    ``flatten`` < 1 squashes the profile (ribbons, scarf tails). Adds UVs
    (u = around, v = along) so knit/fabric shaders can follow the tube."""
    bm = bm or new_bm()
    uv = bm.loops.layers.uv.active or bm.loops.layers.uv.new("UVMap")
    pts = [Vector(p) for p in points]
    n = len(pts)
    rfun = radius if callable(radius) else (lambda t, r=radius: r)
    tangents = []
    for i in range(n):
        a = pts[max(i - 1, 0)]
        b = pts[min(i + 1, n - 1)]
        tangents.append((b - a).normalized())
    up = Vector((0, 0, 1)) if abs(tangents[0].z) < 0.9 else Vector((1, 0, 0))
    normal = tangents[0].cross(up).normalized()
    rings = []
    for i, (p, t) in enumerate(zip(pts, tangents)):
        normal = (normal - t * normal.dot(t)).normalized()   # parallel transport
        binormal = t.cross(normal).normalized()
        r = rfun(i / (n - 1))
        rings.append([bm.verts.new(p + (normal * math.cos(TAU * j / ring) * flatten
                                        + binormal * math.sin(TAU * j / ring)) * r)
                      for j in range(ring)])
    for i in range(n - 1):
        for j in range(ring):
            j2 = (j + 1) % ring
            f = bm.faces.new((rings[i][j], rings[i][j2], rings[i + 1][j2], rings[i + 1][j]))
            for loop, (u, v) in zip(f.loops, ((j, i), (j + 1, i), (j + 1, i + 1), (j, i + 1))):
                loop[uv].uv = (u / ring, v / (n - 1))
    if cap:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    return bm


def bm_leaf(length, width, curl=0.25, segs=10, bm=None):
    """Lens-shaped leaf along +Y with droop and a centre crease."""
    bm = bm or new_bm()
    rows = []
    for i in range(segs + 1):
        t = i / segs
        w = width * math.sin(math.pi * t) ** 0.8
        y = length * t
        z = -curl * length * t * t
        rows.append([bm.verts.new((-w / 2, y, z + w * 0.15)),
                     bm.verts.new((0, y, z)),
                     bm.verts.new((w / 2, y, z + w * 0.15))])
    for i in range(segs):
        a, b = rows[i], rows[i + 1]
        bm.faces.new((a[0], a[1], b[1], b[0]))
        bm.faces.new((a[1], a[2], b[2], b[1]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    return bm


def append_bm(dst, src, matrix=None, mat_index=0):
    """Merge ``src`` into ``dst`` (optionally transformed). Returns (start, end) vert range."""
    if matrix is not None:
        bmesh.ops.transform(src, matrix=matrix, verts=src.verts)
    for f in src.faces:
        f.material_index = mat_index
    me = bpy.data.meshes.new("_tmp")
    src.to_mesh(me)
    src.free()
    dst.verts.ensure_lookup_table()
    start = len(dst.verts)
    dst.from_mesh(me)
    bpy.data.meshes.remove(me)
    return start, len(dst.verts)
