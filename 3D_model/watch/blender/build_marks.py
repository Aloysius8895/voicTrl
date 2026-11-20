"""Markings on the back of the BaseBoard, as in the official product back photo:
the red Mosaico mark, "ESP-MOSAICO", "Powered by Espressif", and the seven pad names.

Seen from the back with the Function-button edge up, text reads along +Y and its
top points to +X. Everything is raised 0.06 mm and sunk 0.02 mm into the board.
The QR code on the real unit is left out: it could not be read from the photo.
"""
import math
import os

import bmesh
import bpy

import spec as S
import watch_lib as L

FONTS = r"C:\Windows\Fonts"
THICK = 0.08                    # total thickness of a marking, mm
PAD_NAMES = ("GND", "BOOT", "RST", "RX", "TX", "5V", "GND")


def _font(filename):
    path = os.path.join(FONTS, filename)
    return bpy.data.fonts.load(path, check_existing=True) if os.path.exists(path) else None


def _glyphs(body, font, size, slant=0.0, res=3, spacing=1.0):
    """Text as a closed mesh in millimetres: baseline on v = 0, left edge on u = 0. Returns (mesh, width)."""
    cu = bpy.data.curves.new("WATCH_txt", "FONT")
    cu.body, cu.size, cu.extrude, cu.resolution_u = body, size, THICK / 2, res
    cu.space_character = spacing
    if font is not None:
        cu.font = font
    ob = bpy.data.objects.new("WATCH_txt", cu)
    L.collection(L.CUTTERS).objects.link(ob)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(cu)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    for layer in list(bm.loops.layers.uv):          # the font's own UVs are of no use here
        bm.loops.layers.uv.remove(layer)
    if slant:                                       # an oblique made by shearing the upright face
        for v in bm.verts:
            v.co.x += v.co.y * slant
    u0 = min(v.co.x for v in bm.verts)
    for v in bm.verts:
        v.co.x -= u0
    width = max(v.co.x for v in bm.verts)
    bm.to_mesh(me)
    bm.free()
    return me, width


def _place(out, me, u, v, scale=1.0):
    """Append a glyph mesh to `out`, scaled in the plane, with its left end of baseline at (u, v)."""
    for vert in me.vertices:
        vert.co.x = vert.co.x * scale + u
        vert.co.y = vert.co.y * scale + v
    out.from_mesh(me)
    bpy.data.meshes.remove(me)


def _to_back(bm):
    """Layout (u, v, w) -> world (x = v, y = u, z = back face - w): a rotation, so nothing is mirrored."""
    zc = S.Z_BASE0 + S.EMBED - THICK / 2
    for vert in bm.verts:
        u, v, w = vert.co
        vert.co = (v, u, zc - w)


def build(m):
    pcb = bpy.data.objects["SM_base_pcb"]
    # Century Gothic. Its italic file has overlapping outlines, so the oblique line is sheared instead.
    bold, regular = _font("GOTHICB.TTF"), _font("GOTHIC.TTF")
    white, red = bmesh.new(), bmesh.new()

    # ---- line 1: [mark] ESP-MOSAICO, fitted to 18.5 mm wide and centred
    size, total, mark_d, gap = 3.2, 18.5, 3.3, 0.9
    esp, w_esp = _glyphs("ESP", bold, size)
    mos, w_mos = _glyphs("-MOSAICO", regular, size)
    join = 0.18
    s = (total - mark_d - gap) / (w_esp + join + w_mos)
    base_v = 13.2
    u = -total / 2
    r = mark_d / 2 * 0.86
    cu_, cv_ = u + mark_d / 2 - 0.2, base_v + 0.72 * size * s / 2
    # the Mosaico mark: three quarters of a disc, and a taller quarter set off to the upper right
    body = [(cu_, cv_)] + [(cu_ + r * math.cos(math.radians(a)), cv_ + r * math.sin(math.radians(a)))
                           for a in range(90, 361, 10)]
    L.prism(red, body, -THICK / 2, THICK / 2)
    off, rw = 0.16 * r, 1.12 * r
    wedge = [(cu_ + off, cv_ + off)] + [(cu_ + off + rw * math.cos(math.radians(a)),
                                         cv_ + off + rw * math.sin(math.radians(a))) for a in range(0, 91, 10)]
    L.prism(red, wedge, -THICK / 2, THICK / 2)
    u_text = u + mark_d + gap
    _place(white, esp, u_text, base_v, s)
    _place(white, mos, u_text + (w_esp + join) * s, base_v, s)

    # ---- line 2: Powered by Espressif, under the name
    # small print is bold with coarse curves: real silkscreen cannot hold a hairline either
    # wider letter spacing, or the sheared dot of the i runs into the hook of the f
    sub, w_sub = _glyphs("Powered by Espressif", bold, 1.5, slant=math.tan(math.radians(12)), res=1, spacing=1.15)
    s2 = 0.66 * (w_esp + join + w_mos) * s / w_sub
    _place(white, sub, u_text + 0.5, base_v - 2.0, s2)

    # ---- the seven pad names, each centred under its pad on the USB side
    for i, name in enumerate(PAD_NAMES):
        lab, w = _glyphs(name, bold, 1.0, res=1)
        s3 = min(1.0, 2.5 / w)
        _place(white, lab, (i - 3) * S.PAD_PITCH - w * s3 / 2, S.PAD_X - 2.75, s3)

    bmesh.ops.dissolve_degenerate(white, edges=white.edges[:], dist=0.002)
    # merge wall facets that are almost in one plane, so no face is smaller than the QA tolerance
    bmesh.ops.dissolve_limit(white, angle_limit=math.radians(10), verts=white.verts[:], edges=white.edges[:])
    # the merge leaves large concave caps; cut them into explicit triangles so every tool agrees on them
    bmesh.ops.triangulate(white, faces=[f for f in white.faces if len(f.verts) > 4])
    _to_back(white)
    _to_back(red)
    L.make("SM_base_marks_white", white, m["silk"], parent=pcb, sharp=30)
    L.make("SM_base_marks_red", red, m["logo_red"], parent=pcb, sharp=30)
    for f in (bold, regular):
        if f is not None and f.users == 0:
            bpy.data.fonts.remove(f)
