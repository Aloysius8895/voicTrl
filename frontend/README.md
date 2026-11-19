# voicTrl app（前端）

手机上的网页 app：和语音助手通话、看任务一步步执行、看每台设备的状态。屏幕宽的时候三块并排，方便比赛时投影。

**现在是样品**：所有数据都是示例，通话是假的，不连总控，不启动 Agora，不花钱。界面上有 "Sample" 标记。你确认样子之后，第二步再接总控和真的 Agora。

## 打开

双击 **start.cmd**，浏览器会打开 http://127.0.0.1:5310 。第一次会先装依赖，要等一两分钟。

也可以在 PowerShell 或 cmd 里运行：

```
cd C:\maven\voicTrl\frontend
npm install
npm run build
npm run render -- --serve
```

开发时用 `npm run dev`（同一个端口，改代码会自动刷新）。

### 看某一刻的样子

在地址后面加 `?scene=`，页面会停在那一刻：

| 地址 | 停在哪 |
|---|---|
| `/?scene=idle` | 还没打电话 |
| `/?scene=listening` | 通话中，助手在听 |
| `/?scene=waking` | 第 2 步：叫醒 Laptop B |
| `/?scene=building` | 第 4 步：在 B 上用 Claude 生成网页 |
| `/?scene=confirm` | 第 5 步：等你确认 |
| `/?scene=done` | 全部完成 |

再加 `&play=1` 会从那一刻继续往下播放；加 `&tab=evidence` 会直接打开设备面板的 Evidence 标签。

## 文件

| 路径 | 内容 |
|---|---|
| `src/demo/sampleRun.ts` | 样品的剧本：通话开始后第几毫秒，每一步、每台设备、字幕各是什么状态。纯函数，有测试 |
| `src/demo/useSampleRun.ts` | 在浏览器里推动剧本：时钟，以及通话、挂断、静音、确认、取消这些按钮 |
| `src/components/` | 通话卡 `CallCard`、任务步骤 `TaskPanel`、设备面板 `DevicePanel`、状态标签 |
| `src/styles.css` | 全部样式。颜色、圆角、字体都在开头的变量里 |
| `public/logo.svg` | app 图标的原图；`npm run icons` 会重新生成各种尺寸的图标 |
| `scripts/render.mjs` | 截图、自动检查、录演示视频；`--serve` 只开服务 |
| `design-review/` | 设计稿截图、演示视频和检查结果，见那里的 README |

## 测试

```
npm test             # 剧本的 11 个测试
npm run build
npm run render       # 截图、录视频、跑 26 项检查，结果在 design-review/
```

要在 **PowerShell 或 cmd** 里运行，路径用大写盘符 `C:\maven\...`。在 Git Bash 里路径是小写的 `c:`，测试框架会被加载两次，报 "failed to find the current suite"。

## 和模板的关系

样式参考 `C:\maven\voicTrl\templete\template3`（kivoagentic.ai 的网站镜像）：暖白底、橙色主色、大圆角卡片、`01 / 05` 编号的步骤卡、状态标签、带标签页的数据面板。

**没有从模板拿任何文件**：代码全部重写；不用它的名字、logo、图片、3D 模型和编译好的 JS。模板用的 Atyp 字体是商用字体，授权在原公司，这里换成了免费字体 Urbanist 和 JetBrains Mono（都是 SIL Open Font License），从 npm 装进 app，不连外网。

## 用到的开源包

React 19、Vite 8（用官方脚手架 create-vite 建的项目）、lucide-react（图标）、vite-plugin-pwa 和 @vite-pwa/assets-generator（可安装、离线可用、生成图标）、Vitest（测试）、playwright-core（截图，用本机的 Chrome）。

## 第二步要做的（等你确认样子后）

- 通话接上真的 Agora：把旧语音页 `physical-agent/voice-page` 里已经跑通的那段搬过来，包括向总控拿配置、启动和停止 Agent、把回答转发给手表。
- 步骤和设备状态改成从总控实时推送，替换掉样品剧本。总控那边要加对应的消息。
- 打包好的文件由总控直接挂出来，手机打开总控的 HTTPS 地址就能用，也能添加到主屏幕。
