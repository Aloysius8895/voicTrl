"""Measure real interpenetration between parts of watch.blend.

  blender -b watch.blend -P check_fit.py -- [--explode 0] [--tol 0.12]

For every pair of mesh objects whose bounding boxes overlap, counts the vertices of one
that lie inside the other deeper than --tol millimetres. Parts are sunk 0.02-0.1 mm into
what they sit on (so no faces are coplanar); anything deeper is a real clash.
"""
import argparse
import json
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import watch_lib  # noqa: E402


def world_mesh(ob, dg):
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    mw = ev.matrix_world
    verts = [mw @ v.co for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    ev.to_mesh_clear()
    return verts, polys


def inside(bvh, p):
    """Ray parity along three directions; a point is inside when the majority say so."""
    votes = 0
    for d in (Vector((0.3, 0.5, 0.81)), Vector((-0.61, 0.2, -0.77)), Vector((0.7, -0.69, 0.18))):
        hits, o = 0, p
        while True:
            loc, _, _, _ = bvh.ray_cast(o, d)
            if loc is None:
                break
            hits += 1
            o = loc + d * 1e-7
        votes += hits % 2
    return votes >= 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--explode", type=float, default=0.0)
    ap.add_argument("--tol", type=float, default=0.12)
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    watch_lib.set_explode(args.explode)
    dg = bpy.context.evaluated_depsgraph_get()
    obs = [o for o in bpy.data.collections["WATCH"].all_objects if o.type == "MESH"]
    data = {}
    for o in obs:
        v, p = world_mesh(o, dg)
        lo = Vector([min(c[i] for c in v) for i in range(3)])
        hi = Vector([max(c[i] for c in v) for i in range(3)])
        data[o.name] = (v, BVHTree.FromPolygons(v, p), lo, hi)
    tol = args.tol / 1000
    clashes, pairs = [], 0
    names = sorted(data)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            va, ba, la, ha = data[a]
            vb, bb, lb, hb = data[b]
            if any(la[k] > hb[k] or lb[k] > ha[k] for k in range(3)):
                continue
            pairs += 1
            worst = 0.0
            for verts, other in ((va, bb), (vb, ba)):
                for p in verts:
                    near = other.find_nearest(p)
                    if near[0] is None:
                        continue
                    d = near[3]
                    if d > tol and d > worst and inside(other, p):
                        worst = d
            if worst > 0:
                clashes.append({"a": a, "b": b, "depth_mm": round(worst * 1000, 3)})
    print("@@JSON@@" + json.dumps({"explode": args.explode, "objects": len(obs), "pairs_tested": pairs,
                                   "tol_mm": args.tol, "clashes": clashes}))


if __name__ == "__main__":
    main()
