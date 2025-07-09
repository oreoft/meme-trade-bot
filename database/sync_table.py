#!/usr/bin/env python3
"""
给 monitor_logs 表添加 transaction_usd 字段的迁移脚本
"""

import os
import sqlite3

# 数据库文件路径
DATABASE_PATH = "./config.db"


def sync_table():
    """主函数"""
    print("=" * 50)
    print("给 monitor_logs 表添加 transaction_usd 字段")
    print("=" * 50)

    if not os.path.exists(DATABASE_PATH):
        print(f"错误：数据库文件 {DATABASE_PATH} 不存在")
        return

    try:
        # 连接数据库
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # 检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='monitor_logs'")
        if not cursor.fetchone():
            print("错误：monitor_logs 表不存在")
            return

        # 检查字段是否已存在
        cursor.execute("PRAGMA table_info(monitor_logs)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        if 'transaction_usd' in column_names:
            print("字段 'transaction_usd' 已经存在于 monitor_logs 表中")
            return

        # 添加字段
        print("正在添加 transaction_usd 字段...")
        alter_sql = "ALTER TABLE monitor_logs ADD COLUMN transaction_usd REAL DEFAULT 0.0"
        cursor.execute(alter_sql)

        # 提交更改
        conn.commit()

        print("✅ 成功为 monitor_logs 表添加了 transaction_usd 字段")
        print("字段定义：transaction_usd REAL DEFAULT 0.0  -- 交易金额(USD)")

        # 验证字段是否添加成功
        cursor.execute("PRAGMA table_info(monitor_logs)")
        columns = cursor.fetchall()
        transaction_usd_col = next((col for col in columns if col[1] == 'transaction_usd'), None)
        if transaction_usd_col:
            print(f"验证成功：{transaction_usd_col}")

    except sqlite3.Error as e:
        print(f"数据库错误：{e}")
    except Exception as e:
        print(f"未知错误：{e}")
    finally:
        if conn:
            conn.close()
