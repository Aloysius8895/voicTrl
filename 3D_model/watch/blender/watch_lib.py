"""Shared helpers for the voicTrl watch model.

Geometry is authored in millimetres and scaled to metres in make().
Frame: origin at the module centre, screen faces +Z, the orange Function
button edge faces +X, the USB-C edge faces -X, the strap leaves along +-Y.
"""
import math

import bmesh
import bpy
from mathutils import Matrix

MM = 0.001
WATCH = "WATCH"
CUTTERS = "WATCH_cutters"
ROOT = "WATCH_root"

# local (u, v, w) -> world. 'X': profile is (Y, Z), extruded along X.
# 'Y': profile is (X, Z), extruded along Y (mirrored; make() fixes normals).
AXIS = {
    "Z": Matrix.Identity(3),
    "X": Matrix(((0, 0, 1), (1, 0, 0), (0, 1, 0))),
    "Y": Matrix(((1, 0, 0), (0, 0, 1), (0, 1, 0))),
}


# ---------------------------------------------------------------- scene
def collection(name=WATCH):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    return c


def root():
    ob = bpy.data.objects.get(ROOT)
    if ob is None:
        ob = bpy.data.objects.new(ROOT, None)
        ob.empty_display_size = 0.01
        collection().objects.link(ob)
        ob["explode"] = 0.0
        ob.id_properties_ui("explode").update(
            min=0.0, max=1.0, soft_min=0.0, soft_max=1.0,
            description="0 = assembled, 1 = fully exploded")
    return ob


# ---------------------------------------------------------------- 2D profiles
def rrect(w, h, r, seg=8, cx=0.0, cy=0.0):
    """Rounded rectangle, counter-clockwise, always 4 * (seg + 1) points."""
    r = max(min(r, w / 2 - 1e-4, h / 2 - 1e-4), 1e-4)
    pts = []
    for sx, sy, a0 in ((1, -1, -90), (1, 1, 0), (-1, 1, 90), (-1, -1, 180)):
        ox, oy = cx + sx * (w / 2 - r), cy + sy * (h / 2 - r)
        for i in range(seg + 1):
            a = math.radians(a0 + 90 * i / seg)
            pts.append((ox + r * math.cos(a), oy + r * math.sin(a)))
    return pts


def circle(r, seg=24, cx=0.0, cy=0.0):
    return [(cx + r * math.cos(2 * math.pi * i / seg),
             cy + r * math.sin(2 * math.pi * i / seg)) for i in range(seg)]


def rect(x0, x1, y0, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def rot2(pts, deg, cx=0.0, cy=0.0):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [(cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c)
            for x, y in pts]


# ---------------------------------------------------------------- solids
def _to_axis(verts, axis):
    if axis != "Z":
        m = AXIS[axis]
        for v in verts:
            v.co = m @ v.co


def loft(bm, rings, axis="Z", cap=True):
    """Closed solid through rings [(points, height), ...] with equal counts."""
    vr = [[bm.verts.new((x, y, z)) for x, y in pts] for pts, z in rings]
    n = len(vr[0])
    for a, b in zip(vr, vr[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    if cap:
        bm.faces.new(list(reversed(vr[0])))
        bm.faces.new(vr[-1])
    verts = [v for ring in vr for v in ring]
    _to_axis(verts, axis)
    return verts


def prism(bm, pts, a0, a1, axis="Z"):
    return loft(bm, [(pts, a0), (pts, a1)], axis)


def box(bm, x0, x1, y0, y1, z0, z1):
    return prism(bm, rect(x0, x1, y0, y1), z0, z1)


def cyl(bm, r, a0, a1, cx=0.0, cy=0.0, seg=24, axis="Z"):
    return prism(bm, circle(r, seg, cx, cy), a0, a1, axis)


def fbox(bm, w, h, r, z0, z1, f=0.5, cx=0.0, cy=0.0, seg=8, fs=4,
         top=True, bottom=True, axis="Z"):
    """Rounded-rectangle prism with quarter-round edges of radius f."""
    def ring(d, z):
        return (rrect(w - 2 * d, h - 2 * d, r - d, seg, cx, cy), z)

    rings = []
    if bottom:
        for k in range(fs):
            a = math.radians(90 * k / fs)
            rings.append(ring(f * (1 - math.sin(a)), z0 + f * (1 - math.cos(a))))
        rings.append(ring(0.0, z0 + f))
    else:
        rings.append(ring(0.0, z0))
    if top:
        rings.append(ring(0.0, z1 - f))
        for k in range(fs - 1, -1, -1):
            a = math.radians(90 * k / fs)
            rings.append(ring(f * (1 - math.sin(a)), z1 - f * (1 - math.cos(a))))
    else:
        rings.append(ring(0.0, z1))
    return loft(bm, rings, axis)


def ring_prism(bm, outer, inner, a0, a1, axis="Z"):
    """Closed tube between two loops with the same point count."""
    n = len(outer)
    assert len(inner) == n
    vo0 = [bm.verts.new((x, y, a0)) for x, y in outer]
    vo1 = [bm.verts.new((x, y, a1)) for x, y in outer]
    vi0 = [bm.verts.new((x, y, a0)) for x, y in inner]
    vi1 = [bm.verts.new((x, y, a1)) for x, y in inner]
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((vo0[i], vo0[j], vo1[j], vo1[i]))
        bm.faces.new((vi0[j], vi0[i], vi1[i], vi1[j]))
        bm.faces.new((vo0[j], vo0[i], vi0[i], vi0[j]))
        bm.faces.new((vo1[i], vo1[j], vi1[j], vi1[i]))
    verts = vo0 + vo1 + vi0 + vi1
    _to_axis(verts, axis)
    return verts


# ---------------------------------------------------------------- objects
def shade(ob, sharp=40.0):
    me = ob.data
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    me.set_sharp_from_angle(angle=math.radians(sharp))
    me.update()


def make(name, bm, mat=None, parent=None, sharp=40.0, coll=WATCH, ex=None):
    """Turn a millimetre bmesh into a metre-scale object. ex = explode offset in mm."""
    bmesh.ops.scale(bm, vec=(MM, MM, MM), verts=bm.verts[:])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    collection(coll).objects.link(ob)
    if mat is not None:
        me.materials.append(mat)
    shade(ob, sharp)
    if coll == WATCH:
        ob.parent = parent or root()
    if ex is not None:
        ob["explode_mm"] = [float(v) for v in ex]
    return ob


def cutter(bm, name="cut"):
    ob = make(name, bm, coll=CUTTERS)
    ob.display_type = "WIRE"
    ob.hide_render = True
    return ob


def boolean(ob, cutters, op="DIFFERENCE", sharp=40.0):
    """Apply EXACT booleans and delete the cutters."""
    if not isinstance(cutters, (list, tuple)):
        cutters = [cutters]
    for c in cutters:
        m = ob.modifiers.new("bool", "BOOLEAN")
        m.operation = op
        m.solver = "EXACT"
        m.object = c
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    old = ob.data
    name = old.name
    ob.modifiers.clear()
    ob.data = me
    bpy.data.meshes.remove(old)
    me.name = name
    for c in cutters:
        d = c.data
        bpy.data.objects.remove(c)
        bpy.data.meshes.remove(d)
    # tidy the result: weld coincident verts, drop the cutter's empty material slot
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-7)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=1e-8)
    for f in bm.faces:
        f.material_index = 0
    bm.to_mesh(me)
    bm.free()
    while len(me.materials) > 1:
        me.materials.pop(index=len(me.materials) - 1)
    shade(ob, sharp)
    return ob


def add_explode_drivers():
    """delta_location = explode * explode_mm, on every object that has explode_mm."""
    r = root()
    for ob in collection().all_objects:
        vec = ob.get("explode_mm")
        if vec is None:
            continue
        for i in range(3):
            if abs(vec[i]) < 1e-9:
                continue
            fc = ob.driver_add("delta_location", i)
            d = fc.driver
            d.type = "SCRIPTED"
            v = d.variables.new()
            v.name = "e"
            v.type = "SINGLE_PROP"
            v.targets[0].id = r
            v.targets[0].data_path = '["explode"]'
            d.expression = "e*%.6f" % (vec[i] * MM)


def set_explode(value):
    r = root()
    r["explode"] = float(value)
    r.update_tag()
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)
    bpy.context.view_layer.update()


def planar_uv(ob, u_axis=0, v_axis=1):
    """UVs from the bounding box, 0..1 on the two given axes."""
    me = ob.data
    cos = [v.co for v in me.vertices]
    lo = [min(c[i] for c in cos) for i in range(3)]
    hi = [max(c[i] for c in cos) for i in range(3)]
    uv = me.uv_layers.new(name="UVMap")
    for loop in me.loops:
        c = me.vertices[loop.vertex_index].co
        uv.data[loop.index].uv = (
            (c[u_axis] - lo[u_axis]) / (hi[u_axis] - lo[u_axis]),
            (c[v_axis] - lo[v_axis]) / (hi[v_axis] - lo[v_axis]))
