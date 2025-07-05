import sqlite3

DB_PATH = './config.db'  # 根据实际路径修改

def add_columns():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 检查并添加 type 字段
    cursor.execute("PRAGMA table_info(monitor_records);")
    columns = [row[1] for row in cursor.fetchall()]
    if 'type' not in columns:
        cursor.execute("ALTER TABLE monitor_records ADD COLUMN type VARCHAR(16) DEFAULT 'sell';")
        print("已添加 type 字段")
    else:
        print("type 字段已存在")

    # 检查并添加 max_buy_amount 字段
    if 'max_buy_amount' not in columns:
        cursor.execute("ALTER TABLE monitor_records ADD COLUMN max_buy_amount FLOAT DEFAULT 0.0;")
        print("已添加 max_buy_amount 字段")
    else:
        print("max_buy_amount 字段已存在")

    conn.commit()
    conn.close()
    print("数据库升级完成")

if __name__ == '__main__':
    add_columns() 