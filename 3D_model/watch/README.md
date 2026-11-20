# voicTrl 手表 3D 模型

ESP-Mosaico V1.2 开发套件装进我们设计的托架和表带，Blender 5.2 模型。能组装，也能用一个滑块拆成爆炸图。

## 打开方式

- 模型：`blender/watch.blend`（Blender 5.2 或更新）。
- 看零件分解，三种办法：
  1. 直接看图：`pic/3d/explode.png`（完全拆开）和 `shots/explode_half.png`（拆到一半）。
  2. 在 Blender 里拖滑块：右上角大纲里点 `WATCH_root`；右下属性栏选橙色方块图标的“物体属性”页，拉到最下面展开 Custom Properties；拖 `explode`，0 是组装，1 是完全拆开。视图右上角切到“材质预览”或“渲染”才看得到颜色。
  3. 渲染任意拆开程度：在 `blender/` 下运行 `blender -b watch.blend -P render_stills.py -- --shots explode --explode 0.3 --out <目录>`。
- 每个零件叫什么、是什么：点模型上的零件，大纲里会高亮它的名字；对照 `blender/spec.md` 的零件表。
- 屏幕声波：材质 `M_screen_waveform` 里名为 `phase` 的 Value 节点，改它声波就变，可以打关键帧。
- 相机：`CAM_hero`、`CAM_edge_fn`、`CAM_edge_usb`、`CAM_back`、`CAM_back_flat`、`CAM_explode`，另有三个对照官方照片角度的 `CAM_ref_*`。
- 成品图在 `C:\maven\voicTrl\pic\3d\`：`hero.png`、`edge_fn.png`、`edge_usb.png`、`back.png`、`back_flat.png`（都是 1920×1080）、`explode.png`（1200×1800）。

## 网页查看器

双击 `web/index.html`，用 Chrome 或 Edge 打开，不用联网，也不用起服务器。

- 拖动旋转，滚轮缩放，右键拖动平移。
- 底部滑块：从组装拖到拆开。
- 点零件：右上角显示它的名字和说明，再点空白处取消。
- “托架和表带”开关：关掉后只剩模块，翻到背面能看到标志和焊盘名。
- 屏幕上的声波是实时画的，会一直动。

模型改过之后，更新网页里的模型（在 `blender/` 下）：

```
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b watch.blend -P export_web.py
```

改了 `web/src/viewer.js` 之后，在 `web/` 下重新打包和测试：

```
npm install --ignore-scripts    # 只需一次：three 0.186.0 和 esbuild 0.28.2，约 34 MB
npm run build
npm test
```

| 文件 | 内容 |
|---|---|
| `web/index.html` | 页面 |
| `web/src/viewer.js` | 查看器源码 |
| `web/viewer.bundle.js` | 打包结果，内含 three.js 0.186.0（MIT，版权声明保留在文件里） |
| `web/watch.glb`、`web/watch.glb.js` | 导出的模型（902 KB），以及它的 base64 版本：双击打开的页面读不了本地 `.glb`，所以用脚本标签带进来 |
| `web/test/viewer.test.mjs` | 用无头 Chrome 打开页面的四个测试 |
| `blender/export_web.py` | 从 `watch.blend` 导出上面两个模型文件 |

测试用的是本机已有的 playwright-core（`%LOCALAPPDATA%\hairline-look`）和 Chromium（`%LOCALAPPDATA%\ms-playwright\chromium-1223`），换机器时用环境变量 `PLAYWRIGHT_CORE` 和 `CHROME_PATH` 指过去。

网页和 Blender 渲染的差别：glTF 带不走程序化材质，所以网页里托架没有打印层纹，引脚标签没有格线；表带纹理和屏幕声波是在网页里另外画的；灯光是照 Blender 的布光重搭的，不是同一套。

## 重建方式

模型全部由脚本生成，改模型改脚本，不在 Blender 里手改。在 `blender/` 目录下：

```
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --factory-startup -P build_all.py
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b watch.blend -P render_stills.py -- --shots hero,edge_fn,edge_usb,back,explode --out C:/maven/voicTrl/pic/3d --samples 384
```

重建约 10 秒，五张图约 80 秒（RTX 3070 Ti，OptiX）。

在打开的 Blender 里重建：

```python
import sys; sys.path.insert(0, r"C:\maven\voicTrl\3D_model\watch\blender"); import build_all; build_all.run()
```

`run()` 只删它自己上一次建的东西（集合 `WATCH`、`LOOK` 和名字以 `SM_`、`M_`、`LOOK_`、`CAM_` 开头的数据块），然后保存 `watch.blend`。

## 目录

| 文件 | 内容 |
|---|---|
| `blender/spec.py` | 所有尺寸，每个数带来源标签。改尺寸只改这里 |
| `blender/spec.md` | 尺寸表和零件表，给人看的 |
| `blender/watch_lib.py` | 公共函数：圆角轮廓、拉伸、放样、布尔、爆炸驱动器 |
| `blender/watch_mats.py` | 26 个材质，包括声波、打印层纹、织带纹理三个程序化着色器 |
| `blender/build_case.py` | 外壳、玻璃、屏幕、三个按键、引脚标签 |
| `blender/build_boards.py` | CoreBoard、BaseBoard、铜柱、螺丝 |
| `blender/build_marks.py` | 背面的标记：红色 Mosaico 标志、ESP-MOSAICO、Powered by Espressif、7 个焊盘名 |
| `blender/build_strap.py` | 托架、表带、滑扣、带环 |
| `blender/build_look.py` | 黑色背景、四盏灯、九个相机 |
| `blender/build_all.py` | 入口：重建全部并保存 |
| `blender/render_stills.py` | 按相机名渲染静帧 |
| `blender/check_fit.py` | 实测零件之间有没有互相穿插 |
| `blender/qa_scaled.py` | 把模型放大若干倍再跑 `qa_check.py`（原因见“跑过的检查”） |
| `blender/compare_sheet.py` | 把官方照片和对应角度的渲染拼在一起 |
| `shots/compare.png` | 对照图：上排官方照片，下排模型 |
| `shots/explode_half.png` | explode = 0.5 的检查图 |

## 用到的技能

按 `3D_model/README.md` 的规则调用，Blender 技能在 `C:/maven/Hackathon_map/rendering/blender-skills/skills`。

- **blender-core**：无头运行方式（`run_in_blender.py`）、环境报告（`env_report.py`）、5.x API 的注意事项。
- **blender-scene-setup**：`SM_` / `M_` 命名、集合分层、米制单位。
- **blender-hardsurface-modeling**：布尔用 EXACT、切割体要伸出表面、圆柱分段数。
- **blender-pbr-materials**：金属度只取 0 或 1；白塑料、黑塑料的反照率范围取自它的实测表；金、黄铜、钢三个材质直接由它的 `build_pbr_material.py` 预设生成。
- **blender-lighting-lookdev**：反光产品的打法（让长条灯映在表面上）、85–100 mm 镜头。
- **blender-rendering**：Cycles 采样和降噪、光程设置、色彩管理的选择。
- **blender-asset-qa**：`qa_check.py` 作为验收门槛。
- **blender-export-pipelines**：`export_asset.py` 的 `gltf` 预设导出 GLB，并核对它返回的摘要。
- **threejs-fundamentals、threejs-loaders、threejs-interaction**（three.js r186）：渲染器和色调映射、从内存解析 GLB、用 PMREM 生成环境光、OrbitControls 和点选。
- **tdd**（`general/skills`）：网页按“先写失败的测试，再写实现”一片一片做，测试点是浏览器里的整页。
- **machine**（`3D_model/machine/SKILL.md`）：只借它的质量标准（真实尺寸、零件按装配顺序、全部是封闭实体、不悬空不穿模），没有做 HTML 页面。

没有用到 `blender-retopology-uv`：表带的 UV 在建模时直接按长度和宽度写进去了。没有参考 `sample`、`sample2`、`sample3`。

## 尺寸来源和假设

完整表格在 `blender/spec.md`。要点：

- **官方数据**：盖板玻璃 43.3 × 43.3 × 0.7 mm、显示区 38.39 mm 见方、屏幕模组 41.09 × 40.29 × 0.8 mm（屏幕规格书）；2×10 排母 2.54 mm 间距、60 针板对板连接器、65 mAh 电池、7 个背面焊盘（用户指南）。
- **照片量取**：外壳厚 12 mm、圆角、按键和开孔的位置、电路板上零件的位置。官方没有公开整机尺寸图和 3D 文件，`esp-mosaico` 的 GitHub 组织里也只有固件仓库。
- **假设**：壁厚、两板间距 5.6 mm、板上零件的高度、铜柱和螺丝柱的做法。内部怎么叠是示意，不是真实拆解。
- **我们自己的设计**：托架、表带、滑扣，以及"横着戴"（橙色键朝手掌，像表冠）。

**参考照片不在仓库里。** 官方照片是 Espressif 的，不再分发：`pic/ref/` 和 `shots/compare.png` 都被忽略了。要重做对照图，从用户指南的图片目录 `https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s31/_images/` 下载 `esp-mosaico-v1.2-isometric.png`、`-front.png`、`-back.png`，存成 `pic/ref/mosaico-isometric.png`、`mosaico-front-labelled.png`、`mosaico-back-labelled.png`。屏幕规格书的链接在用户指南的 Related Documents 里。

## 跑过的检查

- **blender-asset-qa `qa_check.py`**（profile `render`，容差 0.05 mm，因为零件是毫米级）：48 个网格物体，27,970 个三角面，26 个材质，非流形边 0，开口边 0，全部是封闭实体。
  - 放大 10 倍和 100 倍检查（`qa_scaled.py`，容差同比例放大）：通过，0 个错误。
  - 按真实尺寸直接检查：报 9 对“重合面”，全在背面 1 mm 高的小字上，是误报。`qa_check.py` 判断“点在三角形内”用固定容差 1e-9 m²，是按米级模型定的；小字的面片边长不到 0.1 mm，相邻的面就被判成重合。用严格容差复查没有重合面，放大后同一形状也通过。
  - 约 75 条警告都接受了：“没有 UV”（材质是程序化的，不用 UV）；“贴在一起的隐藏面”（零件互相接触的地方，零件要保持封闭才能拆开展示）；屏幕和表带的 UV 重叠或零面积（只看得到一面）；“重复顶点”（小于 0.1 mm 的真实细节）；原点在模块中心而不在底面（有意为之）。
- **`check_fit.py`**：explode 取 0、0.5、1 时，零件之间都没有超过 0.12 mm 的穿插。零件故意沉进它所在的表面 0.02–0.1 mm，避免共面；把阈值收到 0.005 mm 时脚本能报出这些，说明检查有效。
- **对照官方照片**（`shots/compare.png`）：三个角度下轮廓、厚度比例、功能键、扬声器孔、USB-C、两个白键、背面焊盘和螺丝的位置都对得上。
- **看图**：五张成品图和 explode = 0.5 的检查图都看过，没有过曝、悬空和穿模。

## 遗留限制

- 内部零件的位置来自官方单板照片，但高度、两板间距、铜柱和螺丝柱是假设；手上有实物后应该量一遍，改 `spec.py`。
- 声波界面是概念设计，现在的固件里没有这个画面。
- 背面的标志和文字是照官方产品背面照片做的：红色 Mosaico 标志是按照片画的近似图形，字体用的是 Century Gothic（官方字体不明），小字比真品略粗。
- 背面的二维码没做：官方照片里它只有约 75 像素宽，读不出内容，不编造一个扫出来是别的东西的码。
- 侧面引脚标签上的字、芯片刻字没做。
- 侧面排母孔在渲染里比官方照片上浅：孔是真的开通的，看到的是白色孔壁。
- 电路板没有走线和丝印；贴片阻容是随机撒的，不是真实布局。
- 电池和扬声器的红黑导线没有做。
- 色彩管理用的是 Khronos PBR Neutral，不是 AgX：AgX 把亮橙色冲淡成了粉橙。
- 表带是闭合的一整圈，滑扣只是套在表带上的一个环，没有做真实的穿扣结构。
- 模型没有贴图，材质都是程序化的；网页查看器里因此少了托架层纹和标签格线（见“网页查看器”）。
- 网页查看器只在本机的 Chromium 里测过（约 90 帧每秒），没有在手机上试。
