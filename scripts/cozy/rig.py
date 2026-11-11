"""RIG helpers - armature creation, skinning and pose utilities.

Rig conventions (docs/STANDARDS.md#rigging):
  * One armature per character: ``RIG_<Char>``; meshes are parented to it and
    deformed through an Armature modifier (FBX/game-engine friendly).
  * Bone names follow Blender's ``.L``/``.R`` suffix rule so pose mirroring works.
  * ``root`` lies flat on the ground pointing +Y and owns the whole hierarchy.
  * Bones have custom widget shapes (``WGT_*`` meshes in a hidden collection).
  * Pose rotations are authored as quaternions.
"""
import math

import bmesh
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

from .utils import collection


# --------------------------------------------------------------------------- #
# Widgets
# --------------------------------------------------------------------------- #
def _widget(name, kind):
    full = "WGT_" + name
    if full in bpy.data.objects:
        return bpy.data.objects[full]
    wgt_col = collection("WGT")
    bm = bmesh.new()
    if kind == 'circle':
        bmesh.ops.create_circle(bm, cap_ends=False, segments=32, radius=1.0)
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'X'))
    elif kind == 'square':
        bmesh.ops.create_circle(bm, cap_ends=False, segments=4, radius=1.0)
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'X'))
    elif kind == 'root':
        bmesh.ops.create_circle(bm, cap_ends=False, segments=48, radius=1.0)
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'X'))
        a = bm.verts.new((0, 1.0, 0))
        b = bm.verts.new((0, 1.35, 0))
        bm.edges.new((a, b))
    elif kind == 'sphere':
        for ax in ('X', 'Y', 'Z'):
            ring = bmesh.ops.create_circle(bm, cap_ends=False, segments=24, radius=1.0)
            if ax != 'Z':
                bmesh.ops.rotate(bm, verts=ring['verts'], cent=(0, 0, 0),
                                 matrix=Matrix.Rotation(math.pi / 2, 3, 'X' if ax == 'Y' else 'Y'))
    me = bpy.data.meshes.new(full)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(full, me)
    wgt_col.objects.link(obj)
    wgt_col.hide_render = True
    wgt_col.hide_viewport = True
    return obj


# --------------------------------------------------------------------------- #
# Armature
# --------------------------------------------------------------------------- #
def create_armature(name, col, bones, location=(0, 0, 0)):
    """bones: list of dicts {name, head, tail, parent?, roll?, deform?, connect?, widget?, wsize?}"""
    arm_data = bpy.data.armatures.new(name)
    arm_data.display_type = 'OCTAHEDRAL'
    arm = bpy.data.objects.new(name, arm_data)
    arm.location = location
    arm.show_in_front = True
    col.objects.link(arm)

    view_layer = bpy.context.view_layer
    for o in view_layer.objects:
        o.select_set(False)
    view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm_data.edit_bones
    for spec in bones:
        b = eb.new(spec['name'])
        b.head = spec['head']
        b.tail = spec['tail']
        b.roll = spec.get('roll', 0.0)
        b.use_deform = spec.get('deform', True)
    for spec in bones:
        if spec.get('parent'):
            b = eb[spec['name']]
            b.parent = eb[spec['parent']]
            b.use_connect = spec.get('connect', False)
    bpy.ops.object.mode_set(mode='OBJECT')

    # widgets + bone colours
    for spec in bones:
        pb = arm.pose.bones[spec['name']]
        pb.rotation_mode = 'QUATERNION'
        kind = spec.get('widget')
        if kind:
            pb.custom_shape = _widget(kind, kind)
            pb.custom_shape_scale_xyz = (spec.get('wsize', 1.0),) * 3
            pb.use_custom_shape_bone_size = False
        n = spec['name']
        palette = 'THEME01' if n.endswith('.R') else 'THEME04' if n.endswith('.L') else 'THEME09'
        arm_data.bones[n].color.palette = palette
    return arm


def skin(obj, arm, weights):
    """Bind ``obj`` to ``arm``. weights: {group_name: [(vert_index, w), ...]}"""
    for g, items in weights.items():
        vg = obj.vertex_groups.get(g) or obj.vertex_groups.new(name=g)
        for i, w in items:
            if w > 1e-4:
                vg.add([i], w, 'REPLACE')
    mod = obj.modifiers.new("Armature", 'ARMATURE')
    mod.object = arm
    # keep armature first in the stack, before bevel/subdivision etc.
    obj.modifiers.move(len(obj.modifiers) - 1, 0)
    obj.parent = arm
    return mod


def rigid_skin(obj, arm, bone):
    return skin(obj, arm, {bone: [(v.index, 1.0) for v in obj.data.vertices]})


# --------------------------------------------------------------------------- #
# Posing
# --------------------------------------------------------------------------- #
def rest_rot(arm, bone):
    return arm.data.bones[bone].matrix_local.to_quaternion()


def rot_world(arm, bone, euler_xyz):
    """Return the local quaternion for a rotation expressed around the
    armature's *rest-space* X/Y/Z axes (intuitive for keyframing via script)."""
    r = rest_rot(arm, bone)
    q = Euler(euler_xyz, 'XYZ').to_quaternion()
    return r.inverted() @ q @ r


def loc_world(arm, bone, vec):
    """Local translation for an offset given in armature rest space."""
    r = rest_rot(arm, bone)
    return r.inverted() @ Vector(vec)


def key_pose(arm, frame, pose, interp=None):
    """pose: {bone: {'rot': (x,y,z), 'loc': (x,y,z), 'scale': (x,y,z)}} in rest space."""
    for bone, ch in pose.items():
        pb = arm.pose.bones[bone]
        if 'rot' in ch:
            pb.rotation_quaternion = rot_world(arm, bone, ch['rot'])
            pb.keyframe_insert('rotation_quaternion', frame=frame, group=bone)
        if 'loc' in ch:
            pb.location = loc_world(arm, bone, ch['loc'])
            pb.keyframe_insert('location', frame=frame, group=bone)
        if 'scale' in ch:
            s = ch['scale']
            pb.scale = s if not isinstance(s, (int, float)) else (s, s, s)
            pb.keyframe_insert('scale', frame=frame, group=bone)


def bone_parent(obj, arm, bone):
    """Parent a non-mesh object (light, empty) to a bone, keeping its world transform."""
    mw = obj.matrix_world.copy()
    b = arm.data.bones[bone]
    obj.parent = arm
    obj.parent_type = 'BONE'
    obj.parent_bone = bone
    tail = arm.matrix_world @ b.matrix_local @ Matrix.Translation((0, b.length, 0))
    obj.matrix_parent_inverse = tail.inverted()
    obj.matrix_basis = mw
    return obj
