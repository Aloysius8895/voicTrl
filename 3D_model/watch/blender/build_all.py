"""Rebuild the whole watch and save watch.blend.

Headless:   blender -b --factory-startup -P build_all.py
In Blender: import sys; sys.path.insert(0, r"<this folder>"); import build_all; build_all.run()

run() deletes only what an earlier run made (collections WATCH, WATCH_cutters, LOOK
and the data blocks named SM_*, M_*, LOOK_*, CAM_*), then builds everything again.
"""
import importlib
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

OURS = ("SM_", "M_", "LOOK_", "CAM_", "WATCH_", "cut", "bosses", "openings", "ribs", "flange")


def clear():
    for name in ("WATCH", "WATCH_cutters", "LOOK"):
        c = bpy.data.collections.get(name)
        if c:
            for ob in list(c.all_objects):
                bpy.data.objects.remove(ob)
            bpy.data.collections.remove(c)
    for blocks in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras):
        for b in list(blocks):
            if b.users == 0 and b.name.startswith(OURS):
                blocks.remove(b)


def run(save=True):
    import spec, watch_lib, watch_mats, build_case, build_boards, build_marks, build_strap, build_look
    for mod in (spec, watch_lib, watch_mats, build_case, build_boards, build_marks, build_strap, build_look):
        importlib.reload(mod)
    clear()
    if bpy.app.background and bpy.data.filepath == "":
        # headless factory start only: drop the startup cube, light and camera
        for name in ("Cube", "Light", "Camera"):
            ob = bpy.data.objects.get(name)
            if ob:
                bpy.data.objects.remove(ob)
    mats = watch_mats.build()
    build_case.build(mats)
    build_boards.build(mats)
    build_marks.build(mats)
    build_strap.build(mats)
    watch_lib.add_explode_drivers()
    build_look.build()
    c = bpy.data.collections.get("WATCH_cutters")
    if c:
        bpy.data.collections.remove(c)
    meshes = [o for o in bpy.data.collections["WATCH"].all_objects if o.type == "MESH"]
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in meshes)
    out = os.path.join(HERE, "watch.blend")
    if save:
        bpy.ops.wm.save_as_mainfile(filepath=out)
    info = {"objects": len(meshes), "triangles": tris, "materials": len([m for m in bpy.data.materials if m.name.startswith("M_")]),
            "saved": out if save else None}
    print("@@JSON@@" + __import__("json").dumps(info))
    return info


if __name__ == "__main__":
    run()
