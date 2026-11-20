"""Run the blender-asset-qa check on a scaled-up copy of the watch (nothing is saved).

  blender -b watch.blend -P qa_scaled.py -- [--scale 10]

qa_check.py tests "point inside triangle" with a fixed 1e-9 m2 tolerance, meant for
metre-scale assets. On the 1 mm print on the back, whose faces have edges under 0.1 mm,
that tolerance reports neighbouring faces as overlapping. Scaling the model and the
distances (--eps, --tol) by the same factor checks the same shape without that artefact.
"""
import argparse
import json
import sys

import bpy
from mathutils import Matrix

sys.path.insert(0, "C:/maven/Hackathon_map/rendering/blender-skills/skills/blender-asset-qa/scripts")
import qa_check  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, default=10.0)
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    k = args.scale
    obs = [o for o in bpy.data.collections["WATCH"].all_objects if o.type == "MESH"]
    for me in {o.data for o in obs}:
        me.transform(Matrix.Scale(k, 4))
    for o in obs:
        o.location *= k
    bpy.context.view_layer.update()
    r = qa_check.run(objects=[o.name for o in obs], profile="render", eps=0.00005 * k, tol=0.002 * k)
    m = r["objects"]
    print("@@JSON@@" + json.dumps({
        "scale": k, "pass": r["pass"], "errors": r["errors"], "warnings": len(r["warnings"]),
        "objects": len(m), "tris": sum(v["tris"] for v in m.values()),
        "nonmanifold_edges": sum(v["nonmanifold_edges"] for v in m.values()),
        "boundary_edges": sum(v["boundary_edges"] for v in m.values())}))


if __name__ == "__main__":
    main()
