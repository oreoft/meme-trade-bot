#!/usr/bin/env python3
"""
数据库迁移脚本：为PrivateKey表添加deleted字段
"""

import sqlite3
from datetime import datetime

def migrate_private_key_deleted():
    """为private_keys表添加deleted字段"""
    
    # 连接到数据库
    db_path = "config.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查deleted字段是否已存在
        cursor.execute("PRAGMA table_info(private_keys)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'deleted' not in columns:
            print("正在为private_keys表添加deleted字段...")
            
            # 添加deleted字段，默认值为False
            cursor.execute("""
                ALTER TABLE private_keys 
                ADD COLUMN deleted BOOLEAN DEFAULT 0
            """)
            
            # 将现有记录的deleted字段设置为False
            cursor.execute("""
                UPDATE private_keys 
                SET deleted = 0 
                WHERE deleted IS NULL
            """)
            
            conn.commit()
            print("✓ 成功添加deleted字段")
            
            # 获取更新的记录数
            cursor.execute("SELECT COUNT(*) FROM private_keys WHERE deleted = 0")
            count = cursor.fetchone()[0]
            print(f"✓ 已将 {count} 个现有私钥记录的deleted字段设置为False")
            
        else:
            print("deleted字段已存在，跳过迁移")
            
    except Exception as e:
        print(f"迁移失败: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    print("开始数据库迁移...")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)
    
    migrate_private_key_deleted()
    
    print("-" * 50)
    print("数据库迁移完成！") 