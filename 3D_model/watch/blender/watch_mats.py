"""Materials. Albedo and metal values follow blender-pbr-materials/references/pbr-values.md."""
import math
import sys

import bpy

SKILL_PBR = "C:/maven/Hackathon_map/rendering/blender-skills/skills/blender-pbr-materials/scripts"
ORANGE = (255, 90, 31)      # #FF5A1F
CHARCOAL = (28, 23, 20)     # #1C1714


def lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgb(r, g, b):
    return (lin(r), lin(g), lin(b), 1.0)


def _tree(m):
    if m.node_tree is None or not m.node_tree.nodes:
        try:
            m.use_nodes = True
        except Exception:
            pass
    nt = m.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None) \
            or nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(bsdf.outputs[0], out.inputs[0])
    return nt, bsdf


def plain(name, base, rough, metallic=0.0, **sockets):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    nt, b = _tree(m)
    b.inputs["Base Color"].default_value = base
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metallic
    for k, v in sockets.items():
        b.inputs[k].default_value = v
    m.diffuse_color = base
    return m


def _math(nt, op, a, b=None, c=None):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    for i, v in enumerate((a, b, c)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = v
        else:
            nt.links.new(v, n.inputs[i])
    return n.outputs[0]


def _bump(nt, bsdf, height, distance, strength=1.0):
    n = nt.nodes.new("ShaderNodeBump")
    n.inputs["Strength"].default_value = strength
    n.inputs["Distance"].default_value = distance
    nt.links.new(height, n.inputs["Height"])
    nt.links.new(n.outputs["Normal"], bsdf.inputs["Normal"])


def preset(name, kind):
    """Measured metal from the blender-pbr-materials skill script."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    if SKILL_PBR not in sys.path:
        sys.path.insert(0, SKILL_PBR)
    import build_pbr_material
    build_pbr_material.run(name=name, preset=kind)
    return bpy.data.materials[name]


def build():
    m = {}
    m["case"] = plain("M_case_white_abs", rgb(228, 228, 226), 0.28,
                      **{"Coat Weight": 0.25, "Coat Roughness": 0.1})
    m["btn_white"] = plain("M_button_white", rgb(226, 226, 224), 0.42)
    m["btn_orange"] = plain("M_button_orange", rgb(*ORANGE), 0.38)
    m["glass"] = plain("M_cover_glass", (1, 1, 1, 1), 0.0,
                       **{"Transmission Weight": 1.0, "IOR": 1.5})
    m["ink"] = plain("M_glass_ink_black", rgb(5, 5, 6), 0.15)
    m["display"] = plain("M_display_black", rgb(6, 6, 7), 0.15)
    m["pcb"] = plain("M_pcb_black", rgb(20, 21, 21), 0.7, **{"Specular IOR Level": 0.2})
    m["ic"] = plain("M_ic_black", rgb(24, 24, 25), 0.5)
    m["plastic"] = plain("M_plastic_black", rgb(30, 30, 31), 0.45)
    m["passive"] = plain("M_passive_tan", rgb(150, 120, 85), 0.55)
    m["ceramic"] = plain("M_ceramic_white", rgb(226, 222, 208), 0.5)
    m["jst"] = plain("M_connector_white", rgb(226, 223, 212), 0.5)
    m["kapton"] = plain("M_battery_kapton", rgb(205, 140, 40), 0.25,
                        **{"Coat Weight": 0.5, "Coat Roughness": 0.08})
    m["amber"] = plain("M_switch_amber", rgb(200, 140, 60), 0.4)
    m["screw"] = plain("M_screw_black_oxide", rgb(32, 32, 34), 0.35)
    m["buckle"] = plain("M_buckle_black", rgb(26, 26, 28), 0.42)
    m["label"] = plain("M_label_white", rgb(236, 236, 232), 0.6)
    m["silk"] = plain("M_silkscreen_white", rgb(236, 236, 234), 0.55)
    m["logo_red"] = plain("M_mosaico_red", rgb(228, 52, 40), 0.5)
    m["solder"] = plain("M_solder_tin", (0.75, 0.75, 0.74, 1.0), 0.35, 1.0)
    m["gold"] = preset("M_gold", "gold")
    m["brass"] = preset("M_brass", "brass")
    m["steel"] = preset("M_steel", "iron")

    # cradle: charcoal PLA with 0.2 mm print layers along Z
    c = plain("M_cradle_pla", rgb(*CHARCOAL), 0.6)
    nt, b = _tree(c)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    layers = _math(nt, "SINE", _math(nt, "MULTIPLY", sep.outputs["Z"], 2 * math.pi / 0.0002))
    _bump(nt, b, layers, 0.00004, 0.8)
    m["cradle"] = c

    # strap: orange nylon webbing; UVs are in millimetres (u along, v across)
    s = plain("M_strap_nylon", rgb(*ORANGE), 0.85, **{"Sheen Weight": 0.12})
    nt, b = _tree(s)
    uv = nt.nodes.new("ShaderNodeUVMap")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(uv.outputs["UV"], sep.inputs[0])
    u, v = sep.outputs["X"], sep.outputs["Y"]
    diag = _math(nt, "ADD", _math(nt, "MULTIPLY", u, 2 * math.pi / 1.4),
                 _math(nt, "MULTIPLY", _math(nt, "ABSOLUTE", v), 2 * math.pi / 2.2))
    ribs = _math(nt, "MULTIPLY", _math(nt, "SINE", diag),
                 _math(nt, "SINE", _math(nt, "MULTIPLY", v, 2 * math.pi / 0.9)))
    _bump(nt, b, ribs, 0.00012, 1.0)
    m["strap"] = s

    # pin label: white sticker with a dark rule every 2.54 mm
    lab = m["label"]
    nt, b = _tree(lab)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    cell = _math(nt, "FRACT", _math(nt, "ADD", _math(nt, "MULTIPLY", sep.outputs["X"], 1 / 0.00254), 0.5))
    line = _math(nt, "LESS_THAN", cell, 0.07)
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = rgb(236, 236, 232)
    mix.inputs["B"].default_value = rgb(25, 25, 25)
    nt.links.new(line, mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])

    m["screen"] = screen()
    return m


def screen(bars=12, phase=0.0):
    """Black screen with an orange voice waveform. UV 0..1 over the active area;
    u runs along +X (left to right for the wearer), v along +Y. The 'phase'
    value node shifts the bar heights so the waveform can be animated later."""
    mat = bpy.data.materials.get("M_screen_waveform") or bpy.data.materials.new("M_screen_waveform")
    nt, b = _tree(mat)
    b.inputs["Base Color"].default_value = rgb(4, 4, 5)
    b.inputs["Roughness"].default_value = 0.15
    uv = nt.nodes.new("ShaderNodeUVMap")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(uv.outputs["UV"], sep.inputs[0])
    u, v = sep.outputs["X"], sep.outputs["Y"]
    ph = nt.nodes.new("ShaderNodeValue")
    ph.name = ph.label = "phase"
    ph.outputs[0].default_value = phase

    span, x0 = 0.60, 0.20                  # bars cover u = 0.20 .. 0.80
    cell = span / bars                     # one bar slot, in UV units
    r = cell * 0.30                        # bar half-width = cap radius
    t = _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", u, x0), bars / span)
    idx = _math(nt, "FLOOR", t)
    dx = _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", _math(nt, "FRACT", t), 0.5), cell)
    # half-height per bar: two sines of the index, shaped by a centre-weighted envelope
    wob = _math(nt, "ADD",
                _math(nt, "MULTIPLY", _math(nt, "SINE", _math(nt, "ADD", _math(nt, "MULTIPLY", idx, 1.9), ph.outputs[0])), 0.5),
                _math(nt, "MULTIPLY", _math(nt, "SINE", _math(nt, "ADD", _math(nt, "MULTIPLY", idx, 0.83), 1.3)), 0.5))
    env = _math(nt, "SINE", _math(nt, "MULTIPLY", _math(nt, "ADD", idx, 0.5), math.pi / bars))
    half = _math(nt, "ADD", 0.03, _math(nt, "MULTIPLY", _math(nt, "MULTIPLY", _math(nt, "ABSOLUTE", wob), env), 0.20))
    dy = _math(nt, "MAXIMUM", _math(nt, "SUBTRACT", _math(nt, "ABSOLUTE", _math(nt, "SUBTRACT", v, 0.5)),
                                    _math(nt, "SUBTRACT", half, r)), 0.0)
    dist = _math(nt, "SQRT", _math(nt, "ADD", _math(nt, "MULTIPLY", dx, dx), _math(nt, "MULTIPLY", dy, dy)))
    inside = _math(nt, "LESS_THAN", dist, r)
    in_span = _math(nt, "MULTIPLY", _math(nt, "GREATER_THAN", t, 0.0), _math(nt, "LESS_THAN", t, float(bars)))
    mask = _math(nt, "MULTIPLY", inside, in_span)
    b.inputs["Emission Color"].default_value = rgb(*ORANGE)
    nt.links.new(_math(nt, "MULTIPLY", mask, 8.0), b.inputs["Emission Strength"])
    return mat
