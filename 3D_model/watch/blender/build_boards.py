"""CoreBoard, BaseBoard, standoffs and screws.

Part positions come from the official board photos (pic/ref and the user guide);
heights and the exact stacking are assumptions (see spec.py).
"""
import math
import random

import bmesh

import spec as S
import watch_lib as L

E = S.EMBED


def _pcb(name, size, r, z0, z1, mat, ex):
    bm = bmesh.new()
    L.prism(bm, L.rrect(size, size, r, 8), z0, z1)
    pcb = L.make(name, bm, mat, ex=ex)
    b = bmesh.new()
    for sx in (-1, 1):
        for sy in (-1, 1):
            L.cyl(b, 1.1, z0 - 0.3, z1 + 0.3, sx * S.SCREW_X, sy * S.SCREW_Y, 20)
    L.boolean(pcb, L.cutter(b, "holes"))
    return pcb


class Side:
    """Places boxes on one face of a board. up = +1 for the front face, -1 for the back."""

    def __init__(self, z, up):
        self.z, self.up, self.used = z, up, []

    def span(self, h):
        return tuple(sorted((self.z - self.up * E, self.z + self.up * h)))

    def part(self, bm, cx, cy, sx, sy, h, rot=0.0, r=0.0):
        pts = L.rrect(sx, sy, r, 3, cx, cy) if r else L.rect(cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2)
        if rot:
            pts = L.rot2(pts, rot, cx, cy)
        L.prism(bm, pts, *self.span(h))
        d = max(sx, sy) * (0.72 if rot else 0.5) + 0.4
        self.used.append((cx - d, cx + d, cy - d, cy + d))

    def free(self, x, y, m=0.5):
        return all(not (a - m < x < b + m and c - m < y < d + m) for a, b, c, d in self.used)


def _core(m):
    pcb = _pcb("SM_core_pcb", S.CORE, 3.5, S.Z_CORE0, S.Z_CORE1, m["pcb"], S.EX["core"])
    front, back = Side(S.Z_CORE1, 1), Side(S.Z_CORE0, -1)
    for sx in (-1, 1):                       # keep the bosses and standoffs clear
        for sy in (-1, 1):
            for side in (front, back):
                side.used.append((sx * S.SCREW_X - 2.4, sx * S.SCREW_X + 2.4,
                                  sy * S.SCREW_Y - 2.4, sy * S.SCREW_Y + 2.6))

    # ---- front face (towards the display)
    ics = bmesh.new()
    front.part(ics, 9.9, 8.7, 8.5, 8.5, 0.9, rot=45)          # ESP32-S31
    front.part(ics, 1.0, 14.6, 5.7, 7.7, 0.8)                 # flash
    front.part(ics, 1.0, 5.5, 5.7, 6.0, 0.8)                  # PSRAM
    front.part(ics, 0.2, 0.2, 3.0, 3.0, 0.8)                  # IMU
    front.part(ics, 8.4, -16.8, 4.0, 4.0, 1.3, r=0.6)         # 2R2 inductor
    for x in (4.2, -3.0, -7.9):
        front.part(ics, x, -17.5, 3.0, 3.0, 0.9)
    front.part(ics, -5.3, 13.1, 3.5, 3.5, 0.8)
    front.part(ics, -11.1, 14.4, 4.0, 4.0, 0.8)
    for y in (4.0, 0.5, -3.0, -6.5):
        front.part(ics, -10.5, y, 2.0, 3.0, 1.0)
    front.part(ics, -17.0, 7.2, 4.5, 5.0, 1.2)
    L.make("SM_core_ics_front", ics, m["ic"], parent=pcb)

    bm = bmesh.new()
    front.part(bm, 18.8, -1.0, 1.6, 3.2, 1.1)                 # ceramic antenna
    front.part(bm, -19.6, -0.2, 0.8, 1.6, 0.6)                # charge LED, at the -X edge
    L.make("SM_core_antenna_led", bm, m["ceramic"], parent=pcb)

    bm = bmesh.new()
    front.part(bm, -10.1, -11.9, 2.2, 6.5, 1.0)               # display connector
    L.make("SM_core_display_conn", bm, m["plastic"], parent=pcb)

    # ---- back face (towards the BaseBoard)
    sw, pl = bmesh.new(), bmesh.new()
    for x, y, sx in ((17.2, S.FN_SW_Y, 1), (-17.2, -S.PB_Y, -1), (-17.2, S.PB_Y, -1)):
        back.part(sw, x, y, 3.5, 5.5, 1.8)                    # side-push tact switch
        x0, x1 = sorted((x + sx * 1.7, x + sx * 2.7))
        L.box(pl, x0, x1, y - 1.1, y + 1.1, S.Z_CORE0 - 1.5, S.Z_CORE0 - 0.3)
    back.part(sw, -17.9, 6.2, 1.85, 2.75, 0.9)                # MEMS microphone can
    L.make("SM_core_switches_mic", sw, m["steel"], parent=pcb)
    L.make("SM_core_switch_plungers", pl, m["amber"], parent=pcb)

    # USB-C receptacle: steel shell, black tongue
    shell = bmesh.new()
    L.ring_prism(shell, L.rrect(8.94, 3.26, 1.6, 6, 0.0, S.USB_Z), L.rrect(8.34, 2.66, 1.3, 6, 0.0, S.USB_Z),
                 -22.6, -15.3, "X")
    L.prism(shell, L.rrect(8.6, 2.9, 1.4, 6, 0.0, S.USB_Z), -16.0, -15.4, "X")   # closed back
    L.make("SM_core_usbc_shell", shell, m["steel"], parent=pcb)
    back.used.append((-22.6, -15.0, -4.6, 4.6))
    bm = bmesh.new()
    L.prism(bm, L.rect(-3.35, 3.35, S.USB_Z - 0.35, S.USB_Z + 0.35), -22.0, -15.95, "X")
    L.make("SM_core_usbc_tongue", bm, m["plastic"], parent=pcb)

    # board-to-board plug: body on the board, rib that drops into the socket
    bm = bmesh.new()
    zmid = S.Z_CORE0 - S.BOARD_GAP / 2
    L.prism(bm, L.rrect(4.5, 17.6, 0.3, 3, 6.55, 0.0), zmid, S.Z_CORE0 + E)
    L.prism(bm, L.rect(5.15, 7.95, -8.1, 8.1), zmid - 1.1, zmid + 0.05)
    L.make("SM_core_btb_plug", bm, m["plastic"], parent=pcb)
    back.used.append((4.0, 9.1, -9.1, 9.1))

    # vibration motor: a small cylinder lying along Y, with its eccentric weight
    bm = bmesh.new()
    zc = S.Z_CORE0 - 1.7 + E
    L.cyl(bm, 1.7, -3.0, 4.0, -10.3, zc, 20, "Y")           # profile is (X, Z)
    L.make("SM_core_motor", bm, m["steel"], parent=pcb)
    bm = bmesh.new()
    half = [(-10.3 + 1.45 * math.cos(math.radians(a)), zc + 1.45 * math.sin(math.radians(a)))
            for a in range(180, 361, 20)]                    # lower half disc
    L.prism(bm, half, -5.4, -3.3, "Y")
    L.cyl(bm, 0.4, -3.35, -2.9, -10.3, zc, 10, "Y")
    L.make("SM_core_motor_weight", bm, m["brass"], parent=pcb)
    back.used.append((-12.3, -8.3, -5.6, 4.2))

    # gold on the back face: rings round the standoffs, and the row of test pads
    bm = bmesh.new()
    for sx in (-1, 1):
        for sy in (-1, 1):
            L.ring_prism(bm, L.circle(1.8, 20, sx * S.SCREW_X, sy * S.SCREW_Y),
                         L.circle(1.68, 20, sx * S.SCREW_X, sy * S.SCREW_Y), S.Z_CORE0 - 0.06, S.Z_CORE0 + E)
    for i in range(6):
        L.cyl(bm, 0.5, S.Z_CORE0 - 0.06, S.Z_CORE0 + E, 13.4, 0.8 + i * 1.6, 12)
    back.used.append((12.4, 14.4, 0.0, 9.6))
    L.make("SM_core_gold", bm, m["gold"], parent=pcb)

    # small passives scattered over the free area of both faces
    rnd = random.Random(31)
    bm = bmesh.new()
    for side, count in ((front, 70), (back, 40)):
        placed = 0
        while placed < count:
            x, y = rnd.uniform(-18.5, 18.5), rnd.uniform(-18.5, 18.5)
            if not side.free(x, y):
                continue
            w, d = (1.0, 0.5) if rnd.random() < 0.5 else (0.5, 1.0)
            side.part(bm, x, y, w, d, 0.45)
            placed += 1
    L.make("SM_core_passives", bm, m["passive"], parent=pcb)
    return pcb


def _base(m):
    pcb = _pcb("SM_base_pcb", S.BASE, 4.8, S.Z_BASE0, S.Z_BASE1, m["pcb"], S.EX["base"])
    front = Side(S.Z_BASE1, 1)
    z0 = S.Z_BASE1 - E

    # speaker: housing with an oval sound opening on top, next to the +X slots
    bm = bmesh.new()
    L.fbox(bm, 11.0, 19.6, 1.0, z0, S.Z_BASE1 + 3.8, f=0.4, cx=15.0, cy=0.0, seg=4, fs=2, bottom=False)
    spk = L.make("SM_base_speaker", bm, m["plastic"], parent=pcb)
    b = bmesh.new()
    L.prism(b, L.rrect(5.5, 13.0, 2.7, 8, 15.0, 0.0), S.Z_BASE1 + 3.2, S.Z_BASE1 + 4.2)
    L.boolean(spk, L.cutter(b, "port"))

    # board-to-board socket with a trench for the plug's rib
    zmid = S.Z_CORE0 - S.BOARD_GAP / 2
    bm = bmesh.new()
    L.prism(bm, L.rrect(4.5, 17.6, 0.3, 3, 6.55, 0.0), z0, zmid)
    btb = L.make("SM_base_btb_socket", bm, m["plastic"], parent=pcb)
    b = bmesh.new()
    L.prism(b, L.rect(5.05, 8.05, -8.2, 8.2), zmid - 1.2, zmid + 0.3)
    L.boolean(btb, L.cutter(b, "trench"))
    bm = bmesh.new()   # the 60 contact tails, 0.5 mm pitch, 30 a side
    for i in range(30):
        y = (i - 14.5) * 0.5
        for x in (4.05, 9.05):
            L.box(bm, x - 0.3, x + 0.3, y - 0.12, y + 0.12, z0, S.Z_BASE1 + 0.15)
    L.make("SM_base_btb_tails", bm, m["gold"], parent=pcb)

    # 501220 Li-ion cell, 65 mAh, wrapped in amber tape
    bm = bmesh.new()
    L.fbox(bm, 12.0, 20.0, 1.5, z0, S.Z_BASE1 + 5.0, f=0.8, cx=-2.3, cy=0.0, seg=5, fs=3)
    L.make("SM_base_battery", bm, m["kapton"], parent=pcb)

    # right-angle 2 x 10 sockets: bodies at the +-Y edges, pins bent down into the board
    pins = bmesh.new()
    for sy, name in ((1, "SM_base_header_L"), (-1, "SM_base_header_R")):
        bm = bmesh.new()
        ya, yb = sorted((sy * 15.0, sy * 21.4))
        L.box(bm, -12.9, 12.9, ya, yb, z0, S.Z_BASE1 + 5.08)
        hdr = L.make(name, bm, m["plastic"], parent=pcb)
        b = bmesh.new()
        ya, yb = sorted((sy * 16.5, sy * 21.8))
        for z in S.HDR_ROWS_Z:
            for i in range(10):
                x = (i - 4.5) * S.PITCH
                L.prism(b, L.rect(x - 0.4, x + 0.4, z - 0.4, z + 0.4), ya, yb, "Y")
        L.boolean(hdr, L.cutter(b, "sockets"))
        for z, yh in zip(S.HDR_ROWS_Z, (13.9, 11.2)):      # lower row -> outer holes
            for i in range(10):
                x = (i - 4.5) * S.PITCH
                ya, yb = sorted((sy * (yh - 0.25), sy * 15.05))
                L.box(pins, x - 0.25, x + 0.25, ya, yb, z - 0.25, z + 0.25)
                L.cyl(pins, 0.3, z0, z + 0.1, x, sy * yh, 8)      # ends inside the bar, 0.15 below its top
    L.make("SM_base_header_pins", pins, m["solder"], parent=pcb)

    bm = bmesh.new()   # battery and speaker connectors
    for sy in (-1, 1):
        L.fbox(bm, 3.5, 4.5, 0.3, z0, S.Z_BASE1 + 3.0, f=0.2, cx=-15.1, cy=sy * 12.4, seg=2, fs=2, bottom=False)
    L.make("SM_base_connectors", bm, m["jst"], parent=pcb)

    bm = bmesh.new()   # TLV62569 regulator, its inductor, and the row of parts at the -X edge
    front.part(bm, -12.5, 2.2, 1.6, 2.9, 1.0)
    front.part(bm, -12.5, -2.6, 2.0, 2.5, 1.0, r=0.3)
    L.make("SM_base_ics", bm, m["ic"], parent=pcb)
    bm = bmesh.new()
    for i in range(6):
        front.part(bm, -19.5, (i - 2.5) * 3.4, 0.8, 1.6, 0.6)
    L.make("SM_base_edge_parts", bm, m["ceramic"], parent=pcb)

    # gold on the back: the 7 expansion pads (GND BOOT RST RX TX 5V GND)
    bm = bmesh.new()
    zb0, zb1 = S.Z_BASE0 - 0.06, S.Z_BASE0 + E
    for i in range(7):
        L.prism(bm, L.rrect(3.0, 2.3, 0.2, 2, S.PAD_X, (i - 3) * S.PAD_PITCH), zb0, zb1)
    L.make("SM_base_gold", bm, m["gold"], parent=pcb)

    # brass standoffs between the two boards
    bm = bmesh.new()
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * S.SCREW_X, sy * S.SCREW_Y
            L.ring_prism(bm, L.circle(1.6, 20, x, y), L.circle(1.1, 20, x, y), S.Z_BASE1, S.Z_CORE0)
    L.make("SM_standoffs", bm, m["brass"], parent=pcb)
    return pcb


def _screws(m):
    """Four black cross-head screws through the BaseBoard corners. One mesh, four objects."""
    zh0, zh1, tip = S.Z_BASE0 - 0.8, S.Z_BASE0, 3.9
    bm = bmesh.new()
    L.loft(bm, [(L.circle(1.55, 20), zh0), (L.circle(1.8, 20), zh0 + 0.25), (L.circle(1.8, 20), zh1),
                (L.circle(0.9, 20), zh1), (L.circle(0.9, 20), tip - 0.4), (L.circle(0.5, 20), tip)])
    first = L.make("SM_screw_1", bm, m["screw"], ex=S.EX["screw"])
    for cut in (L.rect(-1.15, 1.15, -0.22, 0.22), L.rect(-0.22, 0.22, -1.15, 1.15)):
        b = bmesh.new()
        L.prism(b, cut, zh0 - 0.2, zh0 + 0.45)
        L.boolean(first, L.cutter(b, "cross"))
    spots = [(sx * S.SCREW_X, sy * S.SCREW_Y) for sx in (-1, 1) for sy in (-1, 1)]
    first.location = (spots[0][0] * L.MM, spots[0][1] * L.MM, 0.0)
    for i, (x, y) in enumerate(spots[1:], 2):
        ob = first.copy()
        ob.name = "SM_screw_%d" % i
        ob.location = (x * L.MM, y * L.MM, 0.0)
        L.collection().objects.link(ob)


def build(m):
    _core(m)
    _base(m)
    _screws(m)
