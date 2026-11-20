"""Module case: white shell, cover glass, display, buttons, pin labels."""
import math

import bmesh

import spec as S
import watch_lib as L


def _case(m):
    bm = bmesh.new()
    L.fbox(bm, S.W, S.W, S.R, S.ZB, S.ZF, f=S.FILLET, seg=10, fs=5)
    case = L.make("SM_case", bm, m["case"], ex=S.EX["case"])

    # cavity (open at the back), display opening, glass pocket
    cuts = []
    for size, r, z0, z1 in (
            (S.CAVITY, S.R - S.WALL, S.ZB - 0.2, S.Z_LEDGE0),
            (41.7, 1.3, S.Z_LEDGE0 - 0.1, S.Z_LEDGE1 + 0.1),      # display opening
            (S.GLASS + 0.1, S.GLASS_R + 0.05, S.Z_LEDGE1, S.ZF + 0.2)):
        b = bmesh.new()
        L.prism(b, L.rrect(size, size, r, 10), z0, z1)
        cuts.append(L.cutter(b))
    L.boolean(case, cuts)

    # four screw bosses under the flange, tied into the +-Y walls
    b = bmesh.new()
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * S.SCREW_X, sy * S.SCREW_Y
            wall = sy * (S.CAVITY / 2 + 0.2)
            # one outline: a half round facing the cavity, squared off into the wall
            a0 = 180 if sy > 0 else 0
            pts = [(x + 2.1 * math.cos(math.radians(a0 + 180 * i / 12)),
                    y + 2.1 * math.sin(math.radians(a0 + 180 * i / 12))) for i in range(13)]
            pts += [(x + sy * 2.1, wall), (x - sy * 2.1, wall)]
            L.prism(b, pts, S.Z_CORE1, S.Z_LEDGE0 + 0.05)
    bosses = L.cutter(b, "bosses")
    L.boolean(case, bosses, "UNION")

    # every opening, as one cutter of separate solids
    b = bmesh.new()
    xi, xo = S.W / 2 - S.WALL - 1.0, S.W / 2 + 0.6        # through the +-X walls
    for sx in (-1, 1):
        for sy in (-1, 1):                                  # screw holes in the bosses
            L.cyl(b, 0.95, S.Z_CORE1 - 0.1, 4.0, sx * S.SCREW_X, sy * S.SCREW_Y, 16)
    L.prism(b, L.rrect(S.FN_W + 0.2, S.FN_H + 0.2, 0.9, 6, S.FN_Y, S.FN_Z), xi, xo, "X")
    for i in range(S.SLOT_N):                               # slanted speaker slots
        y = S.SLOT_Y + (i - (S.SLOT_N - 1) / 2) * S.SLOT_PITCH
        slot = L.rot2(L.rrect(S.SLOT_W, S.SLOT_L, 0.38, 4, y, S.SLOT_Z), S.SLOT_TILT, y, S.SLOT_Z)
        L.prism(b, slot, xi, xo, "X")
    L.prism(b, L.rrect(9.3, 3.6, 1.75, 8, 0.0, S.USB_Z), -xo, -xi, "X")
    for sy in (-1, 1):
        L.prism(b, L.rrect(S.PB_W + 0.2, S.PB_H + 0.2, 1.38, 8, sy * S.PB_Y, S.PB_Z), -xo, -xi, "X")
    for i in range(5):                                      # charge light and microphone holes
        L.prism(b, L.rrect(1.4, 0.6, 0.29, 4, (i - 2) * 2.8, S.HOLE_Z), -xo, -xi, "X")
    for sy in (-1, 1):                                      # 2 x 10 header openings
        y0, y1 = sorted((sy * xi, sy * xo))
        for z in S.HDR_ROWS_Z:
            for i in range(10):
                x = (i - 4.5) * S.PITCH
                L.prism(b, L.rect(x - 0.55, x + 0.55, z - 0.55, z + 0.55), y0, y1, "Y")
    L.boolean(case, L.cutter(b, "openings"))
    return case


def _glass(m):
    g = S.GLASS
    bm = bmesh.new()
    L.loft(bm, [(L.rrect(g, g, S.GLASS_R, 10), S.Z_GLASS0),
                (L.rrect(g, g, S.GLASS_R, 10), S.Z_GLASS1 - 0.15),
                (L.rrect(g - 0.3, g - 0.3, S.GLASS_R - 0.15, 10), S.Z_GLASS1)])
    glass = L.make("SM_glass", bm, m["glass"], ex=S.EX["glass"])
    bm = bmesh.new()   # black ink border printed on the back of the glass
    L.ring_prism(bm, L.rrect(g, g, S.GLASS_R, 10), L.rrect(S.VA, S.VA, 4.0, 10),
                 S.Z_DISP1 + 0.02, S.Z_GLASS0 - 0.02)
    L.make("SM_glass_ink", bm, m["ink"], parent=glass)
    return glass


def _display(m):
    bm = bmesh.new()
    L.ring_prism(bm, L.rrect(S.DISP_X, S.DISP_Y, 1.0, 10), L.rrect(S.AA, S.AA, 4.0, 10),
                 S.Z_DISP0, S.Z_DISP1)
    disp = L.make("SM_display", bm, m["display"], ex=S.EX["display"])
    bm = bmesh.new()
    L.prism(bm, L.rrect(S.AA, S.AA, 4.0, 10), S.Z_DISP0, S.Z_DISP1)
    aa = L.make("SM_display_screen", bm, m["screen"], parent=disp)
    L.planar_uv(aa, 0, 1)
    return disp


def _cap(name, mat, w, h, r, y, z, sign, ribs, rib_len, parent, ex, nub_y, nub_z, tip):
    """A button cap on the +X (sign = 1) or -X (sign = -1) wall.
    Stem through the wall, flange behind it, ribs on the face, nub to the switch."""
    face = S.W / 2 + (0.6 if sign > 0 else 0.5)
    inner = S.W / 2 - S.WALL

    def span(a, b):
        return tuple(sorted((sign * a, sign * b)))

    bm = bmesh.new()
    L.prism(bm, L.rrect(w, h, r, 6, y, z), *span(inner - 0.05, face), "X")
    cap = L.make(name, bm, mat, parent=parent, ex=ex)
    b = bmesh.new()
    L.prism(b, L.rrect(w + 1.0, h + 1.0, r, 6, y, z), *span(inner - 0.8, inner), "X")
    L.boolean(cap, L.cutter(b, "flange"), "UNION")
    b = bmesh.new()
    for i in range(ribs):
        ry = y + (i - (ribs - 1) / 2) * 1.0
        L.prism(b, L.rect(ry - 0.22, ry + 0.22, z - rib_len / 2, z + rib_len / 2),
                *span(face - 0.1, face + 0.18), "X")
    L.prism(b, L.rect(nub_y - 1.0, nub_y + 1.0, nub_z - 0.7, nub_z + 0.7),
            *span(tip, inner - 0.75), "X")
    L.boolean(cap, L.cutter(b, "ribs"), "UNION")
    return cap


def _labels(m, case):
    y0 = S.W / 2
    for sy, key, name in ((1, "label_L", "SM_label_L"), (-1, "label_R", "SM_label_R")):
        bm = bmesh.new()
        ya, yb = sorted((sy * y0, sy * (y0 + 0.08)))
        L.prism(bm, L.rect(-12.7, 12.7, 1.6, 4.8), ya, yb, "Y")
        lab = L.make(name, bm, m["label"], parent=case, ex=S.EX[key])
        bm = bmesh.new()   # the two orange supply cells, at opposite ends on the two sides
        ya, yb = sorted((sy * (y0 + 0.06), sy * (y0 + 0.14)))
        for i in range(2):
            x = -sy * (11.43 - i * S.PITCH)
            L.prism(bm, L.rect(x - 1.05, x + 1.05, 1.9, 3.1), ya, yb, "Y")
        L.make(name + "_supply", bm, m["btn_orange"], parent=lab)


def build(m):
    case = _case(m)
    _glass(m)
    _display(m)
    _cap("SM_btn_function", m["btn_orange"], S.FN_W, S.FN_H, 0.8, S.FN_Y, S.FN_Z, 1,
         9, 3.2, case, S.EX["btn_fn"], S.FN_SW_Y, S.Z_CORE0 - 0.9, 19.9)
    for sy, name in ((-1, "SM_btn_power"), (1, "SM_btn_boot")):
        _cap(name, m["btn_white"], S.PB_W, S.PB_H, 1.3, sy * S.PB_Y, S.PB_Z, -1,
             7, 1.8, case, S.EX["btn_pb"], sy * S.PB_Y, S.Z_CORE0 - 0.9, 19.9)
    _labels(m, case)
    return case
