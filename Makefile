# Cozy Nook build targets. Override BLENDER on non-macOS systems.
BLENDER ?= /Applications/Blender.app/Contents/MacOS/Blender
MASTER  := blend/CozyNook_Master.blend
FRAMES  := renders/anim/frames
MOVIE   := renders/anim/CozyNook_CocoaDelivery_1080p.mp4

.PHONY: all scene anim movie stills clay turnarounds sheets exports review clean-wip

all: scene anim movie stills clay turnarounds sheets exports

scene:
	$(BLENDER) -b --factory-startup -P scripts/build_scene.py -- --camera CAM_Anim --samples 64 --pct 100

anim: scene
	mkdir -p $(FRAMES)
	$(BLENDER) -b $(MASTER) -o "$(CURDIR)/$(FRAMES)/CozyNook_####" -F PNG -a

movie:
	ffmpeg -y -framerate 24 -i $(FRAMES)/CozyNook_%04d.png -c:v libx264 -crf 18 -preset slow \
	  -pix_fmt yuv420p -movflags +faststart $(MOVIE)

stills:
	$(BLENDER) -b $(MASTER) -P scripts/render_stills.py -- --samples 256

clay:
	$(BLENDER) -b $(MASTER) -P scripts/render_stills.py -- --clay --engine EEVEE --samples 64 --only Hero

turnarounds:
	for c in pip tock; do \
	  $(BLENDER) -b --factory-startup -P scripts/render_turnaround.py -- --char $$c --engine CYCLES --samples 128 --pct 100; \
	  $(BLENDER) -b --factory-startup -P scripts/render_turnaround.py -- --char $$c --views threequarter --pose --engine CYCLES --samples 128 --pct 100; \
	  $(BLENDER) -b --factory-startup -P scripts/render_turnaround.py -- --char $$c --views front,threequarter --wire --samples 64 --pct 100; \
	done

sheets:
	python3 scripts/make_sheets.py

exports:
	$(BLENDER) -b $(MASTER) -P scripts/export_assets.py

review:
	$(BLENDER) -b $(MASTER) -P scripts/render_contact_sheet.py -- \
	  --frames 1,60,100,118,140,158,190,212,224,256,280,300 --cols 4 --out "$(CURDIR)/renders/wip/review.png"

clean-wip:
	rm -rf renders/wip/*
