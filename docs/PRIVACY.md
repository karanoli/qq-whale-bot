# 本地数据与API传输

## 仓库和真实运行数据分开

仓库只含程序、示例和文档。config.json、targets.json、personality.md、internet-slang.md、模型、密钥、截图、聊天记忆、运行日志和.local-ai都被Git忽略。监听名单初始为空。不要用git add -f把真实运行目录强制提交。

示例人格与词典可公开；它们不包含真实联系人、群号或聊天历史。公开版不带原机的评测题目/回答和安装日志。

## 保存什么

| 位置 | 内容 | 正常保留范围 |
| --- | --- | --- |
| conversations/类型_号码/memory.json | 消息文字、昵称、首次观察时间、图片路径、发送状态 | 最近60条上下文、4000个seen ID、200个pending ID |
| 同scope/captured-images/ | 对应消息节点截取的JPEG | 每会话最近32张，采集最长边1024像素 |
| memory.json的native_seen_images | 最近图像摘要 | 最多32个SHA256 |
| 同scope/direct-cursor.json | 消息对齐游标 | 最近200条 |
| bot-log.jsonl* | 事件、回复、错误 | 约2MiB轮转，最多3份旧归档 |
| memory-backups/ | reset前备份 | 最近3份带本程序标记的备份 |
| diagnostics/ | 开启debug或手动诊断产生的数据 | 不承诺总大小上限；默认debug_snapshots=false |
| .local-ai/ | 本机模型路径、下载校验记录、模型日志与配置备份 | 不上传；模型日志需自行关注大小 |

这些是数量限制，不是整个项目固定MB限额。会话越多，占用越多。模型275GB属于独立部署资产，不应计入Git仓库体积。

截图是QQ显示的气泡图，不是缓存原图；可能没有原图文件路径。原生推理每轮把至多一张截图编码成data URL，只存在于该请求内，不持久化Base64。历史旧缓存文件若存在不会用于当前原生prompt。

## 发给谁

- 本地路线：QQ文字、选中的截图、当前会话上下文、人格与词典发往本机Strata。
- API路线：上述模型输入发往config.json配置的endpoint，包括图片。开启原生识图前确认该API支持data URL及你希望传输的数据范围。
- bridge read：只在本机stdout输出JSON；prompt输出可能含聊天内容和图片Base64。调用者决定是否进一步上传。
- 运行日志可能包含QQ回复和错误，不要把日志整包附到公开Issue。

API Key通过指定环境变量读取；Windows后台任务可回读当前用户Environment注册表项。不会写进prompt、示例文件或bridge输出。

## 重置与账号切换

reset.cmd会停bot、重置会话记忆并保留配置/人格，保留最近3份带标记备份。改QQ账号时先停bot，修改self_names及监听名单并重新核验；不将旧窗口身份缓存当作新账号身份。

删除模型、Python环境或pack所引用的组件会使下次启动失败。清理下载包和过期诊断前可先停相应任务，勿清理正在使用的图片/模型文件。
