# Character Bible

## Pip — the sprout
**Personality:** curious, easily delighted, a little dreamy. Pip spends the evenings watching
the sunset from the living-room window.

| | |
|---|---|
| Height | 0.70 m to the sprout tip (body 0.50 m) |
| Silhouette | bean-shaped body that doubles as the head, a two-leaf sprout, stubby mitten arms and round feet |
| Palette | mint skin `#6FBF95–#86CFA4`, cream belly `#FFF1D8`, blush `#F3968A`, leaf `#93CF5A`, mustard scarf `#E7A436` with cream stripes |
| Surface | soft-touch: subsurface 0.25, light sheen and clear-coat, subtle mottling |
| Face | large glossy eyes with catch-lights lit from the same direction (upper camera-left), a tiny smile, blush cheeks |

**Rig (16 bones):** `root, hips, spine, head, sprout.01–02, eye.L/R, upper_arm/forearm.L/R,
thigh/foot.L/R`
- The body weights blend hips → spine → head by height. The face region (z ≥ 0.35 m)
  belongs entirely to `head`, so the eyes, cheeks and mouth never slide on the surface.
- Blink = `eye.*` Y-scale. Breathing = `spine` scale. Squash and stretch = `hips` scale.
- The sprout is a 2-bone chain driven by baked spring dynamics.
- The arms have FK plus mug-driven IK, with 12% stretch allowed.

**Acting notes:** Pip leads turns with the head, anticipates with a squash, and stretches
on take-off. Arms go up when Pip is happy. Pip closes its eyes while it sips.

## Tock — the hover-bot
**Personality:** a dutiful, gentle helper. Tock sleeps on its charging dock and wakes up to
bring Pip cocoa.

| | |
|---|---|
| Height | 0.93 m to the antenna bulb, hovering about 0.10 m off the floor |
| Silhouette | big rounded CRT head, accordion neck, rounded box torso, thruster saucer, ribbed-hose arms with two-prong claws |
| Palette | cream shell `#F4ECDF`, coral `#EE7C56`, rubber `#2F3337`, screen `#0D1B1D`, face glow `#5EE8D6`, bulb `#FF9A2E` |
| Shape language | soft rounded boxes for a friendly read, with accent buttons in the room's mustard and teal |

**Rig (22 bones):** `root, hover, body, neck, head, antenna.01–02, mouth, eye.L/R,
eye_happy.L/R, upper_arm/forearm/hand.L/R, claw_front/claw_back.L/R`
- Every part is skinned 100% to one bone, the game-engine standard for mechanical rigs.
- Expressions: normal eyes `eye.*` and happy arcs `eye_happy.*` cross-fade by scale.
- `hover` carries a procedural bob plus baked banking that leans into acceleration. The
  antenna follows through on a spring.
- A teal thruster light is bone-parented to `hover`, so it lights the floor under Tock.

**Acting notes:** Tock is asleep at first, with its head drooped and eyes dimmed. On waking
it rises before moving. When carrying the mug, the hand counter-rotates to keep the mug
upright. It shows happy eyes with a little "ta-da" arm.

## Relationship and staging
Pip and Tock are housemates. Pip is small and organic, Tock is taller and mechanical, and
the warm coral and mint palettes complement each other. In two-shots they stand on a line
perpendicular to the lens, each turned about 40° toward camera so both faces read.
