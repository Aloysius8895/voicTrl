"""Render named stills from watch.blend with Cycles.

  blender -b watch.blend -P render_stills.py -- --shots hero,explode --out C:/path
      [--samples 256] [--percent 100] [--explode 0.5]

Shot names are the keys of build_look.SHOTS. --explode overrides the shot's own value.
"""
import argparse
import json
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import build_look   # noqa: E402
import watch_lib    # noqa: E402

OUR_PARTS = ("SM_cradle", "SM_strap", "SM_buckle", "SM_strap_keeper")


def gpu():
    """Use OptiX (or CUDA) when the machine has it; otherwise stay on the CPU."""
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = kind
        except TypeError:
            continue
        prefs.get_devices()
        used = [d for d in prefs.devices if d.type == kind]
        if used:
            for d in prefs.devices:
                d.use = d.type == kind
            scene.cycles.device = "GPU"
            return kind
    scene.cycles.device = "CPU"
    return "CPU"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default="hero")
    ap.add_argument("--out", default=os.path.join(HERE, "..", "shots"))
    ap.add_argument("--samples", type=int, default=256)
    ap.add_argument("--percent", type=int, default=100)
    ap.add_argument("--explode", type=float, default=None)
    ap.add_argument("--suffix", default="")
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])

    scene = bpy.context.scene
    device = gpu()
    c = scene.cycles
    c.samples = args.samples
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.015
    c.use_denoising = True
    c.max_bounces, c.glossy_bounces, c.transmission_bounces = 12, 6, 12
    c.sample_clamp_indirect = 8.0
    scene.render.resolution_percentage = args.percent
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False

    rig = bpy.data.objects["LOOK_rig"]
    written = []
    for name in args.shots.split(","):
        pos, target, lens, explode, module_only, _ = build_look.SHOTS[name]
        cam = bpy.data.objects["CAM_" + name]
        scene.camera = cam
        scene.render.resolution_x, scene.render.resolution_y = build_look.RES.get(name, (1920, 1080))
        rig.location = [v / 1000 for v in target]
        rig.rotation_euler = cam.rotation_euler
        for n in OUR_PARTS:
            bpy.data.objects[n].hide_render = module_only
        watch_lib.set_explode(explode if args.explode is None else args.explode)
        path = os.path.abspath(os.path.join(args.out, name + args.suffix + ".png"))
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        written.append(path)
    print("@@JSON@@" + json.dumps({"device": device, "written": written}))


if __name__ == "__main__":
    main()
