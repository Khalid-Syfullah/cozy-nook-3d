"""Procedural material library (no external textures -> fully portable .blend).

Every material is prefixed ``MAT_`` and built from Principled BSDF so it renders
identically in EEVEE and Cycles. Colours are authored in sRGB hex and converted
to linear, matching how a texture artist would pick them.
"""
import bpy

_CACHE = {}


def hex_lin(h, a=1.0):
    h = h.lstrip('#')
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return (*lin, a)


class NodeBuilder:
    def __init__(self, name):
        self.mat = bpy.data.materials.new("MAT_" + name)
        self.nt = self.mat.node_tree
        self.nodes = self.nt.nodes
        self.links = self.nt.links
        self.bsdf = self.nodes.get("Principled BSDF")
        self.out = self.nodes.get("Material Output")
        self._x = -300

    def node(self, kind, **props):
        n = self.nodes.new(kind)
        n.location = (self._x, len(self.nodes) * -40)
        self._x -= 40
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def link(self, a, b):
        self.links.new(a, b)

    def set(self, **inputs):
        for k, v in inputs.items():
            self.bsdf.inputs[k].default_value = v


def _coords(nb, space='Object', scale=(1, 1, 1)):
    tc = nb.node('ShaderNodeTexCoord')
    mp = nb.node('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = scale
    nb.link(tc.outputs[space], mp.inputs['Vector'])
    return mp.outputs['Vector']


def _ramp(nb, fac, stops, interp='LINEAR'):
    cr = nb.node('ShaderNodeValToRGB')
    cr.color_ramp.interpolation = interp
    els = cr.color_ramp.elements
    while len(els) > len(stops):
        els.remove(els[-1])
    while len(els) < len(stops):
        els.new(0.5)
    for el, (pos, col) in zip(els, stops):
        el.position = pos
        el.color = hex_lin(col) if isinstance(col, str) else col
    nb.link(fac, cr.inputs['Fac'])
    return cr.outputs['Color']


def _bump(nb, height, strength=0.2, distance=0.01):
    b = nb.node('ShaderNodeBump')
    b.inputs['Strength'].default_value = strength
    b.inputs['Distance'].default_value = distance
    nb.link(height, b.inputs['Height'])
    nb.link(b.outputs['Normal'], nb.bsdf.inputs['Normal'])
    return b


def cached(fn):
    def wrap(name, *a, **kw):
        if name not in _CACHE:
            _CACHE[name] = fn(name, *a, **kw)
        return _CACHE[name]
    wrap.__name__ = fn.__name__
    return wrap


# --------------------------------------------------------------------------- #
# Generic families
# --------------------------------------------------------------------------- #
@cached
def solid(name, color, rough=0.5, metal=0.0, coat=0.0, sss=0.0, sheen=0.0, spec=0.5):
    nb = NodeBuilder(name)
    nb.set(**{'Base Color': hex_lin(color), 'Roughness': rough, 'Metallic': metal,
              'Coat Weight': coat, 'Subsurface Weight': sss, 'Sheen Weight': sheen,
              'Specular IOR Level': spec})
    if sss:
        nb.set(**{'Subsurface Radius': (0.25, 0.12, 0.08), 'Subsurface Scale': 0.05})
    return nb.mat


@cached
def noisy(name, c1, c2, rough=0.6, scale=8.0, bump=0.08, detail=6, sheen=0.0, coat=0.0,
          metal=0.0, sss=0.0):
    """Two-tone noise variation - plaster, ceramics, plastics with wear."""
    nb = NodeBuilder(name)
    v = _coords(nb, 'Object', (scale,) * 3)
    nz = nb.node('ShaderNodeTexNoise')
    nz.inputs['Detail'].default_value = detail
    nb.link(v, nz.inputs['Vector'])
    col = _ramp(nb, nz.outputs['Fac'], [(0.35, c1), (0.65, c2)])
    nb.link(col, nb.bsdf.inputs['Base Color'])
    nb.set(**{'Roughness': rough, 'Sheen Weight': sheen, 'Coat Weight': coat,
              'Metallic': metal, 'Subsurface Weight': sss})
    if bump:
        _bump(nb, nz.outputs['Fac'], bump)
    return nb.mat


@cached
def fabric(name, c1, c2, scale=60.0, rough=0.85):
    """Woven fabric: fine noise + weave bump + sheen for soft furnishings."""
    nb = NodeBuilder(name)
    v = _coords(nb, 'Object', (1, 1, 1))
    nz = nb.node('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 6
    nb.link(v, nz.inputs['Vector'])
    col = _ramp(nb, nz.outputs['Fac'], [(0.3, c1), (0.7, c2)])
    nb.link(col, nb.bsdf.inputs['Base Color'])
    wave = nb.node('ShaderNodeTexWave')
    wave.inputs['Scale'].default_value = scale
    wave.inputs['Distortion'].default_value = 2.0
    nb.link(v, wave.inputs['Vector'])
    _bump(nb, wave.outputs['Fac'], 0.12, 0.004)
    nb.set(**{'Roughness': rough, 'Sheen Weight': 0.6, 'Sheen Roughness': 0.4,
              'Sheen Tint': (1, 1, 1, 1)})
    return nb.mat


@cached
def wood(name, light, dark, grain=(0.6, 18, 18), rough=0.45, coat=0.15, rand_attr=None):
    """Long-grain wood along local X. ``rand_attr`` offsets grain per board."""
    nb = NodeBuilder(name)
    tc = nb.node('ShaderNodeTexCoord')
    vec = tc.outputs['Object']
    if rand_attr:
        attr = nb.node('ShaderNodeAttribute', attribute_name=rand_attr)
        vm = nb.node('ShaderNodeVectorMath', operation='MULTIPLY_ADD')
        vm.inputs[1].default_value = (37.0, 11.0, 5.0)
        nb.link(attr.outputs['Vector'], vm.inputs[0])
        nb.link(tc.outputs['Object'], vm.inputs[2])
        vec = vm.outputs['Vector']
    mp = nb.node('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = grain
    nb.link(vec, mp.inputs['Vector'])
    nz = nb.node('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 2.0
    nz.inputs['Detail'].default_value = 8
    nz.inputs['Distortion'].default_value = 0.6
    nb.link(mp.outputs['Vector'], nz.inputs['Vector'])
    col = _ramp(nb, nz.outputs['Fac'], [(0.3, dark), (0.72, light)])
    if rand_attr:
        # per-board tone shift
        attr2 = nb.node('ShaderNodeAttribute', attribute_name=rand_attr)
        sep = nb.node('ShaderNodeSeparateXYZ')
        nb.link(attr2.outputs['Vector'], sep.inputs['Vector'])
        mr = nb.node('ShaderNodeMapRange')
        mr.inputs['To Min'].default_value = 0.72
        mr.inputs['To Max'].default_value = 1.18
        nb.link(sep.outputs['X'], mr.inputs['Value'])
        cmb = nb.node('ShaderNodeCombineXYZ')
        for i in range(3):
            nb.link(mr.outputs['Result'], cmb.inputs[i])
        mul = nb.node('ShaderNodeVectorMath', operation='MULTIPLY')
        nb.link(col, mul.inputs[0])
        nb.link(cmb.outputs['Vector'], mul.inputs[1])
        col = mul.outputs['Vector']
    nb.link(col, nb.bsdf.inputs['Base Color'])
    _bump(nb, nz.outputs['Fac'], 0.06, 0.003)
    nb.set(**{'Roughness': rough, 'Coat Weight': coat, 'Coat Roughness': 0.25})
    return nb.mat


@cached
def emission(name, color, strength=5.0, base=None):
    nb = NodeBuilder(name)
    nb.set(**{'Base Color': hex_lin(base or color), 'Emission Color': hex_lin(color),
              'Emission Strength': strength, 'Roughness': 0.3})
    return nb.mat


@cached
def glass(name, tint='#dfefff', rough=0.02):
    nb = NodeBuilder(name)
    nb.set(**{'Base Color': hex_lin(tint), 'Roughness': rough, 'Transmission Weight': 1.0,
              'IOR': 1.45, 'Alpha': 0.25})
    nb.mat.surface_render_method = 'BLENDED'
    return nb.mat


@cached
def rings(name, stops, rough=0.9, scale=1.0):
    """Concentric bands (round rugs, targets). stops: [(pos, hex), ...]"""
    nb = NodeBuilder(name)
    v = _coords(nb, 'Object', (scale, scale, scale))
    grad = nb.node('ShaderNodeTexGradient', gradient_type='SPHERICAL')
    nb.link(v, grad.inputs['Vector'])
    inv = nb.node('ShaderNodeMath', operation='SUBTRACT')
    inv.inputs[0].default_value = 1.0
    nb.link(grad.outputs['Fac'], inv.inputs[1])
    col = _ramp(nb, inv.outputs['Value'], stops, 'CONSTANT')
    nb.link(col, nb.bsdf.inputs['Base Color'])
    nz = nb.node('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 400
    nb.link(v, nz.inputs['Vector'])
    _bump(nb, nz.outputs['Fac'], 0.35, 0.004)
    nb.set(**{'Roughness': rough, 'Sheen Weight': 1.0, 'Sheen Roughness': 0.5})
    return nb.mat


@cached
def sky_backdrop(name, top, horizon, strength=2.5):
    """Emissive vertical gradient for the view outside the window."""
    nb = NodeBuilder(name)
    tc = nb.node('ShaderNodeTexCoord')
    sep = nb.node('ShaderNodeSeparateXYZ')
    nb.link(tc.outputs['Generated'], sep.inputs['Vector'])
    col = _ramp(nb, sep.outputs['Z'], [(0.2, horizon), (0.85, top)])
    em = nb.node('ShaderNodeEmission')
    em.inputs['Strength'].default_value = strength
    nb.link(col, em.inputs['Color'])
    nb.link(em.outputs['Emission'], nb.out.inputs['Surface'])
    return nb.mat


@cached
def painting(name, colors, rough=0.7, scale=1.0):
    """Abstract landscape canvas: stacked wavy bands."""
    nb = NodeBuilder(name)
    tc = nb.node('ShaderNodeTexCoord')
    sep = nb.node('ShaderNodeSeparateXYZ')
    nb.link(tc.outputs['Generated'], sep.inputs['Vector'])
    wave = nb.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='X')
    wave.inputs['Scale'].default_value = 1.2 * scale
    wave.inputs['Distortion'].default_value = 3.0
    nb.link(tc.outputs['Generated'], wave.inputs['Vector'])
    add = nb.node('ShaderNodeMath', operation='MULTIPLY_ADD')
    add.inputs[1].default_value = 0.12
    nb.link(wave.outputs['Fac'], add.inputs[0])
    nb.link(sep.outputs['Z'], add.inputs[2])
    stops = [(i / len(colors), c) for i, c in enumerate(colors)]
    col = _ramp(nb, add.outputs['Value'], stops, 'CONSTANT')
    nb.link(col, nb.bsdf.inputs['Base Color'])
    nb.set(**{'Roughness': rough})
    return nb.mat


@cached
def checker_cloth(name, c1, c2, scale=12.0):
    nb = NodeBuilder(name)
    v = _coords(nb, 'Generated', (1, 1, 1))
    ch = nb.node('ShaderNodeTexChecker')
    ch.inputs['Scale'].default_value = scale
    ch.inputs['Color1'].default_value = hex_lin(c1)
    ch.inputs['Color2'].default_value = hex_lin(c2)
    nb.link(v, ch.inputs['Vector'])
    nb.link(ch.outputs['Color'], nb.bsdf.inputs['Base Color'])
    nb.set(**{'Roughness': 0.85, 'Sheen Weight': 0.8})
    return nb.mat


@cached
def knit(name, c1, c2, stripe=None):
    """Chunky rib knit following UV (u = around, v = along the tube):
    fine ribs across the length + optional broad accent stripes."""
    nb = NodeBuilder(name)
    tc = nb.node('ShaderNodeTexCoord')
    sep = nb.node('ShaderNodeSeparateXYZ')
    nb.link(tc.outputs['UV'], sep.inputs['Vector'])
    rib = nb.node('ShaderNodeMath', operation='SINE')
    mul = nb.node('ShaderNodeMath', operation='MULTIPLY')
    mul.inputs[1].default_value = 6.2832 * 70
    nb.link(sep.outputs['Y'], mul.inputs[0])
    nb.link(mul.outputs['Value'], rib.inputs[0])
    absn = nb.node('ShaderNodeMath', operation='ABSOLUTE')
    nb.link(rib.outputs['Value'], absn.inputs[0])
    col = _ramp(nb, absn.outputs['Value'], [(0.1, c2), (0.9, c1)])
    if stripe:
        band = nb.node('ShaderNodeMath', operation='FRACT')
        m2 = nb.node('ShaderNodeMath', operation='MULTIPLY')
        m2.inputs[1].default_value = 7.0
        nb.link(sep.outputs['Y'], m2.inputs[0])
        nb.link(m2.outputs['Value'], band.inputs[0])
        mask = _ramp(nb, band.outputs['Value'], [(0.0, (0, 0, 0, 1)), (0.78, (1, 1, 1, 1))], 'CONSTANT')
        mix = nb.node('ShaderNodeMix', data_type='RGBA')
        nb.link(mask, mix.inputs[0])
        nb.link(col, mix.inputs[6])
        mix.inputs[7].default_value = hex_lin(stripe)
        col = mix.outputs[2]
    nb.link(col, nb.bsdf.inputs['Base Color'])
    _bump(nb, absn.outputs['Value'], 0.6, 0.006)
    nb.set(**{'Roughness': 0.92, 'Sheen Weight': 1.0, 'Sheen Roughness': 0.35})
    return nb.mat
