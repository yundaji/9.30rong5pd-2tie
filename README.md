# 多频道随机时间轮流循环发布

一个机器人，共用一个帖子池。默认5个频道，每个每天2条，总共10条。按posts.json数组顺序取帖，依次发给频道1、2、3、4、5，再轮流一遍。下一天接着上一天的帖子位置；帖子池发完自动回第一条。每个相册对象算一条帖子。当前模板仅3条，因此一天内会重复；加入更多帖子可减少重复。

每天北京时间08:00–23:00分成十个时间段，每段随机选择一分钟。GitHub每15分钟检查一次，到时间后发送。随机计划写入state.json，不会每次执行重新抽签。任务延迟时会补发当天已经到期的额度，可能一次发多条；跨午夜不会补前一天的额度。平台可能延迟或漏运行，不能保证准点或每天发满10条。

## 第一步：设置机器人
1. 在Telegram的@BotFather创建机器人，复制Bot Token。
2. 将同一个机器人加入全部目标频道，设为管理员并打开发布消息权限。
3. 将机器人加入帖子链接对应的源频道，保证能够访问原消息。保留原项目的复制方式，不显示转发来源，不需要API_ID。

## 第二步：上传GitHub
1. 新建仓库，将解压后的文件放在根目录：main.py、posts.json、channels.json、state.json、README.md和.github/workflows/daily.yml。
2. 网页上传可能遗漏隐藏的.github目录：Add file → Create new file，文件名填.github/workflows/daily.yml，复制压缩包中该文件的内容并提交。工作流必须在默认分支。
3. 编辑channels.json，把5个@YOUR_CHANNEL占位项替换为自己的频道用户名，例如@mychannel01；私有频道可填写数字chat_id（如-1001234567890）。频道不能重复。
4. Settings → Secrets and variables → Actions → New repository secret，名称BOT_TOKEN，值填机器人Token。不要把Token写进代码。
5. Settings → Actions → General → Workflow permissions，选择Read and write permissions并保存。若组织限制写入，需要管理员放行，否则无法保存进度。
6. Actions → 多频道随机时间轮流循环发布 → Run workflow测试。08:00前不会发送；晚上首次执行会补发当天已到期的额度，最多总共10条。

## 帖子池和进度
直接编辑posts.json，保持单个JSON数组。media为原帖链接数组，相册要列出完整ID，按原频道消息ID升序排列，并来自同一源频道。不要把不同帖子拼成一个对象。文字替换保留原项目的text配文逻辑。

state.json自动保存全局帖子位置、当日计划、发送数量。不要删除或覆盖它，否则会从头发送。一个时间槽只有成功后才推进；失败会在后续任务重试。Telegram已经接收但响应或保存失败时仍可能重复，不具备严格的“仅发送一次”保证。

当天首次运行后不要修改频道配置，等次日首次运行前再改。频道数量可扩展，每频道仍2条，总量为频道数×2。若想从旧单频道项目迁移，使用新仓库和本包初始state.json；这会从帖子池第一条开始。不要同时启用旧项目，以免额外发送。

公开仓库长期无活动时GitHub可能停用定时任务，需在Actions重新启用。Token仅放Secrets；帖子内容和频道列表在公开仓库可见，可按需要使用私有仓库。

本项目通过本地模拟测试，未使用你的Token连接Telegram实发。
