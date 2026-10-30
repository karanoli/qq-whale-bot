# 本地 AI 部署与排障

## 固定方案与来源

本方案固定 Strata v0.2.8 的提交 `870aedd9e1ebe1c91f94da93b59af17729f6c5c0`，CUDA13引擎0.1.54。模型是 DeepSeek-V4.1-Flash-1017，ISTA-DAS IQ2_XS/2.25bpw。主权重、Engram和DSpark复用原机已验证的旧4分片布局；另加原生视觉组件，不运行千问。

2.25bpw是此混合量化方案的标签，各张量精度并不全相同，容量以实际文件为准。

完整文件名、不可变下载修订、字节数和SHA256都在 [models.lock.json](../deployment/models.lock.json)。8个模型文件约274.78GB；不要混入新版5/6分片布局或对现有权重原地转换。Engram独立目录只放表文件，元信息小分片放shared目录，避免把它误判成不完整的Engram集合。

来源：
- [DeepSeek官方模型与配置](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017)
- [Strata原生视觉与分层运行机制](https://github.com/Niko1221/Strata/blob/v0.2.8/docs/DEEPSEEK41.md)
- [Strata固定版本](https://github.com/Niko1221/Strata/releases/tag/v0.2.8)
- [ISTA-DAS量化仓库](https://huggingface.co/ISTA-DASLab/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF)
- [Python Windows安装文档](https://docs.python.org/3/using/windows.html)

## 为什么装得下、为什么仍会慢

12GB显存不会容纳275GB文件。Strata把一部分权重放GPU，在RAM里缓存常用专家，其他数据留在SSD，需要时读取；CPU也参与计算。原机日志中可见GPU权重/专家缓存、RAM store和CPU lane，不能描述成“内存只存、显卡包办所有计算”。

SSD权重主要读取，不是每个token反复重写整份模型。下载、临时分片、日志、安装配置和运行缓存仍会产生写入。模型越大、缓存越难命中，读取压力越明显，游戏或其他工作也会争抢内存与磁盘。关掉模型可归还其占用。

固定方案以9700X、48GB RAM、5070 12GB为实机基线。安装会检查GPU0显存和物理内存，并在下载前核对剩余磁盘空间；驱动须支持CUDA13（检查R580或更新系列，具体兼容性以显卡和引擎为准），安装脚本不自动更换显卡驱动。参见[NVIDIA CUDA13官方说明](https://docs.nvidia.com/cuda/archive/13.0.1/cuda-toolkit-release-notes/index.html)。其他电脑的性能与兼容性需要自行验证。

## 一键入口

解压仓库后，双击 `install.cmd`，或在普通PowerShell中：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Mode Local -AiRoot 'D:\QQWhaleAI' -QQName '你当前的QQ昵称'
```

过程：
1. 寻找64位Python3.10～3.12（含tkinter和pip）。
2. 没找到时，下载Python官方3.12.10 Windows安装程序，验证Authenticode签名及Python Software Foundation发布者后，为当前用户静默安装。它不修改全局执行策略。
3. 创建仓库内 `.venv` 并安装QQ/OCR依赖；只在目标文件不存在时生成配置、人格、词典与空监听名单。
4. 获取固定Strata源码、引擎和8个模型文件。下载以 `.part` 续传，完成后校验大小与SHA256。
5. 建立独立的Strata Python环境；生成pack、tokenizer、原生视觉索引与启动配置；执行引擎pack-info检查。
6. 把机器人配置接到本机8095，启用原生图片和兼容的思考参数。保留现有监听名单、人格和昵称；原机器人配置的一份备份写入 `.local-ai/bot-config.before-local-ai.json`。

部署不会自动登录QQ、替你填群号或开始发消息。模型文件不在仓库里；首次完整下载可能需要数小时。软件安装完成不代表已做一次真实群聊收发，需按README添加会话后发送新消息验证。

## 参数与分步命令

```powershell
# 预览，不安装软件或下载权重
.\install.ps1 -Plan

# 指定已有Python
.\install.ps1 -Mode Local -Python 'C:\Path\To\Python312\python.exe' -AiRoot 'D:\QQWhaleAI'

# 指定HF镜像（由你决定信任的镜像，SHA256仍检查）
.\install.ps1 -Mode Local -AiRoot 'D:\QQWhaleAI' -HfEndpoint 'https://hf-mirror.com'

# 复用旧模型目录，同盘硬链接；首次完整读取做SHA256校验
.\install.ps1 -Mode Local -AiRoot 'D:\QQWhaleAI' -ReuseModels 'D:\AIchat\models\strata-v41'

# 已装完机器人依赖，只继续安装/续传模型
powershell -NoProfile -ExecutionPolicy Bypass -File .\deployment\install-local-ai.ps1 -AiRoot 'D:\QQWhaleAI'
```

复用不是移动模型或修改GGUF；旧文件保留。跨磁盘硬链接会失败，脚本不会悄悄复制275GB。若希望跨盘复制，请自己明确安排空间和文件移动。

网络镜像参数仅替换HF地址。源码和引擎来自GitHub。可通过系统/进程的代理环境变量配置下载网络；机器人请求是否读取代理由 `trust_env` 决定，默认false。若需要pip镜像，在运行安装前自行设置 `$env:PIP_INDEX_URL`。

安装锁阻止两份安装进程同时操作同一份本地状态。已校验且大小、修改时间没变的文件会使用本地校验记录，避免每次重读275GB；文件变化后重新校验。

## 安装目录

```text
仓库/
  .venv/                      QQ脚本环境
  .local-ai/
    chat.local.json           本机模型启动配置
    services.local.json       解释器/服务路径
    download-receipts.json    已验证文件记录
    logs/                     运行日志
D:/QQWhaleAI/
  downloads/                  已校验下载包
  strata-source/              固定Strata源码
  engine-0.1.54/              引擎及CUDA运行库
  strata-venv/                模型服务Python环境
  models/backbone/            4个主模型分片
  models/engram/              独立Engram表
  models/shared/              元数据、DSpark、原生mmproj
  packs/deepseek41-native/    张量索引、hash表及tokenizer
```

AiRoot不能是盘符根或仓库根，也不能随意放进仓库源码子目录；可选仓库的 `.local-ai` 子目录，默认推荐仓库外。安装期间别移动这些目录。之后移动模型需更新本机服务配置并重建pack；只移动源码也需要重新生成带绝对路径的本地服务状态。

## QQ读取前的设置

使用官方Windows QQ。先退出QQ，再按自己电脑上的实际安装位置运行：

```powershell
$qqExe = 'C:\Program Files\Tencent\QQNT\QQ.exe'
Start-Process -FilePath $qqExe -ArgumentList '--force-renderer-accessibility'
```

上面的路径只是示例；从快捷方式属性查实际路径。这个Chromium参数是为了让QQ暴露无障碍节点，但具体QQ版本是否有效仍需检查。项目不会自动给已运行的QQ追加参数、注入进程或读取数据库密钥。

登录后打开目标会话，运行 `prepare-window.cmd`，再用 `manage.cmd`添加并核验目标。窗口基线1200×800；QQ布局、Windows缩放、字号和系统语言变化可能需要调整OCR规则。保持桌面解锁、QQ可见，避免同时游戏/手动输入抢焦点。

## 启动与停止

```powershell
# 模型+机器人
.\start-all.ps1

# 只启模型（交互计划任务，关终端后继续）
.\deployment\start-local-ai.ps1

# 前台调试模型，关闭窗口就停止这一次前台服务
.\deployment\serve-chat.ps1

# 只启机器人；要求模型已可用且监听名单非空
.\start.ps1

# 只停机器人，或按F8
.\stop.ps1

# 停机器人与本仓库自己启动的模型
.\stop-all.ps1

# 只停本仓库模型
.\deployment\stop-local-ai.ps1
```

后台任务分别是QQWhaleBot与QQWhaleLocalAI。注册的命令行必须指向当前仓库，发现任务属于其他安装时拒绝覆盖。8095已存在同名、声明支持原生图片的模型服务时可以复用；stop-all不会停止没有由本仓库登记的外部服务。

## 测试本地模型接口

```powershell
Invoke-RestMethod 'http://127.0.0.1:8095/v1/models'

$body = @{
 model = 'deepseek-v4.1-flash'
 messages = @(@{role='user';content='你好，用一句话打个招呼。'})
 temperature = 0.7
 max_tokens = 512
 reasoning_effort = 'medium'
 reasoning_budget_tokens = 384
} | ConvertTo-Json -Depth 10
Invoke-RestMethod 'http://127.0.0.1:8095/v1/chat/completions' -Method Post -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body))

.\doctor.cmd
```

原生图片输入格式见INTEGRATION.md。模型回复质量、思考预算和量化影响都需实际观察，不根据“能启动”推断满血质量或洛谷/MMLU水平。

## 常见问题

- **下载断了**：重跑同一安装命令，保留 `.part`。空间预估会扣除已有分片。
- **SHA256不符**：不会安装或执行坏文件。核对网络、修订和文件名；明确移走错误文件后重新下载，不要跳过校验。
- **导入依赖失败**：检查Python版本/64位/tkinter、pip网络、VC运行库及显卡驱动。日志里保留真实失败原因；脚本不会假装安装完成。
- **模型服务启动失败**：查 `.local-ai/logs/chat-server.err.log` 与 `chat-engine.log`。核对pack所有文件还在，不要删DSpark、Engram或mmproj等被索引引用的文件。
- **没有聊天文字**：核对官方QQ版本、无障碍参数、已打开会话和焦点。脚本不读取全部后台历史。
- **图片读不到**：图片必须在QQ已加载的会话中、节点仍在且可完整显示；截图是气泡缩略图，不是原图。
- **不回复图片**：可能是主动沉默，也可能还在推理。看 `bot-status.json`、对应会话status与last-model-reply；`image_silent` 是正常决定，不是发送失败。
- **回复出现在输入框但没发出**：检查焦点、草稿和读回日志，保留“不确定送达”的记账，勿手动循环重发。
- **换账号/改群名**：先停bot，再更新昵称与监听名称/号码，必要时reset。不能靠旧窗口的核验缓存认新账号。
