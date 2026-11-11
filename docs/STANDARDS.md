# Production Standards

These conventions follow common studio and game-pipeline practice. The build scripts
enforce them, so the generated master file always complies.

## Scene, units and orientation
- Metric, **1 unit = 1 m**, `scale_length = 1.0`. Real-world proportions: walls 2.6 m,
  sofa seat 0.39 m, Pip 0.70 m, Tock 0.93 m.
- **+Z up, −Y front.** Every asset faces −Y in its own space. Characters face −Y in rest
  pose (Blender/FBX convention), and `.L` is the character's left (+X).
- Object transforms stay clean. Geometry is authored in object space, and props are
  positioned through a parent root (`ENV_<Prop>` empty), not by baking offsets into
  child meshes.
- Origins sit at the logical pivot: base-centre for furniture, ground-centre for rigs.

## Naming
| Prefix | Use | Example |
|---|---|---|
| `CH_` | character meshes / collections | `CH_Pip_Body`, `CH_Tock_Head` |
| `RIG_` | armatures | `RIG_Pip` |
| `WGT_` | bone custom-shape widgets (hidden collection) | `WGT_circle` |
| `ENV_` | environment meshes / prop roots | `ENV_Sofa_SeatCushion_0` |
| `PROP_` | animated hand props | `PROP_Mug_Cocoa`, `PROP_Mug_Hold` |
| `MAT_` | materials | `MAT_Wood_Floor`, `MAT_Pip_Skin` |
| `LGT_` | lights | `LGT_Sun_Window` |
| `CAM_` | cameras / camera targets | `CAM_Anim`, `CAM_Anim_Target` |
| `WLD_` | worlds | `WLD_Studio` |

- Parts use `<Asset>_<Part>[_<Index>]`, and indices are zero-based.
- Sided parts and bones end in `.L` / `.R` so mirror tools work.
- Actions are named `<Char>_<Shot>`, for example `Pip_CocoaDelivery`.

## Collections
```
SCN_CozyNook
├── ENV            ENV_Architecture · ENV_Furniture · ENV_Props · ENV_Outside
├── CH             CH_Pip · CH_Tock
├── PROP           animated props + IK targets
├── LGT            lighting rig
├── CAM            animation + still cameras
└── WGT            bone widgets (hidden, never rendered)
```

## Modelling
- Quads where possible. Smooth surfaces use Subdivision (viewport 1 / render 2).
  Hard-surface parts use angle-limited Bevel (arc miter) instead of subdivision.
- The modifier stack order is **Armature → Bevel/Solidify → Subdivision**, so the base
  mesh deforms before smoothing.
- Instanced or repeated elements (books, floor boards, beadboard) are merged per material
  to keep the object count and draw calls down.
- Every primitive has UVs (`UVMap`), even though the shaders are procedural, so the
  assets can be texture-baked or exported.

## Materials
- Principled BSDF only, so they render the same in EEVEE and Cycles and survive
  glTF/FBX export.
- Colours are authored in sRGB hex and converted to linear in code (`materials.hex_lin`).
- No external image textures; the project is fully self-contained.
- Surface variation uses Object or `rest_pos` coordinates, so patterns stick to
  deforming meshes.

## Rigging
- One armature per character. The `root` bone lies on the ground pointing +Y and owns the
  hierarchy. Everything else is `hips/body → spine/neck → head` plus limbs.
- Meshes are parented to the armature and deformed by an **Armature modifier with vertex
  groups**. That means no bone-parented meshes, which keeps the rigs FBX/glTF-safe.
  Non-mesh children (lights) use bone parenting with a corrected parent inverse.
- Control bones have custom widgets and bone colours (left = blue, right = red,
  centre = yellow).
- Rotations are quaternions. Script keys are authored around rest-space axes
  (`rig.rot_world`), so values mean the same thing on every bone.
- IK chains are 2 bones, with influence animated for FK ↔ IK blending. Stretch is
  limited to 12%.

## Animation
- 24 fps, frames 1–300. Keys use Bézier with auto-clamped handles.
- Primary animation is keyed pose to pose. Secondary motion is simulated and baked
  (see `animation._spring`), never hand-keyed on the same channels.
- Layered channels avoid conflicts: breathing sits on `spine` scale, squash and stretch
  on `hips` scale, blinks on eye-bone Y scale.
- Constraint switches use CONSTANT interpolation on influence, with matched inverse
  matrices at the switch frame.

## Rendering
- Colour management: AgX, look *Medium High Contrast*, exposure 0.
- Animation: EEVEE, ray-traced screen-space GI, 64 samples, motion blur at shutter 0.5,
  rendered as a PNG sequence and then encoded to H.264 (CRF 18, yuv420p).
- Stills: Cycles on the Metal GPU, 256 samples, OpenImageDenoise, light tree.
- Renders go to `renders/<type>/` and are never written next to source files.

## Files and versioning
- `blend/CozyNook_Master.blend` is a build artefact; the scripts are the source of truth.
- Work-in-progress review images go to `renders/wip/` and are excluded from git.
