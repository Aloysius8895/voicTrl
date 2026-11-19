# 04 · 在 VS Code 的 Claude Code 面板里展示 `claude -p` 生成网页的那段对话：调研

- 调研日期：2026-11-18
- 方法：只采用一手来源，包括 code.claude.com 官方文档、code.visualstudio.com 官方文档、本机 `claude --help` / `code --help` 的输出、本机 `~/.claude` 下 CLI 写入的文件，以及本机已安装扩展自带的 `package.json` 和 `extension.js`。读 `~/.claude` 时只看元数据（目录名、文件名、大小、条目类型、`entrypoint`/`cwd`/`version` 字段），没有读取或摘录任何对话内容。没有启动 VS Code，也没有运行任何会调用模型的命令。
- 本机只读核对结果：`claude --version` 为 `2.1.322 (Claude Code)`；`code --version` 为 `1.146.0`；已安装扩展 `anthropic.claude-code-2.1.327-win32-x64`（同时残留一个 2.1.326 目录）；系统为 Windows 11 Home Single Language。
- 标注约定：**[文档]** 指官方文档原文；**[本机]** 指本机命令输出或文件元数据；**[扩展源码]** 指本机已安装扩展的压缩代码（不是文档承诺，版本一变就可能不同）；**[推导]** 指由前面几条事实推出、还没有实测的结论。

---

## 结论

### 在 B 上（`claude -p` 就在这台机器上跑过）

**有文档依据，大概率可行，但最关键的一环需要实机验证。**

- 有文档保证的部分：
  - `claude -p` 默认把会话保存到磁盘。
  - CLI 和扩展共用同一份会话历史。
  - 扩展的 URI `vscode://anthropic.claude-code/open?session=<id>` 会打开一个 Claude Code 标签页，并恢复"VS Code 当前打开的文件夹"下的指定会话。
- 文档没写清楚的部分：扩展面板能否打开由 `claude -p` 创建的会话。这类会话在 transcript 里记为 `entrypoint: "sdk-cli"`。
  - 文档只在 `claudeProcessWrapper` 那一条里提到：2.1.304 起，列表会包含 "sessions that `claude -p` or the Agent SDK started in this workspace"。
  - CLI 的会话选择器明确把 `-p` 会话排除在外。
  - 扩展源码里也有一段"按 entrypoint 排除 SDK 会话"的判断，并且受某个开关控制。
  - 所以 URI 能否打开 `-p` 会话，必须实测。打不开时，按文档行为会退化成一个新的空对话。
- 有文档保证的后备方案：在 VS Code 集成终端里运行 `claude --resume <session-id>`。对话会显示在终端里，不在图形面板里。

### 在 A 上（只拿到工作区副本）

**文档没有覆盖"把会话复制到另一台机器"这种用法。**

- 按文档的存储规则可以这样尝试，但没有实测，也没有文档承诺 [推导]：
  1. 让 A 上的工作区绝对路径与 B 完全相同。
  2. 把 B 上的 `<session-id>.jsonl`（以及同名子目录，如果有）复制到 A 的 `%USERPROFILE%\.claude\projects\<同样编码的目录名>\`。
  3. 再用同一个 URI 打开。
- 有文档保证的后备方案：把 `.jsonl` 带到 A 的任意位置，在集成终端运行 `claude --resume "<.jsonl 的绝对路径>"`。

### 推荐命令（PowerShell，B 上）

```powershell
# 1) device agent 生成网页。不要加 --no-session-persistence，也不要设置 CLAUDE_CODE_SKIP_PROMPT_HISTORY
$sid = [guid]::NewGuid().ToString()
Set-Location "C:\demo\ws-001"      # 示例路径
claude -p "<prompt>" --session-id $sid --output-format stream-json --verbose --permission-mode acceptEdits
#    也可以不传 --session-id，改为从 stream-json 的 system/init 事件或最后的 result 事件里读 session_id

# 2) 等上面的进程退出后，再打开工作区（工作区必须是 VS Code 信任的文件夹，见关键事实 A7）
code "C:\demo\ws-001"

# 3) 等这个窗口拿到焦点、扩展激活后，再发 URI
Start-Process "vscode://anthropic.claude-code/open?session=$sid"

# 后备：在该窗口的集成终端（Ctrl+`）里运行
claude --resume $sid
```

`-p` 和 `--session-id` 同时使用，文档没有给出示例，见"需要实机验证"第 1 步。

---

## 关键事实

### A. 扩展的 URI handler

1. **[文档]** 扩展在 `vscode://anthropic.claude-code/open` 注册了 URI handler，作用是"open a new Claude Code tab"。"If VS Code isn't already running, opening the URL launches it first. If VS Code is already running, the URL opens in whichever window is currently focused."
   来源：https://code.claude.com/docs/en/vs-code （"Launch a VS Code tab from other tools"）
2. **[文档]** 在 Windows 上的调用方式：
   - PowerShell：`Start-Process "vscode://anthropic.claude-code/open"`
   - `cmd.exe`：`start "" "vscode://anthropic.claude-code/open"`（第一个带引号的参数会被当作窗口标题，所以要先给一个空标题）

   来源：同上
3. **[文档]** 文档只列了两个可选参数：
   - `prompt`："Text to pre-fill in the prompt box. Must be URL-encoded. The prompt is pre-filled but not submitted automatically."
   - `session`："ID of a session to resume, from the folder open in VS Code. With Claude Code v2.1.300 or later, a session from the main checkout or a worktree of that folder's repository also resumes. If the session isn't found, a fresh conversation starts instead. If the session is already open in a tab, that tab is focused."
   - 文档没有说两个参数能否同时使用，也没有说在空窗口（没有打开文件夹）时会怎样。

   来源：同上
4. **[本机] `code --open-url` 不是文档化的用法**：`code --help`（1.146.0）没有列出它，VS Code 命令行文档也没有这个选项。不过本机注册表里 `vscode://` 协议的处理命令是 `"C:\Users\User\AppData\Local\Programs\Microsoft VS Code\Code.exe" --open-url -- "%1"`，也就是说 `Start-Process "vscode://..."` 最终就是走这条路径。**建议直接用文档写明的 `Start-Process`。**
   来源：本机 `code --help`；本机注册表 `HKCU:\Software\Classes\vscode\shell\open\command`；https://code.visualstudio.com/docs/configure/command-line （扩展 URL 的格式为 `vscode://{publisher}.{extensionName}/{path}?{query}`）
5. **[扩展源码]**（`extension.js`，v2.1.327，压缩代码）
   - `/open` 分支读取 `session` 和 `prompt` 两个参数。
   - 如果给了 `session` 但格式校验不通过，会直接 `return`，不打开任何标签页。校验的具体规则没能从压缩代码里确认，所以应传 CLI 给出的完整 UUID。
   - 校验通过后，执行命令 `claude-vscode.primaryEditor.open`（命令面板标题为 "Claude Code: Open in Primary Editor"），并把两个参数一起传进去。

   来源：`%USERPROFILE%\.vscode\extensions\anthropic.claude-code-2.1.327-win32-x64\extension.js` 和 `package.json`
6. **[扩展源码]** 扩展的 `activationEvents` 包括 `onStartupFinished`，`engines.vscode` 为 `^1.94.0`。文档的 Prerequisites 也写的是 "VS Code 1.94.0 or later"。
   来源：同上 `package.json`；https://code.claude.com/docs/en/vs-code
7. **[扩展源码 + 文档] 扩展只在受信任的工作区里运行**：
   - `package.json` 中 `capabilities.untrustedWorkspaces.supported = false`，说明为 "Claude Code can run commands and use settings from this folder, so it stays off until you trust the folder."
   - VS Code 文档："extensions that have not explicitly opted into Workspace Trust are disabled by default in Restricted Mode"。
   - 把父文件夹加入 **Trusted Folders & Workspaces** 列表后，它的子文件夹也算受信任。
   - **对演示的影响**：每次生成的都是新工作区文件夹，应事先把它们的公共父目录（例如 `C:\demo`）设为受信任，否则面板不会启动，URI 也不会被处理。

   来源：同上 `package.json`；https://code.visualstudio.com/docs/editing/workspaces/workspace-trust
8. **[文档 + 本机] CLI 自己的 `claude-cli://` 深链接没有恢复会话的参数**：
   - 只有 `q`、`cwd`、`repo` 三个参数，打开的是一个新的终端窗口，不是 VS Code 面板。
   - 注册表位置为 `HKEY_CURRENT_USER\Software\Classes\claude-cli`。本机已注册，处理命令为 `"C:\Users\User\.local\bin\claude.exe" --handle-uri "%1"`。

   来源：https://code.claude.com/docs/en/deep-links ；本机注册表

### B. `claude -p` 的会话能否保存，以及会话 ID

1. **[文档 + 本机] `-p` 默认保存会话**：
   - `--no-session-persistence` 的说明是 "Disable session persistence so sessions are not saved to disk and cannot be resumed. Print mode only."
   - 环境变量 `CLAUDE_CODE_SKIP_PROMPT_HISTORY` 在任何模式下都有同样效果。
   - Agent SDK 的 `persistSession` 默认值为 `true`。

   来源：本机 `claude --help`；https://code.claude.com/docs/en/cli-reference ；https://code.claude.com/docs/en/sessions ；https://code.claude.com/docs/en/agent-sdk/typescript
2. **[文档] 可以事先指定会话 ID**：
   - `--session-id <uuid>`："Use a specific session ID for the conversation (must be a valid UUID)"。
   - SDK 选项 `sessionId`："Use a specific UUID for the session instead of auto-generating one"。
   - 文档没有给出与 `-p` 组合使用的示例。

   来源：本机 `claude --help`；https://code.claude.com/docs/en/cli-reference ；https://code.claude.com/docs/en/agent-sdk/typescript
3. **[文档] 也可以事后从输出里拿到 ID**：
   - `system`/`init` 消息（`SDKSystemMessage`）带有 `session_id` 和 `cwd`。
   - 最后的 `result` 消息（`SDKResultMessage`）带有 `session_id`。
   - headless 文档示例：`claude -p "Start a review" --output-format json | jq -r '.session_id'`。

   来源：https://code.claude.com/docs/en/agent-sdk/typescript ；https://code.claude.com/docs/en/headless
4. **[文档] 存储位置**：
   - 文件路径为 `~/.claude/projects/<project>/<session-id>.jsonl`，其中 `<project>` 是 "your working directory path with non-alphanumeric characters replaced by `-`"。转换后超过 200 个字符时，会截断并附加哈希。
   - 在 Windows 上，`~/.claude` 就是 `%USERPROFILE%\.claude`。设置 `CLAUDE_CONFIG_DIR` 后，整个目录会搬到那里。
   - 同一会话的附属数据：`projects/<project>/<session>/subagents/`、`projects/<project>/<session>/tool-results/`、`file-history/<session>/`。
   - 默认保留 30 天（`cleanupPeriodDays`）。transcript 是明文，里面还包含系统提示词、工具定义等内容。

   来源：https://code.claude.com/docs/en/sessions ；https://code.claude.com/docs/en/claude-directory
5. **[本机，仅元数据] 本机实际情况**：
   - **路径编码与文档一致**：VS Code 打开 `c:\maven\voicTrl` 后，会话存放在 `C:\Users\User\.claude\projects\c--maven-voicTrl\`。另一个例子 `...\Hackathon_map\business-app\.cli-workspace` 对应目录 `C--maven-Hackathon-map-business-app--cli-workspace`，可以看到 `:`、`\`、`_`、`.` 都变成了 `-`。
   - **CLI、`-p` 和扩展的会话放在同一棵目录树下**：transcript 每行都有 `entrypoint` 字段。本机统计结果是：扩展会话为 `claude-vscode`，交互式终端会话为 `cli`，`claude -p` 会话为 `sdk-cli`。
     - 唯一一个 `sdk-cli` 会话位于 `projects\C--Users-User-AppData-Local-Temp\4d959ee8-….jsonl`。它的 `cwd` 为 `C:\Users\User\AppData\Local\Temp`，`version` 为 `2.1.143`，`sessionId` 与文件名相同。
   - **盘符大小写随启动方式不同**：扩展会话的目录都以小写 `c--` 开头（扩展记录的 `cwd` 是 `c:\...`），终端或脚本启动的会话目录以大写 `C--` 开头。NTFS 默认不区分大小写，所以很可能落在同一个目录里，但扩展查找会话时是否区分大小写，没有核实。
   - **`--no-session-persistence` 会让对话无法展示**：本机另一个项目用 `--no-session-persistence` 调用 `claude -p`（见 `C:\maven\business_agent\business\agents\providers\claude.ts`）。它对应的项目目录里有 68 个 `.jsonl`，大小在 105 到 149 字节之间，内容只有 `ai-title` 条目，没有任何消息。这和文档"不保存、不能恢复"的说法一致。注意：这些文件和这个开关之间的对应关系，是根据代码和目录名推断的。
6. **[文档] CLI 和扩展共用历史**：
   - "The extension and CLI share the same conversation history. To continue an extension conversation in the CLI, run `claude --resume`"。
   - 另一页的说法是 "the VS Code extension ... keep their own session list"，指的是各自有一份列表界面。

   来源：https://code.claude.com/docs/en/vs-code （"Switch between extension and CLI"）；https://code.claude.com/docs/en/sessions
7. **[文档] 会话按目录归属**：
   - "A session is a saved conversation tied to a project directory"，"Claude Code stores sessions per project directory"。
   - URI 的 `session` 参数指的是 "from the folder open in VS Code"。
   - 扩展列表那条说明里写的也是 "started in this workspace"。
   - **[推导]** 所以 VS Code 打开的文件夹必须正好是 `claude -p` 当时的 cwd。

   来源：https://code.claude.com/docs/en/sessions ；https://code.claude.com/docs/en/vs-code
8. **[文档] CLI 对 `-p` 会话的处理**：
   - "Claude Code leaves sessions created with `claude -p` or the Agent SDK out of the session picker and out of `claude --continue`. You can still resume one by passing its session ID to `claude --resume <session-id>`."
   - `claude --resume <id>` 可以在任意目录运行：先查当前项目，再查本机所有项目。
   - 也可以直接传 `.jsonl` 的绝对路径。

   来源：https://code.claude.com/docs/en/sessions ；https://code.claude.com/docs/en/cli-reference
9. **扩展面板对 `-p` 会话的处理：文档说得不清楚**
   - **[文档]** 原文只有一条："Conversations missing with `claudeProcessWrapper` set: update the extension to version 2.1.304 or later. The list then includes the conversations that were missing, along with sessions that `claude -p` or the Agent SDK started in this workspace." 这句话只出现在 `claudeProcessWrapper` 的上下文里，没有说明不设这个选项时 `-p` 会话是否出现在列表里。
   - **[扩展源码]** 扩展列出会话的函数里有这样一个判断：当某个布尔参数为假时，跳过 `entrypoint` 属于 `sdk-cli`/`sdk-ts`/`sdk-py`、或 `sessionKind` 为 `daemon` 的 transcript。这个参数由什么决定、URI 按 ID 打开时是否也经过这个判断，压缩代码里都看不出来。

   来源：https://code.claude.com/docs/en/vs-code ；本机 `extension.js`
10. **[文档] 打开时机与表现**：
    - 如果另一个 Claude 进程还开着这段对话，面板会显示 "This conversation is still open somewhere else…"，需要点 **Open here anyway**。所以应等 `claude -p` 进程退出后再打开。
    - 文档还说明，同一会话被两个进程同时写入时，"messages from one of them can be missing"。
    - 恢复的对话一开始可能是空白的，最多等 20 秒才显示（期间显示 `Waiting for your plugins…`）。

    来源：https://code.claude.com/docs/en/vs-code ；https://code.claude.com/docs/en/sessions
11. **[文档] 只打开、不发送，就不会消耗额度**：
    - URI 的 `prompt` 只预填，不提交。
    - CLI 恢复长对话时可能弹出 "Resume this conversation?"，文档说 "The estimated use comes when you send your first message after **Resume**, not when you select it."

    来源：https://code.claude.com/docs/en/vs-code ；https://code.claude.com/docs/en/sessions

### C. 复制到 A 机

1. **[文档] 文档没有讲"跨机器迁移会话"。** 能找到的相关规则有三条：
   - 存储路径和目录名编码规则，见 B4。
   - `--resume` 可以直接接 `.jsonl` 的绝对路径。
   - 按 ID 跨项目查找时，"resolves the ID only when exactly one other project holds a transcript with messages for it, so a hand-copied duplicate makes Claude Code report not-found"。也就是说，在同一台机器上手动复制出多份，会导致按 ID 查不到。

   来源：https://code.claude.com/docs/en/sessions
2. **[推导，未实测]** 想让 A 上的扩展面板显示这段对话，比较稳妥的尝试方式是：
   - A 上工作区的绝对路径与 B 完全一致（例如两台都是 `C:\demo\ws-001`），这样目录名编码和 transcript 内记录的 `cwd` 都一致。
   - 把 `<id>.jsonl` 和同名子目录复制到 A 的 `%USERPROFILE%\.claude\projects\C--demo-ws-001\`。
   - 如果路径不一致，transcript 里记录的 `cwd` 仍然是 B 的路径，扩展会怎样处理，完全没有依据。
3. **[文档] 隐私方面**：transcript 是明文，"Anything that passes through a tool is written to a transcript on disk"，还包含系统提示词和工具定义。复制到 A 就等于把这些内容一起带过去。
   来源：https://code.claude.com/docs/en/claude-directory

### D. 其他展示方式（有文档）

1. **集成终端 + `claude --resume <id>`**：
   - 按 `` Ctrl+` `` 打开集成终端后运行 `claude`。前提是装了独立版 CLI（"Installing the extension does not put `claude` on your shell PATH"）。
   - 在集成终端里启动时，CLI 会自动连接扩展，可以用 diff 查看等功能。
   - 对话显示在终端里，不在图形面板里。

   来源：https://code.claude.com/docs/en/vs-code （"Run CLI in VS Code"）；https://code.claude.com/docs/en/sessions
2. **`--resume <transcript-path>`**：可以直接传 `.jsonl` 的绝对路径，适合 A 机。
   来源：https://code.claude.com/docs/en/cli-reference ；https://code.claude.com/docs/en/sessions
3. **`--fork-session`**："When resuming, create a new session ID instead of reusing the original (use with `--resume` or `--continue`)"。可以在不写入原会话的情况下展示或续聊，但不改变对话显示在哪里。
   来源：本机 `claude --help`；https://code.claude.com/docs/en/cli-reference
4. **`--ide`**："Automatically connect to IDE on startup if exactly one valid IDE is available"。它只负责把 CLI 连接到 IDE（diff 查看、诊断共享），**不会**把对话放进面板。
   来源：本机 `claude --help`；https://code.claude.com/docs/en/cli-reference ；https://code.claude.com/docs/en/vs-code
5. **扩展的终端模式**：设置 `claudeCode.useTerminal`，或命令 "Claude Code: Open in Terminal"。URI 的 `session` 参数在终端模式下是否生效，文档没有说明。
   来源：https://code.claude.com/docs/en/vs-code ；本机 `package.json`
6. **打开文件夹时自动在终端里恢复会话**：VS Code 任务支持 `"runOptions": { "runOn": "folderOpen" }`，可以用它在打开文件夹时自动运行 `claude --resume <id>`。条件如下：
   - `task.allowAutomaticTasks` 默认为 `off`，第一次会弹窗询问是否允许。
   - "Automatic tasks never run in an untrusted workspace"。
   - 这是 VS Code 的功能，和 Claude 组合使用的效果没有实测。

   来源：https://code.visualstudio.com/docs/debugtest/tasks
7. **Claude Desktop（不是 VS Code）**：`claude --desktop --resume <session-id>` 会在 Desktop 应用里打开该会话。适用于 macOS 和 x64 Windows，需要登录 Claude 订阅，要求 v2.1.285 及以上。`-p` 会话能否在 Desktop 里打开，没有核实。
   来源：https://code.claude.com/docs/en/cli-reference

---

## 需要实机验证

1. **B：确认 `-p` 加 `--session-id` 能落盘**
   - 在新目录 `C:\demo\t1` 里运行一次极短的 `claude -p "say hi" --session-id <uuid> --output-format stream-json --verbose`。这一步会调用模型。
   - 检查 `system/init` 事件里的 `session_id` 是否等于 `<uuid>`。
   - 检查 `%USERPROFILE%\.claude\projects\C--demo-t1\<uuid>.jsonl` 是否存在，并且 `entrypoint` 为 `sdk-cli`。
2. **B：确认 URI 能打开 `-p` 会话（最关键）**
   - 进程退出后，先在 VS Code 里把 `C:\demo` 加为受信任文件夹。
   - 运行 `code "C:\demo\t1"`，等窗口拿到焦点后，运行 `Start-Process "vscode://anthropic.claude-code/open?session=<uuid>"`。
   - 判断方法：标签页里出现历史消息（可能先空白，最多 20 秒）就是成功；如果是一个空的新对话，说明没找到或被过滤了。
   - 同时看一下 Session history 列表里有没有这条会话。
   - 如果失败，在 VS Code 里打开 `C:\demo\t1`（盘符为小写 `c:`）再试一次，排除盘符大小写的影响。
3. **B：后备方案**
   - 在同一窗口的集成终端里运行 `claude --resume <uuid>`，确认历史正常显示，并且不输入就不会发出请求。
   - 可选：试 `claude --resume <uuid> --fork-session`，看分叉出的新会话是否会出现在面板列表里。
4. **A：跨机展示**
   - 把工作区复制到 A 上相同的绝对路径 `C:\demo\t1`，把 `<uuid>.jsonl`（和同名目录，如果有）复制到 A 的 `%USERPROFILE%\.claude\projects\C--demo-t1\`，然后重复第 2 步。
   - 如果失败，改用 `claude --resume "<A 上 .jsonl 的绝对路径>"`。
   - 同时记录 A 上没有登录时能否只显示历史。

---

## 未能核实

- 扩展面板或 URI 能否打开 `entrypoint: "sdk-cli"` 的会话：文档只在 `claudeProcessWrapper` 那一条里间接提到，扩展源码里有受开关控制的过滤逻辑，结论只能靠实测。
- `prompt` 与 `session` 能否同时使用：文档没写，扩展源码会把两者一起传给打开命令，但效果未测。
- 在空窗口（没有打开文件夹）里调用带 `session` 的 URI 会怎样：文档没写。
- `code --open-url`：没有任何文档。只知道它是本机注册表里 `vscode://` 协议的处理命令。
- 会话复制到另一台机器或另一个路径后，扩展能否识别；transcript 内 `cwd` 不一致时会怎样：文档没有覆盖。
- 盘符大小写（`c--` 与 `C--`）是否影响扩展查找会话。
- `-n/--name` 能否给 `-p` 会话起一个在列表里显示的名字：没有查证。
- A 机没有登录 Claude 时，扩展或 CLI 能否只展示历史。
- "Resume this conversation?" 对话框会不会出现在 VS Code 面板里：文档只描述了 CLI 的情况。
- 扩展面板打开一个 Claude Code 尚未"信任"的文件夹（`-p` 会跳过信任对话框）时，会不会弹出 Claude 自己的信任提示。
- Desktop 文档的 "Coming from the CLI" 一节因页面过长没有读到，Desktop 能否打开 `-p` 会话未知。

---

## 来源清单

- https://code.claude.com/docs/en/vs-code
- https://code.claude.com/docs/en/sessions
- https://code.claude.com/docs/en/headless
- https://code.claude.com/docs/en/cli-reference
- https://code.claude.com/docs/en/claude-directory
- https://code.claude.com/docs/en/deep-links
- https://code.claude.com/docs/en/agent-sdk/typescript
- https://code.visualstudio.com/docs/configure/command-line
- https://code.visualstudio.com/docs/editing/workspaces/workspace-trust
- https://code.visualstudio.com/docs/debugtest/tasks
- 本机：`claude --version` / `claude --help`（2.1.322）；`code --version` / `code --help`（1.146.0）；注册表 `HKCU:\Software\Classes\vscode\shell\open\command` 与 `HKCU:\Software\Classes\claude-cli\shell\open\command`；`C:\Users\User\.claude\projects\` 的目录与 transcript 元数据；`C:\Users\User\.vscode\extensions\anthropic.claude-code-2.1.327-win32-x64\package.json` 与 `extension.js`
