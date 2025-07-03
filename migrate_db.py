#!/usr/bin/env python3
"""
数据库迁移脚本 - 添加execution_mode和minimum_hold_value字段
"""

import sqlite3
import sys
from datetime import datetime

def check_column_exists(cursor, table_name, column_name):
    """检查表中是否存在指定列"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [column[1] for column in cursor.fetchall()]
    return column_name in columns

def migrate_database():
    """执行数据库迁移"""
    try:
        # 连接数据库
        conn = sqlite3.connect('config.db')
        cursor = conn.cursor()
        
        print("开始数据库迁移...")
        
        # 检查monitor_records表是否存在
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='monitor_records'
        """)
        
        if not cursor.fetchone():
            print("错误: monitor_records表不存在")
            return False
        
        # 备份当前数据
        print("正在备份当前数据...")
        backup_filename = f"config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        backup_conn = sqlite3.connect(backup_filename)
        conn.backup(backup_conn)
        backup_conn.close()
        print(f"数据已备份到: {backup_filename}")
        
        # 检查并添加execution_mode字段
        if not check_column_exists(cursor, 'monitor_records', 'execution_mode'):
            print("添加execution_mode字段...")
            cursor.execute("""
                ALTER TABLE monitor_records 
                ADD COLUMN execution_mode TEXT DEFAULT 'single'
            """)
            
            # 为现有记录设置默认值
            cursor.execute("""
                UPDATE monitor_records 
                SET execution_mode = 'single' 
                WHERE execution_mode IS NULL
            """)
            print("execution_mode字段添加成功")
        else:
            print("execution_mode字段已存在，跳过")
        
        # 检查并添加minimum_hold_value字段
        if not check_column_exists(cursor, 'monitor_records', 'minimum_hold_value'):
            print("添加minimum_hold_value字段...")
            cursor.execute("""
                ALTER TABLE monitor_records 
                ADD COLUMN minimum_hold_value REAL DEFAULT 50.0
            """)
            
            # 为现有记录设置默认值
            cursor.execute("""
                UPDATE monitor_records 
                SET minimum_hold_value = 50.0 
                WHERE minimum_hold_value IS NULL
            """)
            print("minimum_hold_value字段添加成功")
        else:
            print("minimum_hold_value字段已存在，跳过")
        
        # 提交更改
        conn.commit()
        
        # 验证更改
        print("验证数据库结构...")
        cursor.execute("PRAGMA table_info(monitor_records)")
        columns = cursor.fetchall()
        
        print("monitor_records表当前结构:")
        for i, column in enumerate(columns):
            print(f"  {i+1}. {column[1]} ({column[2]}) - 默认值: {column[4]}")
        
        # 统计现有记录数量
        cursor.execute("SELECT COUNT(*) FROM monitor_records")
        record_count = cursor.fetchone()[0]
        print(f"表中现有记录数量: {record_count}")
        
        conn.close()
        
        print("数据库迁移完成！")
        print(f"备份文件: {backup_filename}")
        return True
        
    except Exception as e:
        print(f"数据库迁移失败: {e}")
        return False

def rollback_migration():
    """回滚迁移（如果需要）"""
    try:
        # 这里可以添加回滚逻辑
        print("注意: 如果需要回滚，请使用备份文件替换当前数据库")
        print("备份文件位置: config_backup_*.db")
        
    except Exception as e:
        print(f"回滚失败: {e}")

if __name__ == "__main__":
    print("=" * 50)
    print("数据库迁移脚本")
    print("=" * 50)
    
    # 检查数据库文件是否存在
    import os
    if not os.path.exists('config.db'):
        print("错误: config.db文件不存在")
        sys.exit(1)
    
    # 执行迁移
    if migrate_database():
        print("迁移成功完成!")
        sys.exit(0)
    else:
        print("迁移失败!")
        sys.exit(1) 