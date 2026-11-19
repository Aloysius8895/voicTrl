# 06 手表语音输入两条路线：W1 出厂固件 / W2 自写按住说话固件

- 调研日期：2026-11-19（比赛 2026-11-28）。**未做真机验证**：没有编译、烧录或运行任何固件，结论全部来自读源码和官方文档。凡标"需真机验证"的，当天按第 5 节测。
- 方法：浅克隆三个公开仓库后本地读源码，链接固定到提交：esp-mosaico-claw `8b48039`（2026-11-17）、esp-claw `5007277`（2026-11-12，正是前者子模块锁定的提交）、esp-mosaico-bsp `841f624`（2026-11-11）。价格取自各家官方定价页，查询日期均为 2026-11-19。
- 与 01 号笔记的关系：只补缺口。01 号笔记"ASR 只有 DashScope fun-asr-realtime、默认 zh"的说法要修正，见 2.1 和 2.2。

## 1. 结论先行

| 项目 | W1：出厂固件 Mosaico-Claw | W2：基于 BSP 自写按住说话固件 |
|---|---|---|
| 是否要改固件 | 不用。三处都在网页配置里改：识别语言、LLM 端点、ASR 端点 | 要。自己写、编译、烧录 |
| 英文识别依据 | `asr_language_hint` 可在网页改成 `en`，固件把它放进 `language_hints`；fun-asr-realtime 官方列出 `en`。试用服务是否认这个参数：需真机验证 | 识别放在总控，服务任选，英文都支持（第 4 节） |
| 文字能否直达总控 | 不能绕过 LLM：文字直接进 agent，没有事件或钩子。**但"总控冒充 OpenAI 兼容 LLM"在源码层面成立**（2.3）；另可"总控冒充 ASR 端点"直接收音频（2.4） | 能。总控收到 PCM，自己识别后生成 `utterance` |
| 预计延迟的依据 | 按住期间每 20 ms 流式送音频，松手后取终稿，再发一次非流式 HTTPS 请求。实际秒数：需真机验证 | 边录边传 WSS，松手即发结束标记；延迟主要取决于识别服务。实际秒数：需真机验证 |
| 需要的账号 | 默认用 Espressif 试用服务，不需要账号。备用：阿里云国际站百炼密钥 | 一个语音识别服务账号（推荐 Deepgram） |
| 费用 | 试用服务未见收费说明，额度未知。自备密钥时 $0.00009/秒（新加坡） | Deepgram 流式 $0.0048/分钟，新账号送 $200 |
| 赛前能准备到什么程度 | 总控的 `/v1/chat/completions` 冒充端点、解析规则、单元测试可全部写完；用 curl 按 2.3 的请求体自测 | 总控的音频 WSS 端点和识别对接可全部写完并用电脑麦克风测通；固件代码可写好并编译通过，但无法验证音频和按键 |
| 当天现场工作量 | 装 Mosaico-Claw、连 Wi-Fi、网页填 5 个字段、重启、测 4 项（约 1 小时）。需真机验证 | 装好工具链的前提下：烧录、调麦克风增益、调 Wi-Fi 和 TLS、调界面（估计占 4.5 小时里的大半）。需真机验证 |
| 主要风险 | 设备上未必已装 Mosaico-Claw；试用服务额度和英文支持未知；说话必须在 AI Create 界面按住屏幕，AI 键不参与；请求里混有系统提示、工具表和记忆提取调用 | 工具链是 ESP-IDF master 指定提交，Windows 安装耗时没有官方数字；BSP 没有 Wi-Fi STA、HTTP 客户端、WebSocket 示例，要自己拼；刷自写固件后如何回到 Vibe Mode 未核实 |

建议：W1 的"总控冒充 LLM"做主线，赛前把总控端写完；W2 做备线，赛前只把总控的音频端点和工具链准备好。两条线共用总控的 `utterance` 入口。

## 2. W1 细节

### 2.1 语音识别：语言能配置成英文

- 语言是一个运行时配置项，不是编译期常量。字段 `asr_language_hint`，NVS 键 `asr_language`，默认 `"zh"`：[app_config.c L64-L70、L115](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/components/app_config/app_config.c#L64-L70)。
- 配置入口是设备自带网页（80 端口）的 ASR 页，输入框标签 "Language Hint"：[AsrPage.tsx L169-L173](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/components/http_server/frontend_source/src/pages/AsrPage.tsx#L169-L173)；后端是 `GET/POST /api/config`，字段名 `asr_language_hint`：[http_server_config_api.c L59-L65](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/components/http_server/http_server_config_api.c#L59-L65)。没有对应的 Kconfig 项，也没在设备设置菜单和 Lua 里找到入口。
- ASR 配置改完即时生效，不用重启：`main_asr_config_changed` 比较后重建服务，[main.c L122-L134、L148-L226](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/main/main.c#L122-L226)。
- 固件把该值作为单元素数组写进 run-task 的 `language_hints`：[asr_provider_qwen.c L257-L306](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/components/asr_service/src/asr_provider_qwen.c#L257-L306)。音频格式固定 `pcm`、16000 Hz、单声道、16 位，20 ms 一帧：[asr_provider.h L19-L21](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/components/asr_service/src/asr_provider.h#L19-L21)、[asr_service.c L29-L30](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/components/asr_service/src/asr_service.c#L29-L30)。
- 协议只有一种（`ASR_SERVICE_PROVIDER_QWEN`，即 DashScope 双工 WebSocket），其他 `asr_provider` 值会报不支持：[asr_service.h L27-L29](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/components/asr_service/include/asr_service.h#L27-L29)、[main.c L167-L171](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/main/main.c#L167-L171)。
- 阿里官方文档（DashScope / 百炼）：
  - `language_hints`："There is no default value; if not set, the model detects the language automatically."，只有第一个值生效；`fun-asr-realtime` 列出 30 个语种代码，含 `en`；快照 `fun-asr-realtime-2026-02-28` 只有 `zh`、`en`、`ja`。<https://help.aliyun.com/en/model-studio/fun-asr-client-events>
  - 单价（国际站价格页，美元）：新加坡 $0.00009/秒，免费额度 36,000 秒，有效期 90 天；北京 $0.000047/秒，未列免费额度。页面原话："The following models offer a free quota only in the Singapore region"。<https://www.alibabacloud.com/help/en/model-studio/model-pricing>；中文页北京价 0.00033 元/秒：<https://help.aliyun.com/zh/model-studio/fun-asr-realtime>
  - 接入地址：新加坡 `wss://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/api-ws/v1/inference`，北京把地域换成 `cn-beijing`；请求头 `Authorization: Bearer <api_key>`。<https://www.alibabacloud.com/help/en/model-studio/fun-asr-realtime-websocket-api>
  - 旧域名仍列在地域页：新加坡 `dashscope-intl.aliyuncs.com`，北京 `dashscope.aliyuncs.com`；原话 "Each region has its own endpoint, API Key, and model list. These cannot be used across regions."。<https://www.alibabacloud.com/help/en/model-studio/regions>
  - 固件默认端点是北京的 `wss://dashscope.aliyuncs.com/api-ws/v1/inference`（[asr_service.h L20](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/components/asr_service/include/asr_service.h#L20)），用新加坡密钥时必须同时把 `asr_endpoint` 改成新加坡地址。

### 2.2 出厂默认不是用户的 DashScope 密钥，而是 Espressif 试用服务

- 默认 `asr_endpoint_provider="trial"`、`asr_model="device-asr"`、`asr_api_key=""`；LLM 同样默认 `llm_endpoint_provider="trial"`、`llm_model="device-chat"`：[app_config.c L37-L39、L64-L70](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/components/app_config/app_config.c#L37-L70)。
- 试用服务器是 Espressif 自己的两个地址，按地区选：大陆 `https://mosaico-asr.espressif.com.cn`，其他地区 `https://as.esp-claw.com`：[trial_provider/Kconfig L12-L24](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/components/trial_provider/Kconfig#L12-L24)。ASR 走 `wss://<host>/v1/asr/realtime`，LLM 走 `https://<host>/v1`：[trial_provider.c L21、L51-L76](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/components/trial_provider/src/trial_provider.c#L51-L76)。
- 认证不用用户密钥：设备 ID 是 Wi-Fi MAC，向 `/v1/device/challenge` 取随机数，用 eFuse 里的 HMAC 密钥签名，再到 `/v1/device/token` 换短期令牌：[trial_token.c L144-L149、L240-L333](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/components/trial_provider/src/trial_token.c#L240-L333)。
- 限制：源码里只有令牌过期时间和 401/403 处理，**额度、次数、有效期都在服务端，查不到**。该组件没有 README。试用服务是否把 `language_hints=en` 传给后端：需真机验证。
- 自备密钥时，网页 ASR 页的 "qwen" 预设会填 `asr_endpoint_provider=static`、`asr_model=fun-asr-realtime`、北京端点：[AsrPage.tsx L26-L41](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/components/http_server/frontend_source/src/pages/AsrPage.tsx#L26-L41)。

### 2.3 文字能否不经 LLM 直达总控

**文字的流向（逐跳）**
1. ASR 结果只通过一个 C 回调发出：`asr_service_register_cb`，事件 `ASR_SERVICE_EVENT_PARTIAL` / `ASR_SERVICE_EVENT_FINAL`：[asr_service.h L31-L48、L72](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/components/asr_service/include/asr_service.h#L31-L72)。
2. 全仓库只有一个订阅者 `ai_create_voice_session.c`：[L114-L178、L402](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/components/mosaic_ui/common/ai_create_voice_session.c#L114-L178)。
3. 松手后控制器把终稿交给 `ai_create_controller_post_text`：[ai_create_controller.c L911-L942](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/components/mosaic_ui/common/ai_create_controller.c#L911-L942)。
4. 它调 `cap_im_ai_create_post_message`，后者直接调 `claw_agent_mgr_post_root_message`：[cap_im_ai_create.c L471-L532](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/components/cap_im_ai_create/src/cap_im_ai_create.c#L471-L532)。
5. 该函数把文字放进根 agent 的请求队列，随后进入 LLM 循环：[claw_agent_mgr.c L825-L874](https://github.com/espressif/esp-claw/blob/50072775cfa20d7ce25a9b27591d9d7c8b9dbab5/components/claw_modules/claw_manager/src/claw_agent_mgr.c#L825-L874)、[claw_core_agent_loop.c L304-L340](https://github.com/espressif/esp-claw/blob/50072775cfa20d7ce25a9b27591d9d7c8b9dbab5/components/claw_modules/claw_core/src/claw_core_agent_loop.c#L304-L340)。

**各个口子的结论**
- 事件路由器（event router）：有 `call_cap`、`run_agent`、`run_script`、`send_message`、`emit_event`、`drop` 六种动作（[claw_event_router.c L668-L706](https://github.com/espressif/esp-claw/blob/50072775cfa20d7ce25a9b27591d9d7c8b9dbab5/components/claw_modules/claw_event_router/src/claw_event_router.c#L668-L706)），但语音这条路没有调用 `claw_event_router_publish`，路由规则拦不到它。结论：不可用。
- Lua：`capability.call(name, payload)` 可以调用任何已注册能力，调用者身份是 `CLAW_CAP_CALLER_SYSTEM`（[README](https://github.com/espressif/esp-claw/blob/50072775cfa20d7ce25a9b27591d9d7c8b9dbab5/components/lua_modules/lua_module_call_capability/README.md)、[lua_module_capability.c L254、L335](https://github.com/espressif/esp-claw/blob/50072775cfa20d7ce25a9b27591d9d7c8b9dbab5/components/lua_modules/lua_module_call_capability/src/lua_module_capability.c#L254)），所以 `http_request` **不是只有 LLM 能调，Lua 也能调**。但 Lua 拿不到 ASR 文字（没有事件，也没有 ASR 的 Lua 模块）。结论：能发 HTTP，拿不到文字。
- `http_request`：参数 `url`、`method`、`headers`、`body`、`timeout_ms` 等，标志 `CLAW_CAP_FLAG_CALLABLE_BY_LLM`：[cap_http_request.c L681-L700](https://github.com/espressif/esp-claw/blob/50072775cfa20d7ce25a9b27591d9d7c8b9dbab5/components/claw_capabilities/cap_http_request/src/cap_http_request.c#L681-L700)。让 LLM 每句话都调一次它，等于仍然经过 LLM，而且多一轮往返，不如直接冒充 LLM。
- `http_allowlist`：配置字段 `search_http_allowlist`（NVS 键 `http_allow_ls`），在网页 "search" 分组里改。格式是逗号分隔的主机名：`*` 全放行，`*.example.org` 或 `.example.org` 匹配子域，其余精确匹配：[cap_http_request.c L301-L341](https://github.com/espressif/esp-claw/blob/50072775cfa20d7ce25a9b27591d9d7c8b9dbab5/components/claw_capabilities/cap_http_request/src/cap_http_request.c#L301-L341)。Mosaico 固件的默认值是 `"*"`：[Kconfig.projbuild L104-L110](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/main/Kconfig.projbuild#L104-L110)。

**重点：把 LLM 端点指向总控（成立）**
- 可配置项全部在网页 LLM 页，有现成的 `openai_compatible` 自定义预设：`llm_endpoint_provider=static`、`llm_backend_type=openai_compatible`、`llm_base_url`、`llm_api_key`、`llm_auth_type`、`llm_model`、`llm_supports_tools`：[LlmPage.tsx L164-L176](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/components/http_server/frontend_source/src/pages/LlmPage.tsx#L164-L176)、[http_server_config_api.c L45-L58](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/components/http_server/http_server_config_api.c#L45-L58)。`llm_base_url` 和 `llm_api_key` 各 320 字节：[app_config.h L15-L32](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/components/app_config/include/app_config.h#L15-L32)。
- LLM 配置保存后要重启才生效，返回信息原话："Saved. Restart the device to apply Wi-Fi, core LLM, capability, and Lua module changes."：[http_server_config_api.c L519-L520](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/components/http_server/http_server_config_api.c#L519-L520)。
- 请求：`POST {llm_base_url}/chat/completions`（[backend 头文件 L11](https://github.com/espressif/esp-claw/blob/50072775cfa20d7ce25a9b27591d9d7c8b9dbab5/components/claw_modules/claw_core/src/llm/backends/claw_llm_backend_openai_compatible.h#L11)），`Content-Type: application/json`，TLS 用 `esp_crt_bundle_attach`（[claw_llm_http_transport.c L286-L324](https://github.com/espressif/esp-claw/blob/50072775cfa20d7ce25a9b27591d9d7c8b9dbab5/components/claw_modules/claw_core/src/llm/claw_llm_http_transport.c#L286-L324)）。所以总控证书必须由公共 CA 签发。
- 认证：`llm_auth_type=bearer` 时发 `Authorization: Bearer <llm_api_key>`，`api-key` 时换成另一个头，`none` 时不发：[claw_endpoint_static.c L29-L57](https://github.com/espressif/esp-claw/blob/50072775cfa20d7ce25a9b27591d9d7c8b9dbab5/components/claw_modules/claw_endpoint/src/claw_endpoint_static.c#L29-L57)。**总控现有的 Bearer 令牌可以直接填进 `llm_api_key`。**
- 请求体：`model`、`max_tokens`（字段名可配）、`messages`（第一条是 `system`，其后是历史，最后一条是 `{"role":"user","content":"<识别文字>"}`）、可选 `tools`。**没有 `stream` 字段，是非流式**：[backend.c L187-L258](https://github.com/espressif/esp-claw/blob/50072775cfa20d7ce25a9b27591d9d7c8b9dbab5/components/claw_modules/claw_core/src/llm/backends/claw_llm_backend_openai_compatible.c#L187-L258)、[claw_core_context.c L33-L50](https://github.com/espressif/esp-claw/blob/50072775cfa20d7ce25a9b27591d9d7c8b9dbab5/components/claw_modules/claw_core/src/claw_core_context.c#L33-L50)。
- 响应要求：`choices[0].message.role` 必须是 `"assistant"`，`content` 是非空字符串，或者带 `tool_calls`；否则报 "LLM returned empty text response"：[backend.c L61-L185](https://github.com/espressif/esp-claw/blob/50072775cfa20d7ce25a9b27591d9d7c8b9dbab5/components/claw_modules/claw_core/src/llm/backends/claw_llm_backend_openai_compatible.c#L61-L185)。没有 `tool_calls` 时本轮直接结束并把文字显示出来：[claw_core_agent_loop.c L333-L340](https://github.com/espressif/esp-claw/blob/50072775cfa20d7ce25a9b27591d9d7c8b9dbab5/components/claw_modules/claw_core/src/claw_core_agent_loop.c#L333-L340)。
- 总控端要处理的三件事：
  1. 每个会话的第一句会被加前缀 `"Trusted AI Create mode instruction: ... User request:\n"`，要截掉：[cap_im_ai_create.c L59-L98](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/components/cap_im_ai_create/src/cap_im_ai_create.c#L59-L98)。
  2. 记忆模块会在回复后另发一次不带 `tools` 的 chat 请求做自动提取（默认 `APP_CLAW_MEMORY_MODE_FULL`），总控要按 system 提示内容识别并回一个无害的空结果：[claw_memory_extract.c L63-L92](https://github.com/espressif/esp-claw/blob/50072775cfa20d7ce25a9b27591d9d7c8b9dbab5/components/claw_modules/claw_memory/src/claw_memory_extract.c#L63-L92)、[app_claw.c L632-L660](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/components/app_claw/app_claw.c#L632-L660)。具体提示词和期望的 JSON 没有细读，需真机验证。
  3. 把 `llm_supports_tools` 设成 `false` 能否去掉 `tools` 字段、缩小请求体：源码显示有工具且该项为假时返回 `ESP_ERR_NOT_SUPPORTED`（[backend.c L232-L237](https://github.com/espressif/esp-claw/blob/50072775cfa20d7ce25a9b27591d9d7c8b9dbab5/components/claw_modules/claw_core/src/llm/backends/claw_llm_backend_openai_compatible.c#L232-L237)），上层是否会因此不传工具没有读到。保守做法是保持 `true`，总控忽略 `tools`。
- `utterance` 的 `lang` 和 `final` 由总控自己填（固件只给文字；到达 LLM 的都是终稿）。

### 2.4 另一个不改固件的口子：把 ASR 端点指向总控

`asr_endpoint_provider=static` 时，固件用 `asr_endpoint` 作为 WebSocket 地址，并附 `Authorization: Bearer <asr_api_key>`，TLS 同样用证书包：[asr_service.c L462-L468](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/components/asr_service/src/asr_service.c#L462-L468)、[asr_provider_qwen.c L576-L612](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/components/asr_service/src/asr_provider_qwen.c#L576-L612)。总控只要实现 DashScope 的四种事件（`task-started`、`result-generated`（`payload.output.sentence.text` / `sentence_end`）、`task-finished`、`task-failed`：[L344-L420](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/components/asr_service/src/asr_provider_qwen.c#L344-L420)），就能直接收到 16 kHz PCM 并自选识别服务。代价是要仿一套协议，工作量比 2.3 大；只在试用 ASR 英文不行、又不想开阿里云账号时用。

### 2.5 不改固件能做到哪一步，哪一步必须重新编译

- 不改固件：改识别语言；换 ASR 密钥和端点；LLM 指向总控；总控返回的短句显示在手表上。
- 必须改固件：用 AI 键（GPIO7）按住说话；不进 AI Create 界面就能说话；走 WSS 发 `utterance` 消息；自定义震动和界面；拿到部分结果（`final=false`）。
- 重新编译步骤（仓库 README 原文）：`python -m pip install -r requirements.txt` → `git submodule update --init --recursive` → `idf.py bmgr -c ./boards -b esp_mosaico` → `idf.py build` → `idf.py -p PORT flash monitor`：[README](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/README.md)。
- ESP-IDF 版本：README 写 "ESP-IDF 6.x environment with ESP32-S31 support"；GitLab CI 说明写 "ESP-IDF 6.2"（[.gitlab/README.md](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/.gitlab/README.md)）；GitHub CI 用 `espressif/idf:latest` 镜像（[build.yml L21](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/.github/workflows/build.yml#L21)）。仓库没有锁定具体提交。6.2 尚未发布（见 3.3），实际只能用 master。
- 自编固件还能不能用试用服务取决于 eFuse HMAC 密钥是否已烧（`CONFIG_TRIAL_DEVICE_HMAC_KEY_ID`）：需真机验证。

### 2.6 AI 键和唤醒词

- AI 键在板级定义里是 GPIO7、低电平有效（[board_peripherals.yaml L94-L99](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/boards/esp_mosaico/board_peripherals.yaml#L94-L99)、[boards README L47](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/boards/esp_mosaico/README.md)），**但出厂固件的 C 代码没有给 `button_ai` 注册任何回调**（在主仓库和 esp-claw 子模块里搜索 `button_ai`，只命中这两个板级 YAML；另一个子模块 esp-mosaico-utils 没有查）。
- 注册了回调的是 `button_power`（GPIO57）：单击返回，按住 500 ms 打开 AI Create：[mosaic_button_platform.c L16-L17、L70-L111](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/main/platform/mosaic_button_platform.c#L70-L111)。
- 说话方式是在 AI Create 界面**按住屏幕上的语音区域**，松手发送，上滑超过 72 像素取消，短于 300 ms 作废：[ai_create_app.c L24-L25、L414-L477](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/components/mosaic_ui/apps/ai_create/ai_create_app.c#L414-L477)。
- 没有唤醒词：主仓库（不含 third-party）里没有 esp-sr 依赖，也没有 WakeNet 相关代码（搜索 `wakenet`、`esp_sr`、`multinet` 无命中）。
- 官网用户指南对 AI 键只写了 "Supports custom functions."：<https://mosaico.ai/en/guide>。以上按键行为全部需真机验证。

### 2.7 设备上是不是已经装着这个固件（新发现的风险）

官网固件页目前推荐的是 "Vibe Mode v0.3.0"，并写 "After updating, visit the IDEA Center to download Mosaico Claw or other Ideas."（<https://mosaico.ai/en/firmware>）；安装页写 "To try Chat Coding, use code '100000' to install the Mosaico-Claw IDEA."（<https://mosaico.ai/en/guide/install>）。而仓库 README 说它 "also contains the source code for the ESP-MOSAICO factory firmware"。两种说法并存，**当天拿到的手表里是否已有 Mosaico-Claw：需真机验证**；没有的话要先在 Vibe Mode 连 Wi-Fi 再用代码安装。

## 3. W2 细节

### 3.1 BSP 里可直接抄的部分

| 功能 | API 和要点 | 示例与出处 |
|---|---|---|
| 录音 | `bsp_audio_codec_microphone_init()` 得到 `esp_codec_dev_handle_t`；`esp_codec_dev_open(mic, &info)` 指定格式；`esp_codec_dev_read(mic, buf, bytes)` 阻塞读 PCM；`esp_codec_dev_set_in_gain(mic, 30.0f)`。BSP 默认格式是 48000 Hz / 16 位 / 2 声道，要显式传 16000 / 16 / 1 | 16 kHz 单声道写法：[voice_wake_cmd/main/main.c L117-L141](https://github.com/esp-mosaico/esp-mosaico-bsp/blob/841f6245850e84ec210ec1818db148e9c3172e4e/examples/voice_wake_cmd/main/main.c#L117-L141)；最短闭环：[audio_loopback/main/main.c L39-L68](https://github.com/esp-mosaico/esp-mosaico-bsp/blob/841f6245850e84ec210ec1818db148e9c3172e4e/examples/audio_loopback/main/main.c#L39-L68)；默认值：[bsp/audio.h L16-L22](https://github.com/esp-mosaico/esp-mosaico-bsp/blob/841f6245850e84ec210ec1818db148e9c3172e4e/components/esp-mosaico-bsp/include/bsp/audio.h#L16-L22) |
| AI 键 | `bsp_iot_button_create(buttons, &count, BSP_BUTTON_NUM)`，再 `iot_button_register_cb(btn, BUTTON_PRESS_DOWN / BUTTON_PRESS_UP, NULL, cb, ctx)`。`BSP_BUTTON_AI_GPIO` = `GPIO_NUM_7`，低电平有效 | [button_led_test/main/main.c L74-L107、L122](https://github.com/esp-mosaico/esp-mosaico-bsp/blob/841f6245850e84ec210ec1818db148e9c3172e4e/examples/button_led_test/main/main.c#L74-L122)；[bsp/esp_mosaico.h L131-L133](https://github.com/esp-mosaico/esp-mosaico-bsp/blob/841f6245850e84ec210ec1818db148e9c3172e4e/components/esp-mosaico-bsp/include/bsp/esp_mosaico.h#L131-L140) |
| 屏幕文字 | `bsp_display_start()` → `bsp_display_lock(-1)` → `lv_label_create()` / `lv_label_set_text()` → `bsp_display_unlock()`（LVGL 9.5） | [relay_control/main/main.c L52-L53、L256-L266](https://github.com/esp-mosaico/esp-mosaico-bsp/blob/841f6245850e84ec210ec1818db148e9c3172e4e/examples/relay_control/main/main.c#L256-L266)；[bsp/display.h L95、L172-L173](https://github.com/esp-mosaico/esp-mosaico-bsp/blob/841f6245850e84ec210ec1818db148e9c3172e4e/components/esp-mosaico-bsp/include/bsp/display.h#L95) |
| 振动 | `bsp_motor_init()`、`bsp_motor_set(true/false)`、`bsp_motor_set_strength(percent)`；`BSP_MOTOR_GPIO` = `GPIO_NUM_8`，高电平有效 | [bsp/motor.h L16-L18](https://github.com/esp-mosaico/esp-mosaico-bsp/blob/841f6245850e84ec210ec1818db148e9c3172e4e/components/esp-mosaico-bsp/include/bsp/motor.h#L16-L18)；用法：[imu_gesture/main/main.c L57](https://github.com/esp-mosaico/esp-mosaico-bsp/blob/841f6245850e84ec210ec1818db148e9c3172e4e/examples/imu_gesture/main/main.c#L57) |
| 联网 | **BSP 没有 Wi-Fi STA、HTTP 客户端或 WebSocket 客户端示例**；唯一用到 Wi-Fi 的 `wifi_http_cam` 是 SoftAP 加 HTTP 服务器 | [wifi_http_cam/main/main.c L68-L80](https://github.com/esp-mosaico/esp-mosaico-bsp/blob/841f6245850e84ec210ec1818db148e9c3172e4e/examples/wifi_http_cam/main/main.c#L68-L80) |

### 3.2 把录音传到总控

- 数据量：16 kHz × 16 位 × 单声道 = 32,000 字节/秒。5 秒 160,000 字节（约 156 KiB），10 秒 320,000 字节（约 313 KiB），20 ms 一帧 640 字节。芯片有 16 MB PSRAM，整段缓存也放得下，但边录边传延迟更低。
- `esp_websocket_client`（组件 `espressif/esp_websocket_client`，当前 1.8.0，要求 IDF ≥5.0，不在 IDF 主仓库里，要在 `idf_component.yml` 里声明）：
  - 自定义头：配置项 `headers`（每项以 `\r\n` 结尾），或握手前调 `esp_websocket_client_append_header(client, "Authorization", "Bearer ...")`。
  - TLS：配置项 `crt_bundle_attach = esp_crt_bundle_attach`，需开 `MBEDTLS_CERTIFICATE_BUNDLE`。
  - 发送：`esp_websocket_client_send_bin()` 发 PCM 帧，`esp_websocket_client_send_text()` 发控制消息。
  - 出处：[esp_websocket_client.h L147-L151、L217、L285](https://github.com/espressif/esp-protocols/blob/aba9f6d12afa7ef1e7983da8b7aa957205ffa457/components/esp_websocket_client/include/esp_websocket_client.h#L147-L151)。出厂固件正是这样连 DashScope 的，可当现成范例：[asr_provider_qwen.c L576-L612](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/components/asr_service/src/asr_provider_qwen.c#L576-L612)。
- `esp_http_client` 分块 POST：`esp_http_client_open(client, -1)` 开启 `Transfer-Encoding: chunked`，每块用 `esp_http_client_chunk_write_begin()` / `esp_http_client_write()` / `esp_http_client_chunk_write_end()`。该接口在 BSP 生态锁定的提交 `7b9cc1ac` 里已存在：[esp_http_client.h L668-L714](https://github.com/espressif/esp-idf/blob/7b9cc1ac79f865983f59bb8ff3ff43eb74ff1dbe/components/esp_http_client/include/esp_http_client.h#L668-L714)。
- 结论：两种都能边录边传。总控已有带 Bearer 的 WSS，首选 WebSocket：按下时发一条开始消息，之后每 20–100 ms 发一帧二进制，松手发结束消息，总控回 `utterance` 文字给手表显示。

### 3.3 工具链（核对 01 号笔记 4.3）

- BSP 的组件清单硬性要求 `idf: ">=6.2"`：[idf_component.yml L11-L12](https://github.com/esp-mosaico/esp-mosaico-bsp/blob/841f6245850e84ec210ec1818db148e9c3172e4e/components/esp-mosaico-bsp/idf_component.yml#L11-L12)；README 同样写 "6.2 or newer"。
- 截至 2026-11-19，esp-idf 最新正式版仍是 v6.1.1，没有 v6.2 及其预发布：<https://github.com/espressif/esp-idf/releases>。
- 实际用 master。esp-mosaico-vibe 和 xiaozhi 的板型 README 仍锁定同一提交 `7b9cc1ac79f865983f59bb8ff3ff43eb74ff1dbe`（提交日期 2026-08-24，自报版本 6.2.0，能满足 `>=6.2`）：<https://raw.githubusercontent.com/esp-mosaico/esp-mosaico-vibe/main/README.md>、[version.cmake](https://github.com/espressif/esp-idf/blob/7b9cc1ac79f865983f59bb8ff3ff43eb74ff1dbe/tools/cmake/version.cmake)。**与 01 号笔记相比没有更新。**
- Windows 安装：官方推荐 ESP-IDF Installation Manager（EIM），需要 Git 和 Python 3.11 以上：<https://docs.espressif.com/projects/esp-idf/en/latest/esp32s31/get-started/windows-setup.html>。EIM 文档只说能装带标签的版本（"You can install any tagged version of ESP-IDF."），装指定 master 提交要先自己 `git clone` 并检出，再让 EIM 指向该目录（"EIM will use that repository directly"）：<https://docs.espressif.com/projects/idf-im-ui/en/latest/faq.html>、<https://docs.espressif.com/projects/idf-im-ui/en/latest/cli_installation.html>。
- **安装耗时和磁盘占用：官方文档没有给数字**（见第 6 节）。这一步必须赛前在自己的电脑上做完并实测记录。

## 4. 语音识别服务对比（价格查询日期 2026-11-19）

| 服务 | 英文 | 流式 | 单价（官方页） | 免费额度 | 开通所需 | 马来西亚 | 出处 |
|---|---|---|---|---|---|---|---|
| Deepgram Nova-3（单语） | 支持，`language` 默认 `en` | 支持，`wss://api.deepgram.com/v1/listen`，`encoding=linear16` | 流式 $0.0048/分钟（页面标注原价 $0.0077），录音文件 $0.0043/分钟，按秒计 | $200，不过期，不要信用卡 | Deepgram 账号 | 未找到官方国家清单 | <https://deepgram.com/pricing>；<https://developers.deepgram.com/reference/speech-to-text/listen-streaming> |
| OpenAI `gpt-transcribe` | 支持，`languages: ["en"]` | 文件接口可流式返回文字；持续音频要用 `gpt-live-transcribe`（$0.017/分钟） | $0.0045/分钟 | 定价页未提 | OpenAI API 账号并充值 | 支持国家列表里有 Malaysia | <https://developers.openai.com/api/docs/pricing>；<https://developers.openai.com/api/docs/guides/speech-to-text>；<https://developers.openai.com/api/docs/supported-countries> |
| OpenAI `gpt-4o-transcribe` / `whisper-1` | 支持 | 前者文件流式返回，`whisper-1` 不支持 | 均 $0.006/分钟 | 同上 | 同上 | 同上 | 同上。**官方标注二者已弃用，2027-02-26 停用** |
| Groq `whisper-large-v3-turbo` | 支持（多语种） | 文档未提流式，只有文件接口 `https://api.groq.com/openai/v1/audio/transcriptions` | $0.04/小时（约 $0.00067/分钟），每次请求最少按 10 秒计 | 有免费层（文档提到 "25 MB (free tier)"），具体限额未核实 | Groq 账号 | 未找到官方国家清单 | <https://console.groq.com/docs/speech-to-text> |
| Groq `whisper-large-v3` | 支持 | 同上 | $0.111/小时 | 同上 | 同上 | 同上 | 同上 |
| 阿里 `fun-asr-realtime` | 支持，`language_hints=["en"]` | 支持（双工 WebSocket） | 新加坡 $0.00009/秒（$0.0054/分钟）；北京 $0.000047/秒 | 新加坡 36,000 秒，90 天；北京无 | 阿里云账号并开通百炼，密钥分地域 | 未找到按国家的限制说明；新加坡地域属"国际"部署 | 见 2.1 |
| 阿里 `paraformer-realtime-v2` | 未在本次查到的页面里确认 | 支持 | 北京 $0.000035/秒 | 无 | 同上，价格页只列北京 | 同上 | <https://www.alibabacloud.com/help/en/model-studio/model-pricing> |
| 本地 faster-whisper | 支持 | 不支持（整段转写） | 免费 | 不适用 | 无，Python 3.9 以上 | 不受限 | <https://github.com/SYSTRAN/faster-whisper> |

- faster-whisper 的 CPU 延迟量级：官方基准是 `small` 模型、int8、8 线程 Intel Core i7-12700K，转写 13 分钟音频用 1 分 42 秒（约 7.6 倍实时），内存 1477 MB。按比例推算 10 秒音频约 1.3 秒，这是推算，不含模型加载；总控在 AWS 小实例上会更慢，需实测。
- 推荐：**Deepgram Nova-3 流式**。理由是原生支持 16 kHz `linear16` 流式输入，和 W2 的边录边传对得上；$200 赠金足够（10 秒一句约 $0.0008）。备选是 Groq `whisper-large-v3-turbo`：松手后把整段 WAV 一次 POST 过去，代码最少。W1 主线不需要任何识别服务账号。

## 5. 比赛当天的真机验证清单

| 编号 | 做什么 | 时间 | 通过标准 |
|---|---|---|---|
| V1 | 开机看是 Vibe Mode 还是 Mosaico-Claw；没有就连 Wi-Fi，用代码 `100000` 安装 | 10 分钟 | 能进入 AI Create 界面；记下设备 IP，浏览器能打开 `http://<IP>/` |
| V2 | 按一次 AI 键（GPIO7）、单击和长按电源键，各看反应 | 5 分钟 | 记录三种操作的实际行为；长按电源键 0.5 秒能否进 AI Create 有明确结论 |
| V3 | 网页 ASR 页把 Language Hint 改成 `en` 并保存，按住屏幕说 5 句英文指令 | 10 分钟 | 至少 4 句的屏幕文字和原话一致。不通过就换新加坡 DashScope 密钥（`static` + 新加坡端点）重测一次 |
| V4 | 网页 LLM 页选 `openai_compatible`，填总控地址、Bearer 令牌，保存后重启，说一句话 | 15 分钟 | 总控日志出现 `POST /v1/chat/completions`，`Authorization` 正确，最后一条 user 消息含该句；手表显示总控返回的短句；Agora 对话里出现这句话 |
| V5 | 连说 5 句，在总控日志里数请求 | 10 分钟 | 每句对应的用户请求数为 1；额外请求（记忆提取等）都能被过滤规则认出；记录松手到总控收到的秒数 |
| V6 | 连续说 20 句，观察试用服务 | 10 分钟 | 没有出现密钥交换失败或额度类报错；出现则记下第几句和报错原文 |
| V7 | （W2）编译并烧录 BSP `button_led_test` | 15 分钟 | 串口日志在按下和松开 AI 键时分别打印 `AI: BUTTON_PRESS_DOWN` 和 `AI: BUTTON_PRESS_UP` |
| V8 | （W2）烧录自写固件，按住 AI 键说 5 秒 | 15 分钟 | 总控收到的字节数在 160,000 的 ±10% 内；回放录音能听清；识别文字正确；记录松手到出字的秒数 |
| V9 | （W2）刷回官方固件 | 10 分钟 | 按 BOOT 加电源键进下载模式，用 <https://mosaico.ai/en/firmware> 刷回 Vibe Mode 后能正常开机 |

顺序：V1 → V2 → V3 → V4 → V5。前五项通过就走 W1，V7–V9 只在 W1 走不通时做。

## 6. 未能核实

- 试用服务（`as.esp-claw.com`）的额度、有效期、是否支持英文、是否对地区限流：只读了设备端源码，服务端没有公开文档；该组件没有 README。
- 当天设备里预装的是什么固件，以及 Mosaico-Claw 作为 IDEA 安装后网页配置是否和源码一致：官网和仓库 README 说法不同（2.7）。
- 设备网页配置是否有访问限制：`http_server_core.c` 里没看到鉴权代码，但没有逐个处理函数读完。
- 记忆自动提取请求的确切提示词、触发时机和期望返回格式；`llm_supports_tools=false` 时上层是否仍会带工具（2.3）。
- Lua 音频模块在 Mosaico 构建里是否启用：板级默认配置里相关行被注释（[sdkconfig.defaults.board L44-L47](https://github.com/esp-mosaico/esp-mosaico-claw/blob/8b48039d83d03067757cd6629847d9f2f1040844/boards/esp_mosaico/sdkconfig.defaults.board#L44-L47)），Kconfig 默认值又依赖另一个开关，没有推到底。即使启用，`http_request` 的 `body` 只接受字符串，没有上传文件的参数。
- ESP-IDF 在 Windows 上的安装耗时和磁盘占用：查了 Windows 安装页、EIM 首页、FAQ、命令行安装页，都没有数字。
- 用 `idf.py flash` 直接烧 BSP 应用后，Vibe Mode 是否被覆盖、如何恢复：BSP README 只给了烧录命令；esp-mosaico-utils README 只列出 `python mosaico.py recover --source reviewed`，没有说明前因后果。
- 马来西亚能否注册并使用 Deepgram、Groq、阿里云百炼国际站：三家都没找到按国家列出的可用性页面。只有 OpenAI 的支持国家列表明确包含 Malaysia。
- Groq 免费层的 Whisper 限额：限速页给出 RPM 20、RPD 2K、每小时 7.2K 音频秒、每天 28.8K 音频秒，但页面说明这是 Developer 计划的基础限额，免费层数值要登录后在账号设置里看（<https://console.groq.com/docs/rate-limits>）。
- Deepgram 流式鉴权头的确切格式：参考页只写了 `Authorization` 头，没有给出前缀写法。
- `paraformer-realtime-v2` 是否支持英文、国际站是否提供：本次只看到北京地域的价格行。
- xiaozhi 兜底（一句话）：设备把 Opus 音频发给小智服务端，识别在服务端做，服务端只回一条 `{"type":"stt","text":"..."}` 给设备显示（<https://raw.githubusercontent.com/78/xiaozhi-esp32/main/docs/websocket.md>），所以**固件本身不能把文字转给第三方，要转发只能自建服务端并在服务端改**；板型 README 没有提这件事。
