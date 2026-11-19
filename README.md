# voicTrl

用一句话指挥多台个人设备协作完成一件事：你对手机（或 ESP-Mosaico 手表）说话，Agora 上的语音助手听懂后，经云端总控叫醒笔电、传文件、让 Claude Code 生成网页，再在你指定的电脑上打开结果。

为 Physical AI Hackathon Malaysia 2026（2026-11-28）而做，还在开发中。

## 目录

| 路径 | 内容 |
|---|---|
| `physical-agent/` | 总控（Python / FastAPI）、设备协议、模拟手表、旧的语音页（`voice-page/`，来自 Agora 官方样例，MIT） |
| `frontend/` | voicTrl app：手机上的 PWA，通话、任务步骤、设备状态三块。现在是样品，数据都是示例，见 `frontend/README.md` |
| `general/skills/` | 开发时用的技能，引用 [mattpocock/skills](https://github.com/mattpocock/skills)（git submodule） |
| `Physical_AI_Cross_Device_Agent_Implementation_Plan.md` | 长期架构设计 |
| `ESP32 开机棒.pdf` | 唤醒器（开机棒）的示意图和工作流程 |
| `CLAUDE.md` | 给 Claude Code 的工作规则 |

克隆时带上技能：`git clone --recurse-submodules https://github.com/Aloysius8895/voicTrl.git`

## 运行

**总控**（需要 [uv](https://docs.astral.sh/uv/)）：

```
cd physical-agent
uv run pytest                                   # 测试
uv run --env-file .env python -m pagent.coordinator
```

`.env` 照 `physical-agent/config/examples/coordinator.env.example` 填。Agora 的 App ID、证书、Customer Secret 和设备令牌都只从环境变量读，仓库里只有示例占位符。

**voicTrl app**：

```
cd frontend
npm install
npm run dev        # http://127.0.0.1:5310
```

## 没有放进仓库的

本地目录里还有这些，`.gitignore` 排除了，不公开：

- `templete/`：做界面时参考的几个网站镜像。里面是别人的编译代码、商用字体和品牌素材，只借风格，不再分发。
- `Copy/`、`data/`：别人开源仓库的本地副本，去原仓库获取。
- `idea/`：和本项目无关的其他工作。
- 所有 `.env` 文件和密钥。
