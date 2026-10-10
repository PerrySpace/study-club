// MongoDB 首次初始化脚本（仅数据卷首次创建时执行）
// 说明：集合与索引由后端启动时幂等创建（apps/api/app/db/mongo.py），
//      这里只做数据库层面的基础设置，避免与业务索引两处维护。

db = db.getSiblingDB(process.env.MONGODB_DB || 'study_club');

// 只读健康标记集合，便于运维快速确认初始化脚本已跑过
db.getCollection('_init').insertOne({
  initialized_at: new Date(),
  note: 'study-club mongo init',
});

print('[study-club] MongoDB 初始化完成：' + db.getName());
