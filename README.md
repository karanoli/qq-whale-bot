# 小鲸 · QQWhaleBot

[![Core checks](https://github.com/karanoli/qq-whale-bot/actions/workflows/core-checks.yml/badge.svg)](https://github.com/karanoli/qq-whale-bot/actions/workflows/core-checks.yml)

看大家都在 QQ 养鱼，我也想养一只。又没钱一直调 API，就先用手头的电脑折腾了个本地 AI；原来的第三方 QQ 接入路线又碰上封号，于是改成操作官方 QQ 窗口的脚本。

最后就有了这只会护饭、会嘴欠、会看图，也可以选择不说话的鲸鱼。这个仓库把 **QQ 桌面接入、本地 AI 部署、人格和网络词典、外部模型适配**放在一起。

> 机器人在 Windows 10/11 运行，Mac 可开发和测试核心逻辑。桌面脚本也需要保持 QQ 可见、桌面解锁；换一种接入方式不等于保证不封号。

## 实现了什么

- **文字聊天**：通过 UI Automation 读取 QQ 已加载的群聊/私聊，不解密数据库、不注入 QQ、不使用第三方 QQ 协议。保留旧选取复制后备代码。
- **多会话**：管理器支持新增、修改、改名、删除、启停群或个人；默认30秒冷却，实际速度还取决于切群和推理时间。
- **独立记忆**：按“群/个人＋号码”隔离上下文、待处理消息和发送状态，避免串群。
- **原生识图**：将对应图片节点截成 JPEG，与文字一起发给支持图片的聊天模型；理解和评价、接梗优先，明确问细节时才描述。
- **选择沉默**：普通刷图、重复图、无自然接点时，模型可以不回；内部静默标记不会发送到 QQ。
- **人格可改**：`personality.md` 和 `internet-slang.md` 每轮读取。示例包含鲸鱼娘风格、zako、vw50/疯四等语境，不是训练权重或自动联网学习。
- **发送核验**：核对目标号码和标题，保护用户草稿，整段粘贴后检查，发送后回读。送达不确定会记账，不自动重发。
- **可替换模型**：同一套程序既能连本地 Strata，也能连兼容 OpenAI Chat Completions 的 API。提供 JSON 命令行桥接。
- **常用入口**：一键部署、启动、停止、重置记忆；F8 急停；图片、去重记录和日志有保留上限。

目前没有实现举报、踢人等群管理功能，也没有把“@昵称文本”包装成真正的 QQ @、戳一戳或其他官方消息接口。

## 5070 怎么跑 1017

本地路线复现的是 **DeepSeek-V4.1-Flash-1017 的 ISTA-DAS IQ2_XS / 2.25bpw 量化版本**，使用 [Strata v0.2.8](https://github.com/Niko1221/Strata/releases/tag/v0.2.8) 的 `strata-dsv41 0.1.54` CUDA13 引擎，直接启用 DeepSeek 自己的视觉组件。

实机基线是 **RTX 5070 12GB＋Ryzen 9700X＋48GB DDR5＋SSD，Windows 10**。这里的“能跑”依靠量化、专家按需读取、显卡/CPU协同和 RAM/SSD 缓存，**不是把48GB内存变成48GB显存，也不是所有计算都交给显卡**。推理速度受 CPU、SSD、缓存命中和上下文影响很大。

| 项目 | 本方案 |
| --- | --- |
| 主模型权重 | 4个分片，约155.23 GB |
| Engram 表 | 约110.60 GB |
| DSpark 草稿组件 | 约7.98 GB；保留依赖，低显存下引擎可自动不启用 |
| 原生视觉组件 | 约0.97 GB；不是千问转述 |
| 模型相关下载合计 | **274,776,017,997 字节，约274.78 GB / 255.9 GiB** |
| 固定上下文 | 8192 tokens |
| 路由专家 | 每token激活6个；保留模型完整专家权重 |
| 思考预算 | 日常medium 384，复杂任务high 1536；仅兼容服务启用这些扩展参数 |

原机功能测试中，单条模型回复约15秒到两分钟都有出现；数字识图约29秒，真实 QQ 截图评价约67秒。它不等于即时聊天，也不代表完整基准分数。具体机制、硬件要求、SSD读写和来源见 [本地 AI 部署](docs/LOCAL_AI.md)，验证边界见 [测试说明](docs/TESTING.md)。

## 部署：本地 AI 一起装

推荐至少48GB内存、约12GB显存、支持CUDA13的NVIDIA驱动，SSD额外预留 **约280GB以上**。下载/断点续传会保留分片；请勿用接近满盘的磁盘。

**下载仓库 ZIP、解压后双击 `install.cmd`**，默认安装机器人依赖和本地模型。没有合适 Python 时会下载安装官方3.12.10，执行前校验签名；不需要 Git。已存在的人格、监听名单不会被覆盖。部署过程不登录 QQ、不自动给任何人发消息。

也可以从普通 PowerShell 复制执行：

```powershell
$work = 'D:\QQWhale'
New-Item -ItemType Directory -Force $work | Out-Null
Invoke-WebRequest -UseBasicParsing 'https://github.com/karanoli/qq-whale-bot/archive/refs/heads/main.zip' -OutFile "$work\source.zip"
Expand-Archive "$work\source.zip" -DestinationPath $work -Force
Set-Location "$work\qq-whale-bot-main"

# 只查看方案，不下载
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Plan

# 修改昵称和模型保存位置后执行
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Mode Local -QQName '你当前的QQ昵称' -AiRoot 'D:\QQWhaleAI'
```

可选：网络访问 HF 困难时，显式选择你信任的镜像：

```powershell
.\install.ps1 -Mode Local -QQName '你当前的QQ昵称' -AiRoot 'D:\QQWhaleAI' -HfEndpoint 'https://hf-mirror.com'
```

已有这套旧布局的模型，避免重新下载：

```powershell
.\install.ps1 -Mode Local -AiRoot 'D:\QQWhaleAI' -ReuseModels 'D:\AIchat\models\strata-v41'
```

复用按文件名、大小及SHA256核对，首次会完整读取权重做校验；同盘使用硬链接，**不会复制另一份275GB模型或修改原权重**。跨盘不自动复制。安装中断后重跑相同命令续传。完整参数、目录和逐步命令见 [部署详解](docs/LOCAL_AI.md)。

### 登录 QQ 与开始聊天

1. 安装并登录官方 Windows QQ。先在 QQ 中打开要监听的会话，使它出现在最近会话中。
2. 如果读不到聊天节点，退出 QQ 后按 [QQ 无障碍设置](docs/LOCAL_AI.md#qq读取前的设置) 用 `--force-renderer-accessibility` 启动；本项目不自动重启你的 QQ。
3. 确认 `config.json` 的 `self_names` 是机器人当前昵称；运行 `prepare-window.cmd` 调整窗口到1200×800。系统缩放和QQ布局仍需匹配。
4. 运行 `manage.cmd`，输入群/个人号码与当前完整名称，核验后添加。初始名单为空。
5. 双击 **`start-all.cmd`**：启动/复用原生模型服务，再开始监听。第一屏只建基线，请发一条新消息测试。
6. **`stop.cmd` / F8** 只停机器人；**`stop-all.cmd`** 同时停止本仓库自己启动的本地模型；QQ保留。

程序使用交互计划任务，关闭启动终端后可继续运行；锁屏、切换桌面、关闭QQ或同时手动操作会使桌面控制失败。旧版小鲸仍运行时，新版会拒绝同时操作 QQ。

## 部署：使用已有 API，不装275GB模型

```powershell
.\install.ps1 -Mode API -QQName '你当前的QQ昵称'
.\model-settings.cmd
```

在“模型与思考设置”中填写API地址和Key，点击“获取模型列表”，下拉选择模型后保存。Key用Windows账户加密，不写入config.json；接口只返回一个模型时自动选中，多个时由你选择。没有列表接口也可以手填模型ID。

同一窗口可选择**关闭/低/中/高思考**、是否让复杂问题自动提高，以及各档token预算。提供“兼容模式 / 通用effort / 本地Strata”三种参数格式；不同服务支持的字段不同，不承诺所有API都接受全部档位。详见[模型与思考设置](docs/MODEL_SETTINGS.md)。

打开设置会暂停这份项目自己的聊天脚本，关闭后恢复原来状态；模型服务不停止。设置监听名单后运行start.cmd。本地和API配置都可用这个窗口修改，不需要手动改模型名。

高级用户仍可在安装时指定 `-Endpoint` 与 `-Model`，或使用环境变量。API模式默认纯文字；所选模型支持原生图片时在窗口勾选“原生识图”。文字和图片发往**同一个模型接口**。

按服务要求可选择max_tokens/max_completion_tokens、是否使用环境代理与是否检查模型列表。完整请求/响应和命令行桥接见[数据与接口](docs/INTEGRATION.md)。

## 数据、调用与项目结构

- [模型与思考设置](docs/MODEL_SETTINGS.md)：地址与Key、模型列表、思考档位和预算。
- [数据与接口](docs/INTEGRATION.md)：消息字段、图片、记忆、请求JSON、JSON命令行、外部AI循环示例。
- [工作方式](docs/ARCHITECTURE.md)：从QQ界面到模型再到发送确认的流程与模块。
- [本地 AI 部署](docs/LOCAL_AI.md)：完整命令、固定版本、下载校验、复用、启动停止、排障。
- [本地数据与隐私](docs/PRIVACY.md)：会记录什么、上传给谁、容量边界。
- [验证说明](docs/TESTING.md)：原机实测与公开安装脚本测试的区别。

```text
bot.py / memory.py / reasoning.py       聊天循环、独立记忆和推理策略
native_vision.py / vision.py           原生图文上下文、选图及采集
desktop.py / transport.py              QQ桌面操作、核验、草稿与回读
direct_reader.py / read-qq-*.ps1        UIA文字、身份和图片节点
bridge.py                             对外JSON命令行适配器
runtime.py                            路径、API鉴权和请求参数
model_settings.py / model_config.py    模型设置窗口、列表查询与加密密钥
manager.py                            监听对象管理器
deployment/                           固定模型清单、安装和模型服务
docs/ / tests/                        文档与核心回归检查
```

## 许可证

本项目代码采用 [MIT License](LICENSE)。第三方模型和依赖遵循各自许可证。
