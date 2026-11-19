# 05 Agora `/think` 注入与 transcript 回传调研

- 调研日期：2026-11-19（比赛 2026-11-28）
- 范围：补 01 号文件“关键事实 1(c)”和“未能核实”留下的缺口：`/think` 的完整契约、网页端拿 Agent 回答文字的办法、服务端替代路线、recipe-agent-mcp 后端。01 已写的内容不重复。
- 方法：只认一手来源。docs.agora.io 读的是页面的 `.md` 版（URL 后加 `.md`）和 OpenAPI 原文 <https://docs.agora.io/openapi/conversational-ai/rest-api.en.yaml>；GitHub 仓库只读克隆，链接钉到 commit 或 tag；PyPI `agora-agents` 2.14.0 的 wheel 解包后与仓库 HEAD（`68dfd7a`，pyproject 版本 v2.14.0）逐文件比对，`agent_session.py`、`agent_management/raw_client.py` 等 6 个文件内容一致。
- 没有运行任何代码，也没有调用 Agora 接口，所以“实际返回什么”只能给出文档和源码的说法。`AgoraIO/Docs-Source` 里的 `think.mdx` 停在 2026-05-20，没有 `append` 取值，已过时；`AgoraIO/docs-portal` 仓库存在但没有读。文档事实都取自 docs.agora.io 线上页面和线上 OpenAPI。

链接前缀（下文用简写）：
- SDK = <https://github.com/AgoraIO/agora-agents-python/blob/68dfd7acef07358e10b2ccc73dce83296d59073e/>
- VC = <https://github.com/AgoraIO-Conversational-AI/recipe-agent-voice-coder/blob/f594ba19330ea76b044fdb9da24d0253b182c2f2/>
- MCP = <https://github.com/AgoraIO-Conversational-AI/recipe-agent-mcp/blob/eb752356fbfe1ae5ea688c2c803df00db1c2e149/>
- TK = <https://github.com/AgoraIO-Conversational-AI/agent-client-toolkit-ts/blob/v2.9.0/>

---

## A. `/think`

来源（除另注外）：<https://docs.agora.io/en/api-reference/api-ref/conversational-ai/think> ；OpenAPI 第 5124–5347 行。

**A1 方法、URL、请求体**
- `POST https://api.agora.io/api/conversational-ai-agent/v2/projects/{appid}/agents/{agentId}/think`，头 `Content-Type: application/json`。路径参数 `appid`、`agentId` 都是必填 string。总览页写明 “Request URLs and request bodies are case-sensitive.”（<https://docs.agora.io/en/api-reference/api-ref/conversational-ai>）

| 字段 | 类型 | 必填 | 默认值 | 枚举值 |
|---|---|---|---|---|
| `text` | string | 是 | 无 | 无 |
| `on_listening_action` | string | 否 | `interrupt` | `inject` / `interrupt` / `append` / `ignore` |
| `on_thinking_action` | string | 否 | `interrupt` | `interrupt` / `append` / `ignore` |
| `on_speaking_action` | string | 否 | `ignore` | `interrupt` / `append` / `ignore` |
| `interruptable` | boolean | 否 | `true` | 无 |
| `metadata` | object（`additionalProperties: true`） | 否 | 无 | 无 |

- `append` 的原文：“Don't interrupt the current TTS playback. After the current turn's LLM output finishes, append the custom text instruction as a separate user message and start a new conversation turn.”
- `metadata` 在 Python SDK 里的类型是 `Dict[str, str]`（[SDK raw_client.py#L40](https://github.com/AgoraIO/agora-agents-python/blob/68dfd7acef07358e10b2ccc73dce83296d59073e/src/agora_agent/agent_management/raw_client.py#L40)）。

**A2 鉴权**（<https://docs.agora.io/en/api-reference/api-ref/conversational-ai/authentication> ；OpenAPI 第 14–27 行）
- `tokenAuth`（文档标 Recommended）：`type: apiKey`，`in: header`，`name: Authorization`，值的格式是 `agora token="<your_token>"`。token 用 App ID 和 App Certificate 在服务端生成；原文 “Tokens expire after a maximum of 86400 seconds.” Python 用 `agora_agent.agentkit.token.generate_convo_ai_token(app_id, app_certificate, channel_name, uid, token_expire)`。
- `basicAuth`：`Authorization: Basic <base64_credentials>`，对 `customer_id:customer_secret` 做 Base64。Customer ID 是 Console “RESTful API Keys” 下载文件里的 **Key**，Customer Secret 是 **Secret**。两种方式都只支持 HTTPS（TLS 1.0、1.1 或 1.2）。

**A3 `text` 长度上限：未能核实**
- think 页和 OpenAPI 的 `text` 都没有 `maxLength` 或长度说明（同一份 OpenAPI 里 `/speak` 的 `text` 写了 “512 bytes”）。
- Python SDK 2.14.0 不做长度校验，`text` 原样放进请求体（[SDK raw_client.py#L100-L115](https://github.com/AgoraIO/agora-agents-python/blob/68dfd7acef07358e10b2ccc73dce83296d59073e/src/agora_agent/agent_management/raw_client.py#L100-L115)）。
- recipe-agent-voice-coder 的 8 KiB 是它自己定的常量，按 UTF-8 字节计：`MAX_COMPLETION_ENVELOPE_BYTES = 8 * 1024`（[VC presentation.py#L11](https://github.com/AgoraIO-Conversational-AI/recipe-agent-voice-coder/blob/f594ba19330ea76b044fdb9da24d0253b182c2f2/server/src/task_runtime/presentation.py#L11)，校验在 L35、L49、L56）。代码和文档都没说这个数来自 Agora 的限制。

**A4 返回**
- `200`：`agent_id`（string）、`channel`（string）、`start_ts`（integer）。不含 LLM 的回答文字、turn id 或播放回执。
- think 页只列了 `200` 和 `default` 两项；`default` 的返回体是 `detail`（string）和 `reason`（string）。
- 通用状态码页（<https://docs.agora.io/en/api-reference/api-ref/conversational-ai/status-codes>）：`400` Invalid request parameters；`401` Authentication failed；`403` Unauthorized access；`404` Agent not found or has exited；`409` Agent conflict；`422` Access limit exceeded；`429` Request rate limit exceeded；`500` Internal server error；`502` Gateway error；`503` Agent startup failure；`504` Request timeout。
- `reason` 取值：`ServiceNotEnabled`、`AccountSuspended`、`InternalError`、`InvalidPermission`、`InvalidRequestBody`、`MissingRequiredField`、`InvalidFieldValue`、`ResourceQuotaLimitExceeded`、`ConcurrencyLimitExceeded`、`ServiceUnavailable`、`ResourceAllocationFailed`、`TaskConflict`、`TaskNotFound`、`TaskOperationTimeout`、`NotImplemented`。

**A5 Agent 不在运行时**
- think 页没有单独说明。通用状态码页给的是 `404`：“Agent not found or has exited”，建议动作 “Check whether the agent started successfully or has already stopped.”；对应的 `reason` 是 `TaskNotFound`：“The task was not started successfully, was aborted after starting, or has been destroyed.” 这是全接口通用表，不是针对 `/think` 的实测。
- SDK 层有两道：
  - `AgentSession.think` 先查本地状态，不是 `running` 就抛 `RuntimeError(f"Cannot think in {self._status} state")`，不发请求（[SDK agent_session.py#L781-L782](https://github.com/AgoraIO/agora-agents-python/blob/68dfd7acef07358e10b2ccc73dce83296d59073e/src/agora_agent/agentkit/agent_session.py#L781-L782)）。
  - HTTP 返回非 2xx 时抛 `ApiError`，带 `status_code`、`headers`、`body`；think 没有按状态码细分的子类（[SDK raw_client.py#L116-L130](https://github.com/AgoraIO/agora-agents-python/blob/68dfd7acef07358e10b2ccc73dce83296d59073e/src/agora_agent/agent_management/raw_client.py#L116-L130)；[api_error.py](https://github.com/AgoraIO/agora-agents-python/blob/68dfd7acef07358e10b2ccc73dce83296d59073e/src/agora_agent/core/api_error.py)）。
- recipe-agent-voice-coder 对“被明确拒绝”的判断：`except ApiError as exc: if exc.status_code is not None: return "rejected"`，也就是**任何带 HTTP 状态码的失败都算拒绝**，不区分 404 或 4xx/5xx；本地没有该 agent 的 session 返回 `"unavailable"`；其他异常（超时、断网）原样抛出，上层记为 `delivery_unknown`，不退回 `/speak`（[VC agent.py#L370-L396](https://github.com/AgoraIO-Conversational-AI/recipe-agent-voice-coder/blob/f594ba19330ea76b044fdb9da24d0253b182c2f2/server/src/agent.py#L370-L396)；[VC delivery.py#L119-L167](https://github.com/AgoraIO-Conversational-AI/recipe-agent-voice-coder/blob/f594ba19330ea76b044fdb9da24d0253b182c2f2/server/src/managed_ingress/delivery.py#L119-L167)）。
- **实测（2026-11-19，用本项目的 `HttpAgora` 和真实 App ID，basicAuth）**：对不存在的 agentId 调 `/think`，返回 `404`，`reason` 为 `TaskNotFound`，`detail` 为 “The session was not found, has already ended, or failed to start.”；agentId 格式不对（`not-a-real-agent`）时也是 `404`，但返回体里没有 `reason`。
- **实测（2026-11-19，完整生命周期）**：用 `agora-agents` 2.14.0 按 recipe-agent-mcp 的托管管线（Deepgram STT、OpenAI `gpt-4o-mini`、MiniMax TTS，不带任何厂商密钥，`Area.US`）启动 agent，4.9 秒返回 agentId，列表里状态为 `RUNNING`；对它调 `/think` 返回 `200`，耗时 0.47 秒；`stop_agent` 成功后再调 `/think`，返回 `404` 加 `TaskNotFound`，和不存在的 agentId 一样；对已停止的 agent 再 stop 一次不报错。频道里当时没有用户，所以没有听到回答。超时退出的 agent 还没测。
- 可以先用 `GET .../agents/{agentId}` 查 `status`，取值 `IDLE`、`STARTING`、`RUNNING`、`STOPPING`、`STOPPED`、`FAILED`（<https://docs.agora.io/en/api-reference/api-ref/conversational-ai/query>）。
- 和本项目相关的退出条件：`properties.idle_timeout` 默认 `30`（秒），`remote_rtc_uids` 里的用户全部离开频道超过这个时间，agent 自动退出；`0` 表示不因空闲退出；单次会话最长 72 小时（OpenAPI 第 1443–1457 行）。recipe-agent-mcp 设的是 `idle_timeout=30`（[MCP agent.py#L183](https://github.com/AgoraIO-Conversational-AI/recipe-agent-mcp/blob/eb752356fbfe1ae5ea688c2c803df00db1c2e149/server/src/agent.py#L183)）。手机网页一关，30 秒后 `/think` 就没有可用的 agent 了。

**A6 频率限制**
- 文档只有 `429` “Request rate limit exceeded”（建议动作 “Retry using a backoff strategy.”）和 `422` “Access limit exceeded”，没有给 `/think` 的 QPS 数字。另一条相关限制：“The number of Peak Concurrent Users (PCU) allowed to call the server API under a single App ID is limited to 20.”（<https://docs.agora.io/en/ai/build/start-stop-agent>）

**A7 Python SDK 的调用方式**
- 会话层：`AgentSession.think(text, *, on_listening_action=None, on_thinking_action=None, on_speaking_action=None, interruptable=None, metadata=None, options=None) -> AgentThinkResponse`；异步版 `AsyncAgentSession.think` 签名相同（[SDK agent_session.py#L764-L805](https://github.com/AgoraIO/agora-agents-python/blob/68dfd7acef07358e10b2ccc73dce83296d59073e/src/agora_agent/agentkit/agent_session.py#L764-L805)，异步版 L1131 起）。`options` 的类型是 `ThinkOptions`（[agentkit/agent.py#L175-L180](https://github.com/AgoraIO/agora-agents-python/blob/68dfd7acef07358e10b2ccc73dce83296d59073e/src/agora_agent/agentkit/agent.py#L175-L180)）。
- 底层（不需要 session 对象，只要 agentId）：`client.agent_management.agent_think(appid, agent_id, *, text, on_listening_action=OMIT, on_thinking_action=OMIT, on_speaking_action=OMIT, interruptable=OMIT, metadata=OMIT, request_options=None) -> AgentThinkAgentManagementResponse`（[agent_management/client.py#L38-L50](https://github.com/AgoraIO/agora-agents-python/blob/68dfd7acef07358e10b2ccc73dce83296d59073e/src/agora_agent/agent_management/client.py#L38-L50)）。返回类型的字段是 `agent_id`、`channel`、`start_ts`，全是 Optional（[agent_think_agent_management_response.py](https://github.com/AgoraIO/agora-agents-python/blob/68dfd7acef07358e10b2ccc73dce83296d59073e/src/agora_agent/agent_management/types/agent_think_agent_management_response.py)）。

---

## B. 手机网页拿 Agent 回答的文字

**B1 事件和回调字段**（npm `agora-agent-client-toolkit`，以 recipe 锁定的 2.9.0 源码为准）
- 事件：`AgoraVoiceAIEvents.TRANSCRIPT_UPDATED = 'transcript-updated'`，回调 `(transcription: TranscriptHelperItem<Partial<UserTranscription | AgentTranscription>>[]) => void`（[TK events.ts#L32](https://github.com/AgoraIO-Conversational-AI/agent-client-toolkit-ts/blob/v2.9.0/src/core/events.ts#L32)）。每次给的是**整段会话的完整数组**，不是增量，README 原话 “Delivers the **complete conversation history array** — not an incremental update.”（[HEAD README#L182-L190](https://github.com/AgoraIO-Conversational-AI/agent-client-toolkit-ts/blob/094e47d35fc6e0004543aba93940bf76edc01679/packages/conversational-ai/README.md#L182-L190)）
- 每项的字段：`uid`、`stream_id`、`turn_id`、`_time`、`text`、`status`（`TurnStatus`：`IN_PROGRESS = 0`、`END = 1`、`INTERRUPTED = 2`）、`metadata`（[TK types.ts#L387-L395](https://github.com/AgoraIO-Conversational-AI/agent-client-toolkit-ts/blob/v2.9.0/src/core/types.ts#L387-L395)，枚举在 L216–L220）。
- `metadata` 是服务端下发的原始消息（[TK types.ts#L235-L257](https://github.com/AgoraIO-Conversational-AI/agent-client-toolkit-ts/blob/v2.9.0/src/core/types.ts#L235-L257)）：
  - 公共字段：`object`、`text`、`start_ms`、`duration_ms`、`language`、`turn_id`、`stream_id`、`user_id`、`words`。
  - 说话方看 `object`：用户是 `'user.transcription'`，Agent 是 `'assistant.transcription'`。
  - 用户消息多一个 `final: boolean`；Agent 消息多 `quiet: boolean`、`turn_seq_id: number`、`turn_status: TurnStatus`。
- 顶层 `uid`：用户项固定是 `'0'`（`self_uid`），Agent 项是发布者的 RTC uid（[TK sub-render.ts#L251-L254](https://github.com/AgoraIO-Conversational-AI/agent-client-toolkit-ts/blob/v2.9.0/src/rendering/sub-render.ts#L251-L254)）。
- **坑**：`renderMode` 为 `TranscriptHelperMode.TEXT` 时，顶层 `status` 被写死成 `TurnStatus.END`（[TK sub-render.ts#L249](https://github.com/AgoraIO-Conversational-AI/agent-client-toolkit-ts/blob/v2.9.0/src/rendering/sub-render.ts#L249)）。判断“Agent 这一轮说完了”要看 `metadata.turn_status`，判断用户最终结果看 `metadata.final`。
- 传输：toolkit 同时监听 RTC 的 `'stream-message'` 和 RTM 的 `'message'`，两条路进同一个处理函数（[HEAD conversational-ai.ts#L1238-L1245](https://github.com/AgoraIO-Conversational-AI/agent-client-toolkit-ts/blob/094e47d35fc6e0004543aba93940bf76edc01679/src/core/conversational-ai.ts#L1238-L1245)）。
- docs.agora.io 的 Web toolkit 页用的是另一套名字：`ConversationalAIAPI`、`EConversationalAIAPIEvents.TRANSCRIPT_UPDATED`（值同为 `"transcript-updated"`）、`ISubtitleHelperItem`，字段相同（<https://docs.agora.io/en/api-reference/api-ref/conversational-ai/client-toolkit/web>）。npm 包实际导出的是 `AgoraVoiceAI` 这一套，写代码以包为准。

**B2 join 时要开的配置**（<https://docs.agora.io/en/ai/build/transcripts> ；OpenAPI 第 1512、4099 行）
- 文档表格标 Required 的两项：`advanced_features.enable_rtm: true`，`parameters.data_channel: "rtm"`。原文 “Transcript data is delivered through Signaling channel messages.” 可选的两项：`parameters.enable_metrics: true`、`parameters.enable_error_message: true`。
- 默认值：`enable_rtm` 默认 `false`；`data_channel` 默认 `datastream`，取值 `rtm` 或 `datastream`，`rtm` 只在 `enable_rtm` 为 `true` 时生效。开 RTM 前 token 要同时带 RTC 和 RTM 权限。
- 客户端前提：RTC SDK v4.5.1 以上；Console 里开通 Signaling；先 `subscribeMessage(channel)` 再启动 agent；逐词模式要在建 client 前调 `AgoraRTC.setParameter('ENABLE_AUDIO_PTS_METADATA', true)`。

**B3 recipe-agent-mcp 前端的做法**
- 包和版本（[MCP web/package.json#L17-L21](https://github.com/AgoraIO-Conversational-AI/recipe-agent-mcp/blob/eb752356fbfe1ae5ea688c2c803df00db1c2e149/web/package.json#L17-L21)）：`agora-agent-client-toolkit ^2.9.0`、`agora-agent-uikit 1.1.0`、`agora-rtc-react ^2.5.1`、`agora-rtc-sdk-ng ^4.24.3`、`agora-rtm ^2.2.3`。根目录 `bun.lock` 解析到 toolkit 2.9.0、rtc 4.24.4、rtm 2.2.4；`web/bun.lock` 是旧的（写着 toolkit 0.1.1），不要信。
- 关键代码（[ConversationComponent.tsx#L183-L247](https://github.com/AgoraIO-Conversational-AI/recipe-agent-mcp/blob/eb752356fbfe1ae5ea688c2c803df00db1c2e149/web/src/components/ConversationComponent.tsx#L183-L247)）：
  - L183–188：`AgoraVoiceAI.init({ rtcEngine: client, rtmConfig: { rtmEngine: rtmClient }, renderMode: TranscriptHelperMode.TEXT, enableLog: true })`。
  - L200–202：`ai.on(AgoraVoiceAIEvents.TRANSCRIPT_UPDATED, (t) => { setRawTranscript([...t]); })`。
  - L247：`ai.subscribeMessage(agoraData.channel)`。
- RTM 登录在 [LandingPage.tsx#L127-L134](https://github.com/AgoraIO-Conversational-AI/recipe-agent-mcp/blob/eb752356fbfe1ae5ea688c2c803df00db1c2e149/web/src/components/LandingPage.tsx#L127-L134)：`new AgoraRTM.RTM(appId, config.uid)` → `login({ token })` → `subscribe(channel_name)`，用的是 `/get_config` 给的同一个 token。
- 显示前的整理在 [lib/conversation.ts#L71-L97](https://github.com/AgoraIO-Conversational-AI/recipe-agent-mcp/blob/eb752356fbfe1ae5ea688c2c803df00db1c2e149/web/src/lib/conversation.ts#L71-L97)：把 `uid === '0'` 换成本地 uid，再按 `status !== TurnStatus.IN_PROGRESS` 分成“已完成”和“进行中”。
- 后端对应的 join 配置：`"advanced_features": {"enable_rtm": True}`，`parameters` 里 `"data_channel": "rtm"`、`"enable_error_message": True`、`"enable_metrics": True`（[MCP agent.py#L107-L122](https://github.com/AgoraIO-Conversational-AI/recipe-agent-mcp/blob/eb752356fbfe1ae5ea688c2c803df00db1c2e149/server/src/agent.py#L107-L122)）。

**B4 `/think` 注入的文字会不会作为 user transcript 下发**：会。实测（2026-11-19，托管管线，recipe-agent-mcp 的网页前端）：经总控用 `/think` 注入一句话后，语音助手用语音回答了，网页字幕里也出现了注入的那句话。字幕里是否带 `[think API injected]` 前缀没有记录。文档层面仍然没有说明，见“未能核实”。能确认的只有历史记录一侧：官方 `103 agent history` 的示例里，注入内容记成 `"role": "user"`，`content` 带前缀 `"[think API injected] User level: VIP"`（<https://docs.agora.io/en/ai/reference/event-types#103-agent-history> 的 Custom LLM 示例）。

---

## C. 服务端替代路线

**C1 REST `history`**（<https://docs.agora.io/en/api-reference/api-ref/conversational-ai/history> ；<https://docs.agora.io/en/ai/build/handle-runtime-events/retrieve-session-history>）
- `GET https://api.agora.io/api/conversational-ai-agent/v2/projects/{appid}/agents/{agentId}/history`，无请求体，鉴权同 A2。
- 返回：`agent_id`、`start_ts`、`status`、`contents[]`；每项有 `role`（`user` 或 `assistant`）和 `content`。`speech_start_ms`、`speech_end_ms`、`speech_algorithmic_delay` 只在 `llm.vendor` 为 `custom` 时返回。
- **只能在运行中调**：原文 “Call this endpoint while the agent is running”，`status` 的说明是 “Only supports querying the running agent.” 指南也把 “The session is still running and you want the current stored memory” 列为它的用途。
- 条数上限由 join 时的 `llm.max_history` 决定，默认 `32`（SDK 文档串：[agents/client.py#L276-L282](https://github.com/AgoraIO/agora-agents-python/blob/68dfd7acef07358e10b2ccc73dce83296d59073e/src/agora_agent/agents/client.py#L276-L282)）。SDK 调用是 `session.get_history()`，或 `client.agents.get_history(appid, agent_id) -> GetHistoryAgentsResponse`。
- 文档没有任何延迟说明，也没有“只取新增”的参数；要拿最新回答只能轮询后自己比对。
- `GET .../turns` 不含文字，只有每轮的起止和延迟，而且原文是 “After a conversation with the agent ends, use this endpoint”（<https://docs.agora.io/en/api-reference/api-ref/conversational-ai/turns>）。

**C2 webhook**（<https://docs.agora.io/en/ai/build/handle-runtime-events/webhooks> ；<https://docs.agora.io/en/ai/reference/event-types>）
- 没有实时带 transcript 的事件。带对话文字的只有 `103 agent history`，原文 “After an agent stops, this event notifies the stored history”，是 agent 停止之后才推一次。
- 其余：`101` agent joined、`102` agent left、`104` agent expire、`110` agent error（只有 `turn_id` 和错误）、`111` agent metrics、`112` turns finished（会话结束后推，不含文字）、`201`、`202`（电话）。
- webhook 要在 Console 的 Notifications 里配置公网 HTTPS 地址，10 秒内回 `200 OK`；验签用头 `Agora-Signature`（HMAC/SHA1）或 `Agora-Signature-V2`（HMAC/SHA256）。

**对本项目的含义**：总控想实时拿到回答文字，文档支持的服务端办法只有轮询 `history`；实时推送只在客户端（B1 的 `TRANSCRIPT_UPDATED`），所以“手机网页收到后转发给总控”是有文档依据的那条路。

---

## D. recipe-agent-mcp 后端

来源：[MCP server/src/server.py](https://github.com/AgoraIO-Conversational-AI/recipe-agent-mcp/blob/eb752356fbfe1ae5ea688c2c803df00db1c2e149/server/src/server.py) ；[MCP server/src/agent.py](https://github.com/AgoraIO-Conversational-AI/recipe-agent-mcp/blob/eb752356fbfe1ae5ea688c2c803df00db1c2e149/server/src/agent.py)

- 路由（server.py L115、L161、L194）：
  - `GET /get_config`（查询参数 `channel`、`uid`）→ `data` 里有 `app_id`、`token`、`uid`、`channel_name`、`agent_uid`。
  - `POST /startAgent`，请求体 `channelName`、`rtcUid`、`userUid`、`parameters`（可选）、`agentMode`（`"pipeline"` 或 `"realtime"`，默认 `"pipeline"`）→ `data` 里有 `agent_id`、`channel_name`、`status`、`agent_mode`。
  - `POST /stopAgent`，请求体 `agentId`。
  - FastMCP 挂在根路径，对外是 `/mcp`（server.py L216）。
- 读的环境变量名：`AGORA_APP_ID`、`AGORA_APP_CERTIFICATE`、`MCP_ENDPOINT`（这三个缺了 `Agent()` 初始化失败，三个路由都返回 500）、`AGENT_GREETING`、`OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`、`OPENAI_REALTIME_API_KEY`、`OPENAI_REALTIME_MODEL`、`PORT`。从 `server/.env.local` 和 `server/.env` 加载。前端另有 `AGENT_BACKEND_URL`。它不用 Customer ID/Secret：`AsyncAgora(area=Area.US, app_id=..., app_certificate=...)`，走 token 鉴权（agent.py L76–80）。
- agentId 存在哪：
  - 后端只放在进程内存的字典 `self._sessions: Dict[str, Any]`，键是 agent_id，值是 SDK 的 session 对象（agent.py L83 定义，L208 写入，L228 `pop`）。进程重启就没了，没有落盘。
  - 前端从 `/startAgent` 的 `data.agent_id` 拿到后放在 React state（`agoraData.agentId`），停止时再传回 `/stopAgent`。
  - 内存里找不到 session 时，停止走无状态的 `client.stop_agent(agent_id)`（agent.py L241–242）。
- 对本项目：总控要调 `/think`，要么一直持有这个 session 对象调 `session.think(...)`，要么只存 agentId、用 A7 的 `client.agent_management.agent_think(...)`。

---

## 未能核实

- **`/think` 的 `text` 长度上限**（字节或字符都没有说法）。查过：think 页、OpenAPI、状态码页、release notes、Python SDK 2.14.0 源码、recipe-agent-voice-coder 源码和文档。只知道官方样例自己限在 8 KiB，并记录过一次真实调用返回 HTTP 200（[VC test-results.md#L181](https://github.com/AgoraIO-Conversational-AI/recipe-agent-voice-coder/blob/f594ba19330ea76b044fdb9da24d0253b182c2f2/docs/ai/test-results.md#L181)，那次的实际字节数没有记录）。
- **对超时退出的 agentId 调 `/think` 实际返回的状态码和 `reason`**。不存在和已 stop 的 agentId 都已实测为 `404` 加 `TaskNotFound`（见 A5），超时退出的还没测。
- **`/think` 的频率限制数值**。文档只有 `429` 这个状态码。
- **`/think` 注入的文字会不会作为 `user.transcription` 下发到网页**。查过 transcripts 指南、Web toolkit 参考页、think 页、toolkit 源码，都没提。recipe-agent-voice-coder 的说法是 “The synthetic input may also appear as a user-role item in history or transcript”（[VC 07_gotchas.md#L48](https://github.com/AgoraIO-Conversational-AI/recipe-agent-voice-coder/blob/f594ba19330ea76b044fdb9da24d0253b182c2f2/docs/ai/L1/07_gotchas.md#L48)），它的实测记录把这一项标为 Partial：“the transcript was not independently captured”（[VC test-results.md#L191](https://github.com/AgoraIO-Conversational-AI/recipe-agent-voice-coder/blob/f594ba19330ea76b044fdb9da24d0253b182c2f2/docs/ai/test-results.md#L191)）。
- **`[think API injected]` 前缀在托管 LLM（非 `custom`）下是否也出现**，以及 `GET history` 里是否带这个前缀。官方只在 `103` 事件的 Custom LLM 示例里出现过一次。
- **不开 RTM 能不能收到 transcript**（来源互相矛盾）。docs.agora.io 的 transcripts 指南把 `enable_rtm: true` 和 `data_channel: "rtm"` 标为 Required；toolkit 的 README 写 “RTM is optional. Transcripts and agent state work without it — just omit `rtmConfig`”（[TK README.md#L152-L160](https://github.com/AgoraIO-Conversational-AI/agent-client-toolkit-ts/blob/v2.9.0/README.md#L152-L160)），join 参考页的 `data_channel` 默认值也是 `datastream`。recipe 走的是 RTM，照它做最稳。
- **`/think` 返回的 `start_ts` 含义**（来源矛盾）：docs.agora.io 写 “Timestamp indicating when the agent was created.”，SDK 类型注释写 “Unix timestamp in seconds when the think request was processed.”
- **用 token 鉴权调 `/think` 时，token 要绑定哪个 channel 和 uid**。鉴权页只在 join 的语境下说明（`channelName` 对 `properties.channel`，uid 对 `properties.agent_rtc_uid`）。用 SDK 的 `AsyncAgora(app_id, app_certificate)` 可以绕开这个问题，SDK 内部怎么生成这个 token 没有读。
- **`history` 的更新时机**：Agent 一句话说到一半或被打断时，`contents` 里是完整文字、部分文字还是没有，文档没写。
- **MLLM 模式下 `/think` 能不能用**：think 页仍然没写（本项目用级联模式，不受影响）。另外 webhooks 指南的事件表没列 `104` 和 `112`，event-types 页列了，本文按 event-types 页写，没有进一步求证。
