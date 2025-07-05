import sqlite3

DB_PATH = './config.db'

# 连接数据库
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 检查字段是否已存在
cursor.execute("PRAGMA table_info(monitor_records);")
columns = [row[1] for row in cursor.fetchall()]

if 'pre_sniper_mode' not in columns:
    # 添加新字段
    cursor.execute("ALTER TABLE monitor_records ADD COLUMN pre_sniper_mode BOOLEAN DEFAULT 0;")
    print('已添加 pre_sniper_mode 字段')
else:
    print('pre_sniper_mode 字段已存在，无需添加')

conn.commit()
conn.close() 