# voicTrl 手表：尺寸和零件表

数值的唯一来源是同目录的 `spec.py`，这里是给人看的说明。改尺寸改 `spec.py`，再重跑 `build_all.py`。

来源标签：
- **官方**：Espressif ESP-Mosaico V1.2 用户指南，或屏幕规格书 H0216F002AMT004
- **照片**：从官方产品照片和单板照片上量取（`pic/ref/`，以及用户指南里的四张单板图）
- **假设**：为了让零件装得下而定的数，没有对着实物核实

## 坐标

单位米，建模时用毫米。原点在模块中心；屏幕朝 +Z；橙色功能键那一边朝 +X；USB-C 那一边朝 −X；表带沿 ±Y 接出。

## 外形

| 量 | 数值 | 来源 |
|---|---|---|
| 外壳宽（X、Y） | 46.0 mm | 盖板玻璃 43.3（官方）+ 两侧白边各 1.35（照片） |
| 外壳厚 | 12.0 mm | 照片：侧面按 2.54 mm 排母间距换算 |
| 外圆角 / 棱边圆角 | 6.5 / 0.9 mm | 照片 |
| 盖板玻璃 | 43.3 × 43.3 × 0.7 mm | 官方 |
| 玻璃可视区 / 屏幕显示区 | 38.99 / 38.39 mm 见方 | 官方 |
| 屏幕模组 | 41.09 × 40.29 × 0.8 mm | 官方 |
| 排母 | 2 × 10，2.54 mm 间距，两侧各一 | 官方 |
| 板对板连接器 | 60 针，0.5 mm 间距 | 官方 |
| 电池 | 501220，5 × 12 × 20 mm，65 mAh | 官方（容量）、照片（型号印字） |
| USB-C 母座外壳 | 8.94 × 3.26 mm | USB-C 标准 |
| 侧壁厚 | 1.5 mm | 假设 |
| 两板间距 | 5.6 mm | 假设：电池 5.0 加余量 |
| CoreBoard / BaseBoard | 41.0 / 42.6 mm 见方，厚 1.0 | 照片（外形）、假设（厚度） |
| 四颗螺丝中心 | (±17.5, ±17.5) mm | 照片：产品背面图 |
| 托架壁厚 / 底厚 | 1.8 / 1.6 mm | 假设（我们自己的设计） |
| 表带 | 宽 22、厚 1.2 mm，内圈周长 165 mm | 假设 |

量出来的整体尺寸：模块连按键 47.5 × 46.0 × 12.0 mm；整只表（含表带圈）47.5 × 62.2 × 52.2 mm。

## 零件，按装配顺序从前到后

| # | 物体 | 是什么 | 材质 | 来源 |
|---|---|---|---|---|
| 1 | `SM_glass` + `SM_glass_ink` | 盖板玻璃，背面一圈黑色油墨边 | 透明玻璃、黑油墨 | 官方尺寸 |
| 2 | `SM_display` + `SM_display_screen` | AMOLED 模组，显示区单独一块，带声波着色器 | 黑、发光 | 官方尺寸；声波是概念设计 |
| 3 | `SM_case` | 白色外壳：玻璃槽、屏幕开口、四个螺丝柱、所有开孔 | 白色 ABS | 照片 |
| 3a | `SM_btn_function` | 橙色功能键，9 条细纹 | 橙色塑料 | 照片 |
| 3b | `SM_btn_power`、`SM_btn_boot` | 白色长圆键，POWER 在 −Y，BOOT 在 +Y | 白色塑料 | 照片 |
| 3c | `SM_label_L/R` (+`_supply`) | 排母旁的引脚标签，两个橙色电源格 | 白色贴纸 | 照片；不含文字 |
| 4 | `SM_core_pcb` | CoreBoard | 黑色阻焊 | 照片 |
| 4a | `SM_core_ics_front` | 正面：ESP32-S31（斜 45°）、Flash、PSRAM、IMU、电感等 | 黑 | 照片（位置）、假设（高度） |
| 4b | `SM_core_antenna_led`、`SM_core_display_conn` | 陶瓷天线、充电灯、屏幕排线座 | 陶瓷白、黑 | 官方（有这些零件）、照片（位置） |
| 4c | `SM_core_switches_mic` + `SM_core_switch_plungers` | 背面三个侧按开关和麦克风 | 钢、琥珀色 | 照片 |
| 4d | `SM_core_usbc_shell` + `SM_core_usbc_tongue` | USB-C 母座 | 钢、黑 | 标准尺寸 |
| 4e | `SM_core_btb_plug` | 板对板连接器（公） | 黑 | 官方（规格）、假设（高度） |
| 4f | `SM_core_motor` + `SM_core_motor_weight` | 震动马达和偏心块 | 钢、黄铜 | 照片 |
| 4g | `SM_core_gold`、`SM_core_passives` | 金色焊盘环和测试点、110 个贴片阻容 | 金、棕 | 阻容的分布是示意 |
| 5 | `SM_base_pcb` | BaseBoard，背面就是手表的背面 | 黑色阻焊 | 照片 |
| 5a | `SM_base_speaker` | 扬声器，靠 +X 的扬声器孔 | 黑 | 照片 |
| 5b | `SM_base_btb_socket` + `SM_base_btb_tails` | 板对板连接器（母）和 60 个触点 | 黑、金 | 官方（规格） |
| 5c | `SM_base_battery` | 501220 电池 | 琥珀色胶带 | 照片 |
| 5d | `SM_base_header_L/R` + `SM_base_header_pins` | 两个 2×10 弯针排母和 40 根针 | 黑、锡 | 官方、照片 |
| 5e | `SM_base_connectors`、`SM_base_ics`、`SM_base_edge_parts` | 电池和扬声器插座、TLV62569 稳压、边缘一排小件 | 白、黑 | 照片 |
| 5f | `SM_base_gold` | 背面 7 个金色扩展焊盘 | 金 | 照片：产品背面图 |
| 5f2 | `SM_base_marks_white`、`SM_base_marks_red` | 背面的白色文字和红色 Mosaico 标志，凸起 0.06 mm | 白色丝印、红 | 照片：产品背面图；字体用 Century Gothic（假设） |
| 5g | `SM_standoffs` | 两板之间的 4 根铜柱 | 黄铜 | 假设 |
| 6 | `SM_screw_1..4` | 4 颗黑色十字螺丝，共用一个网格 | 黑色发黑钢 | 照片 |
| 7 | `SM_cradle` | 3D 打印托架：底板、两侧壁、表带过桥 | 炭黑 PLA，0.2 mm 层纹 | 假设（我们自己的设计） |
| 8 | `SM_strap` + `SM_buckle` + `SM_strap_keeper` | 一条过的尼龙织带、滑扣、带环 | 橙色尼龙、黑 | 假设（我们自己的设计） |
