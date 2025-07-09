import sqlite3

# 数据库文件路径（如有需要请修改）
db_path = "config.db"

columns = [
    ("monitor_type", "TEXT", "'normal'"),
    ("price_type", "TEXT", "NULL"),
    ("current_value", "REAL", "NULL"),
    ("sell_threshold", "REAL", "NULL"),
    ("buy_threshold", "REAL", "NULL"),
    ("action_type", "TEXT", "NULL"),
    ("watch_token_address", "TEXT", "NULL"),
    ("trade_token_address", "TEXT", "NULL"),
]

def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())

def add_column(cursor, table, column, col_type, default):
    if not column_exists(cursor, table, column):
        sql = f"ALTER TABLE {table} ADD COLUMN {column} {col_type} DEFAULT {default}"
        print(f"执行: {sql}")
        cursor.execute(sql)
    else:
        print(f"字段 {column} 已存在，跳过。")

def main():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    for col, col_type, default in columns:
        add_column(cursor, "monitor_logs", col, col_type, default)
    conn.commit()
    conn.close()
    print("数据库字段升级完成！")

if __name__ == "__main__":
    main() 