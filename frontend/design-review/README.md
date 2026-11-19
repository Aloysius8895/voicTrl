# voicTrl app 样品：设计稿

**状态：样品，等你确认。** 还没接总控，也没接真的 Agora。

## 你要的，以及我的理解

你给了模板 `templete\template3`（kivoagentic.ai 的网站镜像），要我照它做这个 app 的前端，放在 `C:\maven\voicTrl\frontend`。第 2 轮的 8 个问题你回答"全部是"，所以照这几条做：

- 一个手机网页 app，分三块：通话、任务步骤、设备状态。
- 用 Vite + React 新建。
- 先做样品，所有数据都是示例。
- 交互像打电话：大的通话按钮，挂断就停。
- 手机上排成一列，电脑上排成三栏。
- 名字先叫 voicTrl，界面文字用英文，做成 PWA。

## 先看这几张

| | |
|---|---|
| `05-phone-building.png` | 手机：第 4 步执行中，看得到助手选了哪个工具（`buildOnDevice`）、参数和进度 |
| `06-phone-confirm.png` | 手机：最后一步等你按 Confirm 或 Cancel，也可以直接说 "confirm" |
| `12-desktop-building.png` | 电脑：通话、步骤、设备三栏并排 |
| `demo.webm` | 手机上完整跑一遍，约 45 秒，用 Chrome 打开 |

## 全部截图

手机截图是 390×844（iPhone 14 的大小），按 2 倍清晰度截；电脑截图是 1440×900。

| 文件 | 内容 |
|---|---|
| `01-phone-idle.png` | 打电话前：第一屏只有一个大的通话按钮 |
| `02-phone-idle-task.png` | 打电话前：任务区是空的，并举例告诉你可以怎么说 |
| `03-phone-listening.png` | 通话中：助手在听，字幕只显示最近两句 |
| `04-phone-waking.png` | 第 2 步：叫醒 Laptop B（`wakeDevice`，Wi-Fi 唤醒器） |
| `05-phone-building.png` | 第 4 步：Claude Code 在 B 上生成网页 |
| `06-phone-confirm.png` | 第 5 步：等你确认 |
| `07-phone-devices.png` | 设备面板：两台笔电已上线，右上角显示有 1 件事等你 |
| `08-phone-evidence.png` | 证据标签：两台笔电各自的唤醒用时、文件 SHA-256、网页里的本次运行码 |
| `09-phone-done.png` | 五步全部完成 |
| `10-phone-full-page.png` | 手机上整页（运行结束后） |
| `11-desktop-idle.png` | 电脑：打电话前，上面是标题 "One voice. Every device." |
| `12-desktop-building.png` | 电脑：执行中，三栏并排 |
| `13-desktop-confirm.png` | 电脑：等你确认 |

## 怎么用

- **打电话**：点 "Call your assistant"，或者顶栏的 Call。依次经过连接、问候、你说话、思考，然后任务开始。
- **通话中**：左边的按钮静音，右边黑色的按钮挂断。挂断后任务照样在设备上跑，可以点 "Call again" 回到通话。
- **步骤卡**：正在执行的那一步会展开，显示三行：
  1. Understand：为什么要做这一步。
  2. Pick the tool：用哪个工具，带什么参数。
  3. Execute：怎么执行的，下面有进度条。

  做完后收起，显示结果，例如 "Awake in 4.1 s"。
- **最后一步**：Confirm 完成任务，Cancel 取消。
- **设备面板**：Devices 标签看每台设备的状态（Asleep、Waking、Online），Evidence 标签看这次运行的证据。

样品里一次完整运行约 40 秒。真实情况下 Claude 生成网页要几分钟，样品里压缩成 12 秒。

## 和模板的关系

| 模板里的 | 这里的 |
|---|---|
| 橙色大卡（KivoSales 那张） | 通话卡 |
| `01 / 05` 的代理卡，带 Waiting / Executing 标签，展开后是 "Think and reason / Pick the right tool / Execute" | 任务步骤卡，展开后是 Understand / Pick the tool / Execute |
| Execution analytics 面板（标签页加数字格子） | 设备面板（Devices / Evidence 两个标签） |
| 浮在顶上的圆角导航条，右边一个橙色按钮 | 同样的顶栏，按钮是 Call |

**没有用模板的任何文件**。代码是新写的，名字、logo、图片、3D 球体、Atyp 字体都没用。字体换成免费的 Urbanist 和 JetBrains Mono。

## 渲染时发现并改掉的问题

1. 顶栏原来太透明，往下滑时后面卡片的字会透出来。改成几乎不透明，并把滑到它下面的内容模糊掉。
2. 工具参数挤在一行，`prompt: file1.md` 被折成两行。改成每个参数单独占一行。
3. 证据里的用时（4.1 s）原来也用等宽字体，看着别扭。现在只有 hash 和运行码用等宽字体。
4. 电脑上首屏露不出通话按钮。压缩了标题区的留白，通话卡也调矮了一点。
5. 电脑三栏时，往下看步骤会把右边的设备面板滑走。改成和通话卡一样固定在屏幕上。
6. 顶栏的 Call 按钮只有 42px 高，手机上按起来偏小。改成 44px。

## 自动检查

26 项全部通过（`render-report.json`）：

- 手机和电脑在每个场景下都没有横向滚动条。
- 字体是从 app 自己加载的。
- 手机上每个按钮都至少 44px 高。
- 执行中的步骤永远只有一个，并且显示工具名。
- 点 Confirm 能完成任务；点通话能开始，点挂断能结束。
- 电脑上三栏顶部对齐。
- PWA：manifest 正确，有 512px 图标，service worker 在运行，第一次打开后断网也能开。
- 整个过程没有任何请求发到本机以外，页面没有任何报错。

逻辑另有 11 个单元测试（`src/demo/sampleRun.test.ts`），也全部通过。

## 限制

- 只做了浅色。模板就是浅色的，通话卡本身是橙色，在投影上也够醒目。
- 样品没有失败的情况，比如设备叫不醒或者 Claude 出错。接真数据时要补上 Failed 的样子，组件里已经有这个状态。
- 截图里的模糊效果是按 Chrome 的规则写的，在 iPhone Safari 上的效果要你在真机上看一眼。

## 需要你确认

1. **样子可以吗？** 可以的话，我就进入第二步：接上总控和真的 Agora，取代旧的语音页。
2. **标题文案**：电脑上的大标题是 "One voice. Every device."，副标题是 "Talk to your assistant. It wakes your laptops, moves the files, has Claude build the page, and opens the result wherever you are." 我建议先这样，Pitch 时也能直接用。
3. **样品里步骤的名字和顺序**，照的是计划里的演示脚本：叫醒 A，叫醒 B，传 file1.md，在 B 生成，在 A 打开。我建议不改。
