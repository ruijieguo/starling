-- 0040_events_incarnation.sql:events 行加一个删除重建后不复用的身份(裁定 R102、R118)。
-- remember_event 分三段,begin 与 finish 之间(锁外抽取)行可能被 clear_tenant 删掉,再被另一次调用用同一个 key
-- 重建。finish 原来靠 text_sha256 与 seq 认行,但 next_seq 是 MAX(seq)+1,清空之后从 0 重新编号:重建是清空后第一条
-- 写入时,新行与旧行的 seq 相同,同一段文本的 sha 也相同,finish 认不出来,会照常收尾、改写新行的 failure_category。
-- incarnation 是行的随机身份(UUID v4),由 C++ 在 INSERT 时写入(memory_events.cpp 的 remember_event_begin),
-- 不取自 seq 或任何可重算的值,所以删掉再建的行一定拿到另一个值。begin 记下它,finish 在事务里重读时比它。
--
-- 只加列,不重建表,不回填。已有的行读出 '':迁移不碰行内容,这一列在 SQL 里也给不出与 C++ 同源的随机值。
-- '' 在 begin 第一次碰到这一行时补上:第 1 段的事务里就地写一个随机值(WHERE ... AND incarnation=''),之后按新值
-- 处理。只补 begin 碰到的行;finish 只认 begin 记下的值,不补。abandon_event 不读这一列。
--
-- 摘要(memory_digest.cpp 的 excluded_columns)排除这一列:它是行身份,与 id 同类,两个库写入相同内容时必然不同;
-- 迁移前后同一个库的摘要也因此不变('' 不进摘要)。
-- MigrationRunner 已把本文件包在 BEGIN IMMEDIATE 里,这里不另开事务。

ALTER TABLE events ADD COLUMN incarnation TEXT NOT NULL DEFAULT '';
