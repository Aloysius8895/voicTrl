# 语音页

手机（现在先是电脑浏览器）上像打电话一样和语音助手说话的网页。

## 来源

这是 Agora 官方样例 [recipe-agent-mcp](https://github.com/AgoraIO-Conversational-AI/recipe-agent-mcp) 的网页前端（MIT，见 `LICENSE`），拷自 `UPSTREAM_COMMIT` 里记的那个提交。样例自带的 Python 后端没有拷过来，总控实现了同样的三个接口（`/get_config`、`/startAgent`、`/stopAgent`）。

## 我们改了什么

只有三处，其余文件和上游一致：

- `web/src/lib/coordinator-link.ts`（新增）：从链接的 `#token=` 读手机的设备令牌；把语音助手说完的每一轮文字经 WSS 发给总控，由总控推到手表。
- `web/src/services/api.ts`：三个接口请求带上 `Authorization: Bearer <手机令牌>`。
- `web/src/components/ConversationComponent.tsx`：字幕更新时调用上面的转发。

另外删掉了上游的 `web/bun.lock`（已过时），依赖以根目录的 `bun.lock` 为准。

## 运行

```
# 1. 总控（在 physical-agent 目录）
uv run --env-file .env python -m pagent.coordinator

# 2. 语音页（在 physical-agent\voice-page\web 目录）
bun run dev

# 3. 拿到带令牌的链接，用浏览器打开（在 physical-agent 目录）
uv run --env-file .env python -m pagent.coordinator.voice_url
```

`web/.env.local` 里是两个地址，不是密钥：`AGENT_BACKEND_URL`（总控的 HTTP 地址）和 `NEXT_PUBLIC_COORDINATOR_WS_URL`（总控的设备 WSS 地址）。

第一次用先在 `voice-page` 目录运行 `bun install --frozen-lockfile`。测试：在 `voice-page` 目录运行 `bun test tests`。
