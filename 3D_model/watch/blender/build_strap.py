"""Our own parts: 3D-printed cradle, pass-through nylon strap, slide buckle and keeper."""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

import spec as S
import watch_lib as L

Z_FLOOR1 = S.ZB                       # cradle floor top = case back
Z_FLOOR0 = Z_FLOOR1 - S.CR_FLOOR      # -7.6
Z_BAR1 = Z_FLOOR0 - S.STRAP_T - 0.2   # -9.0, top of the lug bars
Z_BAR0 = Z_BAR1 - 1.4                 # -10.4
Z_STRAP = Z_FLOOR0 - 0.1 - S.STRAP_T / 2   # strap centre line under the floor


def _cradle(m):
    y_in = S.W / 2 + S.CR_GAP
    y_out = y_in + S.CR_WALL
    bm = bmesh.new()
    L.fbox(bm, S.W, 2 * y_out, S.R, Z_FLOOR0, Z_FLOOR1, f=0.5, seg=10, fs=3, top=False)
    cradle = L.make("SM_cradle", bm, m["cradle"], ex=S.EX["cradle"])
    for sy in (-1, 1):
        # side wall: rounded top corners, profile in (X, Z)
        b = bmesh.new()
        x, zt, r = S.CR_WALL_X, S.CR_WALL_Z1, 3.0
        wall = [(-x, Z_FLOOR1 - 0.6), (x, Z_FLOOR1 - 0.6)]
        wall += [(x - r + r * math.cos(math.radians(a)), zt - r + r * math.sin(math.radians(a)))
                 for a in range(0, 91, 15)]
        wall += [(-x + r + r * math.cos(math.radians(a)), zt - r + r * math.sin(math.radians(a)))
                 for a in range(90, 181, 15)]
        ya, yb = sorted((sy * y_in, sy * y_out))
        L.prism(b, wall, ya, yb, "Y")
        L.boolean(cradle, L.cutter(b, "wall"), "UNION")
        # lug: two cheeks hanging under the floor and the bar the strap passes over
        b = bmesh.new()
        y0 = sy * S.LUG_Y
        for sx in (-1, 1):
            xa, xb = sorted((sx * (S.STRAP_W / 2 + 0.4), sx * (S.STRAP_W / 2 + 2.0)))
            L.box(b, xa, xb, y0 - 1.5, y0 + 1.5, Z_BAR0, Z_FLOOR0 + 0.3)
        L.boolean(cradle, L.cutter(b, "cheeks"), "UNION")
        b = bmesh.new()
        L.prism(b, L.rrect(2.2, Z_BAR1 - Z_BAR0, 0.5, 4, y0, (Z_BAR0 + Z_BAR1) / 2),
                -(S.STRAP_W / 2 + 1.0), S.STRAP_W / 2 + 1.0, "X")
        L.boolean(cradle, L.cutter(b, "bar"), "UNION")
    return cradle


def _path(b, flat=25.5, rc=5.0, n=2.4):
    """Closed strap centre line in (Y, Z): flat under the cradle, round over the wrist."""
    zt = Z_STRAP
    pts = [(-flat + 2 * flat * i / 24, zt) for i in range(24)]
    pts += [(flat + rc * math.cos(math.radians(90 - 90 * i / 8)),
             zt - rc + rc * math.sin(math.radians(90 - 90 * i / 8))) for i in range(8)]
    a, z1 = flat + rc, zt - rc
    for i in range(96):
        c, s = math.cos(math.pi * i / 96), math.sin(math.pi * i / 96)
        pts.append((a * math.copysign(abs(c) ** (2 / n), c), z1 - b * abs(s) ** (2 / n)))
    pts += [(-flat + rc * math.cos(math.radians(180 - 90 * i / 8)),
             zt - rc + rc * math.sin(math.radians(180 - 90 * i / 8))) for i in range(8)]
    return pts


def _length(pts):
    return sum(math.dist(p, q) for p, q in zip(pts, pts[1:] + pts[:1]))


def _resample(pts, count):
    """Evenly spaced points round a closed polyline."""
    total = _length(pts)
    step, out, acc = total / count, [], 0.0
    target = 0.0
    for p, q in zip(pts, pts[1:] + pts[:1]):
        seg = math.dist(p, q)
        while target <= acc + seg and len(out) < count:
            t = (target - acc) / seg
            out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
            target += step
        acc += seg
    return out, total


def _frames(pts):
    """Per point: tangent and outward normal, both in (Y, Z)."""
    n = len(pts)
    out = []
    for i in range(n):
        (y0, z0), (y1, z1) = pts[i - 1], pts[(i + 1) % n]
        d = math.hypot(y1 - y0, z1 - z0)
        ty, tz = (y1 - y0) / d, (z1 - z0) / d
        out.append(((ty, tz), (-tz, ty)))
    return out


def _strap(m):
    # choose the depth of the loop so the inside of the strap measures the wrist
    want = S.WRIST + math.pi * S.STRAP_T
    lo, hi = 15.0, 60.0
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if _length(_path(mid)) < want else (lo, mid)
    pts, total = _resample(_path((lo + hi) / 2), 360)
    frames = _frames(pts)

    hw, ht, c = S.STRAP_W / 2, S.STRAP_T / 2, 0.25
    prof = [(-hw + c, -ht), (hw - c, -ht), (hw, -ht + c), (hw, ht - c),
            (hw - c, ht), (-hw + c, ht), (-hw, ht - c), (-hw, -ht + c)]
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    rings = []
    for (y, z), (_, (ny, nz)) in zip(pts, frames):
        rings.append([bm.verts.new((x, y + d * ny, z + d * nz)) for x, d in prof])
    step, k = total / len(pts), len(prof)
    for i in range(len(rings)):
        a, b = rings[i], rings[(i + 1) % len(rings)]
        for j in range(k):
            j2 = (j + 1) % k
            f = bm.faces.new((a[j], a[j2], b[j2], b[j]))
            us = (i * step, i * step, (i + 1) * step, (i + 1) * step)
            vs = (prof[j][0], prof[j2][0], prof[j2][0], prof[j][0])
            for loop, u, v in zip(f.loops, us, vs):
                loop[uvl].uv = (u, v)
    strap = L.make("SM_strap", bm, m["strap"], sharp=50, ex=S.EX["strap"])
    return strap, pts, frames, total


def _loop_part(name, mat, parent, pts, frames, index, outer, inner, length, r):
    """A flat ring round the strap at path point `index`, `length` long along it."""
    (y, z), ((ty, tz), (ny, nz)) = pts[index], frames[index]
    bm = bmesh.new()
    L.ring_prism(bm, L.rrect(outer[0], outer[1], r, 6), L.rrect(inner[0], inner[1], 0.4, 6),
                 -length / 2, length / 2)
    mw = Matrix(((1, 0, 0, 0), (0, ny, ty, y), (0, nz, tz, z), (0, 0, 0, 1)))   # local (x, d, along)
    bmesh.ops.transform(bm, matrix=mw, verts=bm.verts[:])
    return L.make(name, bm, mat, parent=parent)


def build(m):
    cradle = _cradle(m)
    strap, pts, frames, total = _strap(m)
    n = len(pts)
    inner = (S.STRAP_W + 0.7, S.STRAP_T + 0.7)
    _loop_part("SM_buckle", m["buckle"], strap, pts, frames, int(n * 0.50),
               (S.STRAP_W + 5.0, S.STRAP_T + 4.2), inner, 5.0, 1.6)
    _loop_part("SM_strap_keeper", m["strap"], strap, pts, frames, int(n * 0.44),
               (S.STRAP_W + 2.6, S.STRAP_T + 2.4), inner, 4.0, 1.0)
    strap["centre_line_mm"] = total
    return cradle, strap
