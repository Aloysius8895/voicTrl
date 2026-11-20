"""Dimensions of the voicTrl watch, in millimetres. Single source for every build script.

Source tags used in the comments:
  [official]  Espressif ESP-Mosaico V1.2 user guide or the display datasheet
  [photo]     measured from the official product / board photos (pic/ref)
  [assumed]   chosen so the parts fit; not verified against a real unit
"""

# ---- module case
W = 46.0            # outer width, both ways: 43.3 glass [official] + 1.35 rim each side [photo]
T = 12.0            # thickness [photo: side face scaled by the 2.54 mm header pitch]
R = 6.5             # outer corner radius [photo]
FILLET = 0.9        # edge rounding front and back [photo]
WALL = 1.5          # side wall [assumed]
ZF, ZB = T / 2, -T / 2
CAVITY = W - 2 * WALL   # 43.0

# ---- display stack [official: H0216F002AMT004 datasheet]
GLASS = 43.3        # cover glass outline, square
GLASS_T = 0.7
GLASS_R = 5.15      # corner radius [photo]
VA = 38.99          # touch panel viewing area
AA = 38.39          # active area
DISP_X, DISP_Y, DISP_T = 41.09, 40.29, 0.8   # AMOLED module outline
Z_GLASS1 = ZF - 0.05            # glass top, 0.05 below the rim [assumed]
Z_GLASS0 = Z_GLASS1 - GLASS_T   # 5.25
Z_DISP1 = Z_GLASS0 - 0.18       # 5.07, OCA 0.18 [official]
Z_DISP0 = Z_DISP1 - DISP_T      # 4.27
Z_LEDGE1 = Z_DISP1 - 0.02       # 5.05, top of the flange the glass sits over
Z_LEDGE0 = 4.20                 # underside of that flange [assumed]

# ---- boards. Stack heights are [assumed]; the parts on them are [official] / [photo]
BOARD_GAP = 5.6     # between the boards: battery 5.0 [official 501220] + clearance
PCB_T = 1.0
Z_BASE0 = -5.1      # BaseBoard back face = the back of the watch, 0.9 below the rim [photo: slightly recessed]
Z_BASE1 = Z_BASE0 + PCB_T        # -4.1
Z_CORE0 = Z_BASE1 + BOARD_GAP    # 1.5  CoreBoard back face
Z_CORE1 = Z_CORE0 + PCB_T        # 2.5  CoreBoard front face
CORE = 41.0         # CoreBoard outline, square [photo]
BASE = 42.6         # BaseBoard outline, square [photo]
PAD_X, PAD_PITCH = -9.4, 2.9     # 7 gold expansion pads on the back [photo: product back view]
SCREW_X, SCREW_Y = 17.5, 17.5    # the four screws [photo: product back view]
EMBED = 0.02        # parts sink this far into the board so no faces are coplanar

# ---- +X edge: Function button and speaker slots [photo]
FN_Y, FN_Z = -11.5, 1.2
FN_W, FN_H = 9.5, 4.0
FN_SW_Y = -12.6                 # the tact switch behind the Function cap [photo]
SLOT_N, SLOT_PITCH, SLOT_Y, SLOT_Z = 6, 2.4, 2.5, -2.0
SLOT_W, SLOT_L, SLOT_TILT = 0.8, 3.6, 45.0

# ---- -X edge: USB-C, POWER (-Y), BOOT (+Y), small holes [photo]
USB_Z = Z_CORE0 - 1.62           # receptacle centre; shell is 8.94 x 3.26 [USB-C standard]
PB_Y, PB_Z = 12.9, 0.5           # POWER at -PB_Y, BOOT at +PB_Y
PB_W, PB_H = 8.0, 2.6
HOLE_Z = 2.9                     # row of five small holes (charge light, microphone)

# ---- +-Y edges: 2 x 10 header, 2.54 mm pitch [official]
PITCH = 2.54
HDR_ROWS_Z = (Z_BASE1 + 1.27, Z_BASE1 + 1.27 + PITCH)   # -2.83, -0.29

# ---- cradle, strap, buckle [all assumed: our own design]
CR_GAP = 0.15       # side clearance between the case and the cradle walls
CR_WALL = 1.8
CR_FLOOR = 1.6
CR_WALL_X = 15.0    # walls span x = +-15
CR_WALL_Z1 = 4.8
STRAP_W, STRAP_T = 22.0, 1.2
WRIST = 165.0       # wrist circumference the strap is closed to
LUG_Y = 20.5        # the two bars the strap passes over, under the cradle floor

# ---- explode offsets at explode = 1 (mm). Children inherit their parent's offset.
EX = {
    "glass": (0, 0, 52), "display": (0, 0, 38), "case": (0, 0, 22),
    "btn_fn": (8, 0, 0), "btn_pb": (-8, 0, 0), "label_L": (0, 6, 0), "label_R": (0, -6, 0),
    "core": (0, 0, 0), "base": (0, 0, -20), "screw": (0, 0, -38),
    "cradle": (0, 0, -56), "strap": (0, 0, -76),
}
