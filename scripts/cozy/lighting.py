"""LGT / CAM - lighting rig, cameras and render presets."""
import math

import bpy
from mathutils import Vector

from .materials import hex_lin


def _look_at(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def _light(name, kind, col, loc, energy, color, size=0.1, target=None, **kw):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = hex_lin(color)[:3]
    if kind == 'AREA':
        ld.shape = kw.get('shape', 'RECTANGLE')
        ld.size = size
        ld.size_y = kw.get('size_y', size)
    elif kind == 'SUN':
        ld.angle = math.radians(kw.get('angle', 1.5))
    else:
        ld.shadow_soft_size = size
    obj = bpy.data.objects.new(name, ld)
    obj.location = loc
    col.objects.link(obj)
    if target is not None:
        _look_at(obj, target)
    return obj


def build_world():
    world = bpy.data.worlds.new("WLD_Studio")
    bpy.context.scene.world = world
    nt = world.node_tree
    bg = nt.nodes.get("Background")
    # soft vertical gradient - dusk blue studio
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    nt.links.new(tc.outputs['Generated'], sep.inputs['Vector'])
    nt.links.new(sep.outputs['Z'], ramp.inputs['Fac'])
    ramp.color_ramp.elements[0].position = 0.45
    ramp.color_ramp.elements[0].color = hex_lin("#1b2230")
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = hex_lin("#3a4a63")
    nt.links.new(ramp.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 0.4
    return world


def build_lights(col):
    # late-afternoon sun raking through the window only (ceiling blocks the rest)
    sun = _light("LGT_Sun_Window", 'SUN', col, (2.5, 6.0, 5.0), 9.0, "#ffb070", angle=1.2)
    sun.rotation_euler = Vector((-0.42, -0.78, -0.48)).to_track_quat('-Z', 'Y').to_euler()
    # window bounce / sky fill entering the room
    win = _light("LGT_Window_Fill", 'AREA', col, (0.9, 1.9, 1.55), 70, "#ffd9b0", size=1.2,
                 size_y=1.1, target=(0.9, 0, 1.0))
    # large soft key from camera side so characters read clearly
    key = _light("LGT_Key_Soft", 'AREA', col, (3.5, -4.5, 3.6), 120, "#ffeedd", size=3.0,
                 target=(-0.2, 0.0, 0.6))
    # cool rim from front-left to separate silhouettes from the warm room
    rim = _light("LGT_Rim_Cool", 'AREA', col, (-3.5, -3.5, 2.8), 130, "#9fc0ff", size=2.0,
                 target=(0.0, 0.2, 0.6))
    # warm practical bounce under the string lights
    bounce = _light("LGT_StringLights_Bounce", 'AREA', col, (-0.5, 0.2, 2.5), 40, "#ffc98a",
                    size=4.0, size_y=3.5, target=(-0.5, 0.2, 0.0))
    for o in (win, key, rim, bounce):
        o.data.use_shadow = True
    return dict(sun=sun, win=win, key=key, rim=rim, bounce=bounce)


def camera(name, col, loc, target, lens=50, dof_target=None, fstop=4.0, sensor=36):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_width = sensor
    cd.clip_start = 0.05
    cd.clip_end = 100
    cam = bpy.data.objects.new(name, cd)
    cam.location = loc
    col.objects.link(cam)
    _look_at(cam, target)
    if dof_target is not None:
        cd.dof.use_dof = True
        cd.dof.focus_object = dof_target
        cd.dof.aperture_fstop = fstop
    return cam


def render_settings(scene, engine='EEVEE', res=(1920, 1080), samples=64, pct=100):
    r = scene.render
    r.resolution_x, r.resolution_y = res
    r.resolution_percentage = pct
    r.fps = 24
    r.film_transparent = False
    vs = scene.view_settings
    try:
        vs.view_transform = 'AgX'
        vs.look = 'AgX - Medium High Contrast'
    except TypeError:
        pass
    vs.exposure = 0.0
    if engine == 'EEVEE':
        r.engine = 'BLENDER_EEVEE'
        ee = scene.eevee
        ee.taa_render_samples = samples
        ee.use_raytracing = True
        ee.ray_tracing_method = 'SCREEN'
        ee.use_shadows = True
        ee.shadow_ray_count = 2
        ee.shadow_step_count = 8
        ee.use_fast_gi = True
        ee.fast_gi_method = 'GLOBAL_ILLUMINATION'
        ee.fast_gi_distance = 2.0
        ee.ray_tracing_options.resolution_scale = '2'
    else:
        r.engine = 'CYCLES'
        c = scene.cycles
        c.samples = samples
        c.use_denoising = True
        c.max_bounces = 8
        c.diffuse_bounces = 4
        c.glossy_bounces = 4
        c.transmission_bounces = 6
        c.use_light_tree = True
        c.sample_clamp_indirect = 8.0
        try:
            prefs = bpy.context.preferences.addons['cycles'].preferences
            prefs.compute_device_type = 'METAL'
            prefs.refresh_devices()
            for d in prefs.devices:
                d.use = True
            c.device = 'GPU'
        except Exception:
            c.device = 'CPU'
    r.use_motion_blur = True
    r.motion_blur_shutter = 0.5
    r.image_settings.file_format = 'PNG'
    r.image_settings.color_mode = 'RGB'
