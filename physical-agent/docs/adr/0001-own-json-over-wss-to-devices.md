# 总控与设备之间用自有的 JSON-over-WSS，不用 MCP 或 A2A

设备（电脑、手表、唤醒器）都在 NAT 后面，只能主动连出去；MCP 和 A2A 的标准绑定都要求被调用的一方能被访问到，A2A 的推送也是反向 webhook。所以总控对设备一侧用自己的 JSON-over-WSS（设备主动外连，身份由已认证的连接决定），消息形状照 A2A Task 的状态和事件来设计，日后要对外互通时在总控上加 A2A 服务端即可。总控对语音助手一侧仍然用 MCP。

依据见 [03 号调研 1.4 节](../research/03-agent-orchestration-memory.md)。
