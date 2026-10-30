# 小鲸 · QQWhaleBot

[![Core checks](https://github.com/karanoli/qq-whale-bot/actions/workflows/core-checks.yml/badge.svg)](https://github.com/karanoli/qq-whale-bot/actions/workflows/core-checks.yml)

通过 **Windows 官方 QQ 的桌面界面**接入本地聊天模型的实验项目：读取已加载的聊天文字、按会话保存独立记忆、生成回复，再用普通输入与发送按钮发出。支持可选的本地截图识图。

**机器人运行在 Windows。Mac 用于整理源码、开发与核心逻辑测试，不能直接运行 QQ 桌面控制。**

## 能做什么

- 群聊与私聊监听名单：新增、改名、修改号码、删除、启停。
- 群之间、私聊之间独立记忆；人格写在 Markdown 中。
- 多会话轮询，默认30秒回复冷却；这不是固定回复周期，切群和模型推理可能更久。
- 无障碍直读 QQ 当前加载的消息；保留旧选取复制实现作为后备。
- 群号精确核验、用户草稿保护、整段粘贴核验、发送后回读；送达不确定时不盲目重发。
- 图片按对应消息节点截图，交给本机视觉模型；取图失败明确提示未读到。
- F8 停止、一键重置、截图和缓存数量限制。

程序会切换会话并操作鼠标键盘。需保持已登录的 QQ 可见，桌面解锁，避免与手动操作同时进行。它不是全量后台消息数据库读取器，也不提供举报、群管理或防封号保证。

## 运行条件与已知边界

- Windows 10/11 交互桌面、Windows PowerShell 5.1、64位 Python 3.10～3.12（含 tkinter）。
- 官方 Windows QQ，且该版本实际提供聊天 UI Automation 节点；版本或无障碍状态不兼容时会停止读取，不会自动修改 QQ。
- 布局来自一套 **1200×800** QQ 窗口。OCR 坐标、侧栏和阈值仍有布局依赖；改变系统缩放、QQ 字号或布局后可能需要修改 desktop.py / transport.py。
- 文本时间是首次观察时间，不是 QQ 原始发送时间。忙群消息被大量刷新、无法唯一对齐时会建立新基线，可能漏读。
- 截图是显示出来的缩略图，不是缓存原图；小字、背景和人物细节可能识错，动图只识别当前帧。

UI Automation 的能力取决于应用暴露的界面信息，参见 [Microsoft 官方概述](https://learn.microsoft.com/en-us/dotnet/framework/ui-automation/ui-automation-overview)。Python 安装方式参见 [Python 官方 Windows 文档](https://docs.python.org/3/using/windows.html)。

## 安装与启动

1. 下载本仓库 ZIP 或克隆到普通用户可写的文件夹，避免解压到 Program Files。
2. 安装 Python 3.10～3.12。双击 **setup.cmd**，创建本目录 .venv 并安装依赖。已有配置不会被覆盖。
3. 单独启动提供 OpenAI 兼容接口的聊天模型服务。本仓库不包含大模型权重、QQ 安装包或模型服务。
4. 编辑自动生成的 **config.json**：
   - endpoint：实际聊天接口完整地址，须以 /chat/completions 结尾。
   - model：服务端接受的模型名；local-chat 只是示例。
   - self_names：当前机器人账号自己的 QQ 昵称，避免把自己的话当作新消息。
5. 编辑 **personality.md** 调整性格。程序下一次生成回复时读取最新内容。
6. 打开并登录 QQ，先在最近会话中打开要监听的对象。可运行 **prepare-window.cmd** 将 QQ 调整到配置的窗口大小；这只调整尺寸，不会自动完成 DPI/OCR 校准。
7. 运行 **manage.cmd**，输入号码和当前完整群名/昵称，核验后加入。初始监听名单为空，不会自动给任何人发消息。
8. 点击管理器里的“保存并开始监听”，或双击 **start.cmd**。管理器打开时会暂停机器人，避免输入冲突。

第一次读取仅建立基线，不回答整屏旧消息；加入后发送新的普通文字进行测试。建议先用自己的测试会话核验收发，再添加更多会话。

也可以在 PowerShell 中安装，并显式指定 Python：

```powershell
.\setup.ps1 -Python "C:\Path\To\Python312\python.exe"
```

首次启动会建立当前用户的交互计划任务 **QQWhaleBot**。运行后可以关闭启动终端；锁屏或退出登录后桌面操作仍会失效。项目不会修改全局 PowerShell 执行策略，不会启动或停止你已有的其他模型任务。若系统策略不允许注册计划任务，可在本项目终端直接运行 .venv\Scripts\python.exe bot.py。

## 配置示例

```json
{
  "endpoint": "http://127.0.0.1:8095/v1/chat/completions",
  "model": "your-served-model-name",
  "self_names": ["你当前的QQ昵称"],
  "persona": "personality.md",
  "cooldown_seconds": 30,
  "send_reasoning_parameters": false
}
```

这是字段节选，完整文件以 config.example.json 为准。路径相对 config.json 所在目录解析，支持移动整个项目文件夹。

send_reasoning_parameters 默认为 false，只发送常见的聊天参数。只有模型服务明确支持 reasoning_effort 和 reasoning_budget_tokens 时才打开它；medium / high 的预算由 reasoning 字段配置。识别到证明、复杂代码等内容时可选择更高预算，实际效果仍由服务端决定。

需要认证时，在启动程序前设置环境变量：

```powershell
$env:QQ_BOT_API_KEY = "你的聊天服务密钥"
.\start.ps1
```

密钥不写入仓库。该变量属于当前 PowerShell 进程，计划任务未必继承它；需要后台任务使用密钥时，请在自己的 Windows 用户环境变量中配置后重新登录。也可在同一终端直接运行 .venv\Scripts\python.exe bot.py，不经过计划任务。

## 开启识图

先独立启动支持图片输入的本机 OpenAI 兼容视觉服务，再设置：

```json
"vision": {
  "enabled": true,
  "endpoint": "http://127.0.0.1:8081/v1/chat/completions",
  "model": "vision-local",
  "api_key_env": "QQ_BOT_VISION_API_KEY",
  "allowed_roots": ["conversations"]
}
```

识图服务目前限本机地址。截图需要原始图片节点仍在 QQ 已加载的界面中，并能完整显示在聊天视口内；界面切换、节点消失或图片太大无法完整显示时，会拒绝猜测。获取后会恢复到最新消息。

图片数据形如：

```json
{
  "image_count": 1,
  "images": ["conversations/group_示例号码/captured-images/消息哈希.jpg"],
  "vision": ["本地图像模型给出的观察描述"]
}
```

每个会话最多保留最近32张自身生成的截图和32份识图描述缓存，聊天上下文保留60条。详见 [本地数据与隐私](docs/PRIVACY.md)。

## 常用操作

| 入口 | 操作 |
| --- | --- |
| setup.cmd | 安装依赖，生成本地配置 |
| manage.cmd | 编辑监听名单，打开时暂停机器人 |
| start.cmd | 检查模型服务并开始监听 |
| stop.cmd / F8 | 停止机器人，保留 QQ 和模型服务 |
| reset.cmd | 停止并重置记忆，保留配置和人格，保留最近3份备份 |
| doctor.cmd | 只读检查依赖和模型接口 |
| prepare-window.cmd | 将 QQ 调整到配置的窗口大小 |

日志与状态位于 bot-log.jsonl、bot-status.json 和各会话 status.json。它们可能包含聊天内容，均被 Git 忽略。打开 debug_snapshots 会保存诊断截图，使用后自行清理。

## 开发与验证

核心逻辑测试不需要 QQ、Windows 扩展、模型或账号：

```bash
python3 -m unittest discover -s tests -v
```

测试覆盖消息去重与基线、独立记忆、图片路径保留、上下文、推理配置、时间前缀清理、日志轮转及重置备份。GitHub Actions 在 Linux 和 Windows 运行核心测试，并在 Windows 解析 PowerShell 脚本。

Windows 桌面收发需在真人登录的 QQ 环境中另外测试；CI 不会登录 QQ 或发送消息。公开整理版与原运行版本的验证差异见 [验证说明](docs/TESTING.md)，代码分工见 [工作方式](docs/ARCHITECTURE.md)。

## 公开内容

仅发布源代码、示例配置、示例人格和文档。不会上传账号、群号、聊天记录、截图、模型或本地部署日志。公开仓库当前尚未指定开源许可证。
