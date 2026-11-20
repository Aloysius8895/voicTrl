"""Studio set: black world, a soft key, two strip lights, and the named cameras.

The four lights hang on LOOK_rig. render_stills.py turns the rig to face whichever
camera is rendering, so every view gets the same key-from-upper-left lighting.
"""
import math

import bpy
from mathutils import Matrix, Vector

LOOK = "LOOK"

# name: (camera position mm, target mm, lens mm, explode, hide strap+cradle, world axis that is "up" in frame)
SHOTS = {
    "hero":      ((150, -185, 200), (0, 0, -16), 85, 0.0, False, "Z"),
    "edge_fn":   ((150, -55, 42), (23, -4, 0), 100, 0.0, False, "Z"),
    "edge_usb":  ((-150, -55, 42), (-23, 0, 0), 100, 0.0, False, "Z"),
    "back":      ((-150, 120, -250), (0, 0, -2), 85, 0.0, True, "X"),
    "explode":   ((300, -385, 152), (0, 0, -33), 85, 1.0, False, "Z"),
    # the three official photo angles: module only, Function-button edge up
    "ref_iso":   ((-150, -115, 240), (0, 0, 0), 85, 0.0, True, "X"),
    "ref_front": ((120, -125, 245), (0, 0, 0), 85, 0.0, True, "X"),
    "ref_back":  ((-150, 120, -240), (0, 0, 0), 85, 0.0, True, "X"),
    "back_flat": ((0, 0, -330), (0, 0, 0), 100, 0.0, True, "X"),     # straight on, to read the markings
}
UP = {"X": Vector((1, 0, 0)), "Z": Vector((0, 0, 1))}
RES = {"explode": (1200, 1800)}      # every other shot is 1920 x 1080


def look_at(pos, target, up):
    """Rotation for a camera at pos looking at target with the given world axis up in frame."""
    back = (pos - target).normalized()
    right = up.cross(back).normalized()
    true_up = back.cross(right)
    return Matrix((right, true_up, back)).transposed().to_euler()


def _collection():
    c = bpy.data.collections.get(LOOK)
    if c is None:
        c = bpy.data.collections.new(LOOK)
        bpy.context.scene.collection.children.link(c)
    return c


def _area(name, rig, pos_mm, size_mm, power, color=(1, 1, 1)):
    light = bpy.data.lights.new(name, "AREA")
    light.shape = "RECTANGLE"
    light.size, light.size_y = size_mm[0] / 1000, size_mm[1] / 1000
    light.energy = power
    light.color = color
    ob = bpy.data.objects.new(name, light)
    _collection().objects.link(ob)
    ob.parent = rig
    ob.location = Vector(pos_mm) / 1000
    ob.rotation_euler = (-ob.location).to_track_quat("-Z", "Y").to_euler()   # aim at the rig origin
    return ob


def build():
    scene = bpy.context.scene
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.name = "LOOK_world_black"
    nt = world.node_tree
    if nt is None:
        world.use_nodes = True
        nt = world.node_tree
    # black to the camera, a dim grey dome to everything else, so metals have something to reflect
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    dome = nt.nodes.new("ShaderNodeBackground")
    dome.inputs["Color"].default_value = (0.5, 0.5, 0.5, 1)
    dome.inputs["Strength"].default_value = 0.10
    black = nt.nodes.new("ShaderNodeBackground")
    black.inputs["Color"].default_value = (0, 0, 0, 1)
    black.inputs["Strength"].default_value = 0.0
    path = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(path.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(dome.outputs[0], mix.inputs[1])
    nt.links.new(black.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])

    rig = bpy.data.objects.new("LOOK_rig", None)
    rig.empty_display_size = 0.02
    _collection().objects.link(rig)
    # rig space: +X right of the camera, +Y up, +Z towards the camera
    _area("LOOK_key_softbox", rig, (-330, 170, 330), (300, 300), 9.0)
    _area("LOOK_strip_right", rig, (330, 60, -120), (40, 520), 7.0)
    _area("LOOK_strip_left", rig, (-340, -20, -200), (40, 520), 5.0)
    _area("LOOK_glass_streak", rig, (-75, 440, -50), (40, 420), 0.3)

    for name, (pos, target, lens, _, _, up) in SHOTS.items():
        cam = bpy.data.cameras.new("CAM_" + name)
        cam.lens = lens
        cam.clip_start, cam.clip_end = 0.02, 3.0
        ob = bpy.data.objects.new("CAM_" + name, cam)
        _collection().objects.link(ob)
        ob.location = Vector(pos) / 1000
        ob.rotation_euler = look_at(ob.location, Vector(target) / 1000, UP[up])
        ob["target_mm"] = [float(v) for v in target]
    scene.camera = bpy.data.objects["CAM_hero"]

    r = scene.render
    r.resolution_x, r.resolution_y, r.resolution_percentage = 1920, 1080, 100
    try:   # faithful colours for a product shot; AgX washed the orange out to salmon
        scene.view_settings.view_transform = "Khronos PBR Neutral"
    except TypeError as err:
        print("view transform:", err)
    scene.view_settings.exposure = -0.8          # keeps the white case below clipping
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
