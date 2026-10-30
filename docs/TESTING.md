# 验证说明

## 本次公开整理版（2026-10-31）

公开代码从现用原生视觉版本整理，并保留可移动的配置和API适配。验证分开记录：

- Mac Python3.14：46项核心回归测试全部通过。
- 原Windows10，Python3.10.5与3.12.15：在独立测试目录运行46项回归，两个版本全部通过，不覆盖现用机器人。
- Windows PowerShell5.1.19041.6456：16个仓库PowerShell脚本语法解析；执行install.ps1 -Plan与Python模型安装器--plan，确认预览不下载模型。
- 通过公开版doctor连接现有原生模型服务，核验model匹配及text/image声明。
- 使用公开部署代码的pack配方，复用原机现有GGUF，仅在隔离目录重建索引；**48,786个张量条目与现用pack一致**，引擎pack-info通过。没有修改模型文件或另外启动一份大模型。
- 在交互桌面中验证公开桥接能检测仍运行的旧版小鲸并拒绝争抢桌面。SSH会话本身不等于可操作的交互桌面。
- 8个模型资产的固定修订、大小及SHA256与HF上游文件元数据逐项核对；下载器使用本机HTTP服务验证续传、服务器忽略Range时重新下载、坏hash不安装及现有错误文件不覆盖。
- 检查Git忽略与发布文件列表，排除真实配置、人格、监听名单、聊天数据、图片、权重、密钥和私人日志。

回归覆盖原有记忆/基线/送达记账、原生图片同scope限制、失败新图不借旧图、纯文本API不上传存量图、未回答pending不被一起清除、请求参数和认证、模型清单/pack配方、安装路径保护及解压路径检查。CI在Linux/Windows × Python3.10/3.12运行同一组检查，当前结果见[Actions](https://github.com/karanoli/qq-whale-bot/actions)。

## 已实测的原机功能

硬件：RTX5070 12GB、9700X、48GB RAM、SSD，Windows10。现用版本曾验证：

- 两群切换、精确号码核验、普通自动回复、多行粘贴、发送后回读。
- QQ消息图片节点定位与视口截图。
- DeepSeek1017原生接口识别红圆、蓝方块及7294。
- 真实QQ截图经过正式生成函数，返回一句评价。
- 有图时选择静默，process不调用send并处理pending。
- zako、vw50语境的本地生成测试；词典修改下一轮生效。

观察到的模型耗时约15～120秒，受prompt和缓存影响。这些是少量功能测试，不是完整模型基准，也不能据此保证看懂任意梗或图片。

## 没有宣称完成的检查

没有为了发布再完整下载约275GB、在一台全新电脑上从零安装到底；新bootstrap在“没有Python”的分支会安装官方Python，但本轮没有卸载原机Python来重演该分支。固定资源和下载器已核验，完整冷安装仍受网络、驱动、依赖可用性和QQ版本影响。

公开版新增的JSON send/ack没有向真实群额外发送测试消息；底层沿用原机已测试的Transport和Memory，核心契约做了回归。Windows11、其他QQ版本、DPI、帐号和布局仍需用户自己的测试会话验收。

模型服务使用的推理扩展参数只在Strata方案启用。第三方API适配经过请求构造与原生图文测试，不代表已调用每个商业服务，也没有使用真实外部API Key做付费测试。

## 可重跑的核心检查

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-test.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Mac/Linux可用自己的Python环境运行相同命令；它们只验证核心逻辑，不能控制QQ桌面。

## 手工验收

1. 使用自己的测试会话，先停掉其他旧版/外部桌面控制器。
2. 首次读取只建基线；发新文字，核对发送、自己的消息回读和pending处理。
3. 换另一个测试群，确认没有前一群上下文。
4. 发图片及提问，检查对应会话captured-images和last-model-reply的image_meta；不把占位当识图。
5. 发普通图/重复图，观察是否能选择image_silent。
6. stop/F8后确认鼠标键盘不再被操作；reset只影响本项目记忆。
