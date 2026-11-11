"""Export game-engine-ready assets from the master file.

  exports/Pip.glb / Pip.fbx    - skinned mesh + rig + "CocoaDelivery" action
  exports/Tock.glb / Tock.fbx  - rigid-skinned mesh + rig + action
  exports/CozyNook_Env.glb     - static environment (modifiers applied)

Usage:
    blender -b blend/CozyNook_Master.blend -P scripts/export_assets.py
"""
import os

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "exports")


def select_only(objs):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.hide_set(False)
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def export_character(name, rig_name):
    rig = bpy.data.objects[rig_name]
    objs = [rig] + [o for o in rig.children_recursive if o.type in {'MESH'}]
    select_only(objs)
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, f"{name}.glb"), use_selection=True,
                              export_apply=True, export_animations=True, export_skins=True,
                              export_animation_mode='ACTIVE_ACTIONS', export_yup=True,
                              export_nla_strips_merged_animation_name=f"{name}_CocoaDelivery")
    bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, f"{name}.fbx"), use_selection=True,
                             apply_unit_scale=True, add_leaf_bones=False, bake_anim=True,
                             object_types={'ARMATURE', 'MESH'}, armature_nodetype='NULL',
                             mesh_smooth_type='FACE')
    print("[export]", name, len(objs), "objects")


def export_environment():
    env = bpy.data.collections["ENV"]
    objs = [o for o in env.all_objects if o.type == 'MESH' and o.visible_camera]
    select_only(objs)
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "CozyNook_Env.glb"), use_selection=True,
                              export_apply=True, export_animations=False)
    print("[export] env", len(objs), "objects")


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, rig in (("Pip", "RIG_Pip"), ("Tock", "RIG_Tock")):
        ad = bpy.data.objects[rig].animation_data
        if ad and ad.action:
            ad.action.name = f"{name}_CocoaDelivery"
            ad.action.use_fake_user = True
    export_character("Pip", "RIG_Pip")
    export_character("Tock", "RIG_Tock")
    export_environment()


if __name__ == "__main__":
    main()
