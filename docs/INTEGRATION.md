# 数据与接口：接入自己的 AI

本项目的接口有两层：

1. **模型接口**：机器人向你配置的OpenAI兼容Chat Completions地址发请求。最简单的模型替换只需要改config.json。
2. **桌面JSON桥接**：`bridge.py` 让其他程序读取会话、构建prompt、发送或确认不回复。它是本机命令行，不是HTTP服务器，也不是QQ官方协议API。

## 能提供哪些数据

| 字段/文件 | 含义与边界 |
| --- | --- |
| target.kind / target.id / target.name | 你配置并核验的群/个人类型、号码和显示名称 |
| scope | `group_123456789` 或 `private_123456789`，同号码不同类型也隔离 |
| id | 本项目本地去重ID，例如uia-开头的随机ID；不是QQ服务器消息ID |
| sender | 界面显示的发言人昵称，不保证取得其QQ号或真实身份 |
| self | 是否识别为机器人自己；依赖界面属性及self_names配置 |
| time | 首次观察时间，不是QQ原始发送时间 |
| body | 当前界面取得的文字，图片通常是占位，可能含引用/表情文字；不是完整消息协议 |
| image_count | 本条检测到的图片节点数量 |
| image_refs | 当前UIA图片节点的runtime_id引用，可能过期，不是图片文件路径 |
| images | 已采集到本机的JPEG路径；可能为空，不能据此猜测图片内容 |
| pending_ids | 尚未处理的非自身消息ID；多条可以合成一次接话 |
| delivery / created_at | 本机发送尝试的状态与时间；uncertain不代表一定失败 |
| baseline | 第一次读取或旧消息对齐失败时建立新基线，不把整屏历史当新消息 |

示例（全部为虚构数据）：

```json
{
  "schema_version": 1,
  "scope": "group_123456789",
  "target": {"kind": "group", "id": "123456789", "name": "测试群", "enabled": true},
  "baseline": false,
  "timestamp_semantics": "first_observed_not_original_send_time",
  "pending_ids": ["uia-demo-2"],
  "messages": [{
    "id": "uia-demo-2",
    "time": "2026-01-01 12:00:00",
    "sender": "测试群友",
    "self": false,
    "body": "这图是不是在演我？[图片，尚未获取内容]",
    "image_count": 1,
    "image_refs": [{"runtime_id": "42,100,200"}],
    "images": ["conversations/group_123456789/captured-images/本地消息哈希.jpg"],
    "vision_mode": "native"
  }]
}
```

这些是QQ当前已加载的会话信息。不能保证全量历史、所有后台群实时消息、原图路径、视频/音频、撤回前内容、精确QQ消息时间或真正的发言人QQ号。忙群刷出可见历史且没有唯一重叠时会重新建基线，可能漏消息。

## 直接替换模型

推荐先用model-settings.cmd填写地址和Key、获取模型列表并选档位；手动配置仍支持以下字段。详见[设置窗口](MODEL_SETTINGS.md)。

```json
{
  "endpoint": "https://api.example.com/v1/chat/completions",
  "model": "your-model",
  "api_key_env": "QQ_BOT_API_KEY",
  "self_names": ["你当前的QQ昵称"],
  "persona": "personality.md",
  "slang": "internet-slang.md",
  "temperature": 0.7,
  "output_token_parameter": "max_tokens",
  "send_reasoning_parameters": false,
  "check_models": true,
  "trust_env": false,
  "vision": {"enabled": true, "mode": "native"}
}
```

这是字段节选，请以完整config.example.json为基础。只会发一个模型请求，不再先找千问生成图片描述。纯文本模型关闭vision.enabled。图像模型需接受 `image_url` 的data URL；如果服务有自己的格式，需在runtime.chat_payload或外部适配器中转换，不能只把接口地址改成Responses等不兼容端点。

设置窗口保存的Key优先从api_key_file指定的DPAPI文件解密；否则按api_key_env读取进程环境，Windows再回读当前用户Environment项。密钥绑定API地址，不输出到prompt或JSON桥接结果。

兼容字段：
- 常规请求：model、messages、max_tokens、temperature。
- 服务要求时可选 `output_token_parameter: "max_completion_tokens"`。
- `temperature: null` 表示不发temperature。
- reasoning_api可选off（不发送）、effort（仅reasoning_effort）、strata（程度＋非关闭档的预算）。旧send_reasoning_parameters只在没有reasoning_api时用于兼容。
- reasoning.mode为fixed时固定default档位，auto时允许复杂问题提高。none/low/medium/high及预算可在窗口设置；服务是否支持对应取值以其文档为准。
- doctor默认检查GET /models及model名称；服务没有此接口时设check_models=false。跳过检查不等于服务一定可用。
- trust_env=false使聊天请求不自动走环境代理；确需代理时显式设true。
- 生成截断、空回复、超过max_reply_chars、错误的静默标记均不发送。

请求示例：

```json
{
  "model": "your-model",
  "temperature": 0.7,
  "max_tokens": 1152,
  "messages": [
    {"role": "system", "content": "人格、词典、当前会话与接话规则"},
    {"role": "assistant", "content": "先把我饭还回来。"},
    {"role": "user", "content": [
      {"type": "text", "text": "【本轮新消息】[2026-01-01 12:00:00] 测试群友：这图是不是在演我？"},
      {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
    ]}
  ]
}
```

服务应返回：

```json
{"choices":[{"finish_reason":"stop","message":{"role":"assistant","content":"演你都不用写剧本。"}}]}
```

人物、图中文字、昵称、群聊内容都是被观察数据，不能覆盖system指令。原生图片每轮最多一张最近相关图片，失败新图不借旧图。历史Qwen文字描述不会进入原生prompt。图片Base64只存在于请求中，不写入聊天记忆。

### 不回复

在有新图片的场景，模型可只返回内部 `<NO_REPLY>`。机器人将它解释为“这一批已处理但不发言”，从pending移除，保留上下文及图片摘要；不会把标记发送到QQ。这不是HTTP204，也不需要返回JSON工具调用。

外部AI自行判断不回复时，用下面的ack命令处理指定ID。不要把空回复或内部标记传给send。

## JSON命令行桥接

从仓库目录用 `.venv\Scripts\python.exe bridge.py ...` 调用。read/send/ack要求桌面没有被本项目或旧版机器人占用；先stop.cmd。桥接独占操作期间仍响应F8，命令结束恢复先前STOP状态，不会偷偷启动bot。

```powershell
# 列出已配置对象，不操作QQ
.\.venv\Scripts\python.exe bridge.py targets

# 读取并合并群消息；首次/重建基线时pending为空
.\.venv\Scripts\python.exe bridge.py read --scope group_123456789

# 同时采集最近待处理图片，需要原生图片配置
.\.venv\Scripts\python.exe bridge.py read --scope group_123456789 --images

# 根据已保存的此会话记忆，输出可直接POST给模型的JSON请求体
.\.venv\Scripts\python.exe bridge.py prompt --scope group_123456789

# 明确发送回复，指明本次回答了哪些pending ID
.\.venv\Scripts\python.exe bridge.py send --scope group_123456789 --reply-to uia-demo-2 --text '演你都不用写剧本。'

# 决定不回复，处理对应pending
.\.venv\Scripts\python.exe bridge.py ack --scope group_123456789 --ids uia-demo-2
```

send依旧执行目标核验、草稿保护、粘贴核验、点击前记账和回读；不是直接往任意QQ号发协议包。scope必须已经存在于targets.json，不能由模型随意拼一个号码绕过监听名单。

成功发送：
```json
{"ok":true,"scope":"group_123456789","delivery":"confirmed","text":"演你都不用写剧本。","reply_to":["uia-demo-2"]}
```

如果已尝试点击但回读失败：
```json
{"ok":false,"scope":"group_123456789","delivery":"uncertain","retry_safe":false,"error":"..."}
```

退出码0成功、1配置/占用等错误、2发送或回读失败。uncertain可能实际已送达，**不要自动重试**。`retry_safe: true` 只表示本次没有到达记录发送尝试的点击边界，仍需核对窗口/草稿与目标后决定。send不传reply-to时作为额外手工消息发送，不消耗pending。

## 外部AI最小循环

仓库中 [examples/external_ai.py](../examples/external_ai.py) 是一个单轮适配示例。它读取一次QQ、将prompt发到你的API、选择send或ack，不启动持续循环：

```powershell
.\stop.cmd
.\.venv\Scripts\python.exe examples\external_ai.py --scope group_123456789 --images
```

它使用当前config.json的endpoint、model和api_key_env。运行前先通过管理器添加并核验会话，并单独启动本地模型（若使用本地路线）。第一次只有baseline时不会调用模型。示例只处理本次读取的pending，不把模型回复后的新消息一起清掉。

同一QQ桌面只能由一个控制器操作。外部程序若需要常驻，多次调用时自行安排轮询/冷却与错误处理，不能同时启动bot.py。

## 存储和容量

每个会话默认保留60条上下文、4000个去重ID、200个pending ID，采集图片最多32张，图片摘要哈希最多32个。日志约2MiB轮转并保留3个旧文件；reset只保留最近3份带标记备份。会话数量和诊断产物仍会影响总空间，不承诺固定总MB配额。

完整数据流及对外API传输范围见 [隐私说明](PRIVACY.md)。
