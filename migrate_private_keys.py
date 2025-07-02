#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据迁移脚本：将现有监控记录的私钥迁移到新的私钥管理系统
"""

import sqlite3
import sys
from datetime import datetime

from solders.keypair import Keypair


def migrate_private_keys():
    """迁移私钥数据"""

    # 连接数据库
    conn = sqlite3.connect('config.db')
    cursor = conn.cursor()

    try:
        # 检查是否已经有private_keys表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='private_keys'")
        if not cursor.fetchone():
            print("❌ private_keys表不存在，请先运行主程序创建表结构")
            return False

        # 检查monitor_records表是否还有private_key字段
        cursor.execute("PRAGMA table_info(monitor_records)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'private_key' not in columns:
            print("✅ 数据库已经是新结构，无需迁移")
            return True

        # 获取所有带有私钥的监控记录
        cursor.execute(
            "SELECT id, name, private_key FROM monitor_records WHERE private_key IS NOT NULL AND private_key != ''")
        records = cursor.fetchall()

        if not records:
            print("✅ 没有需要迁移的监控记录")
            return True

        print(f"📝 找到 {len(records)} 个监控记录需要迁移私钥")

        migrated_keys = {}  # 私钥 -> 私钥ID的映射

        for record_id, record_name, private_key in records:
            try:
                # 如果这个私钥已经迁移过，直接使用existing的ID
                if private_key in migrated_keys:
                    key_id = migrated_keys[private_key]
                    print(f"  🔄 记录 '{record_name}' 使用已存在的私钥")
                else:
                    # 验证私钥格式并生成公钥
                    try:
                        keypair = Keypair.from_base58_string(private_key)
                        public_key = str(keypair.pubkey())
                    except Exception as e:
                        print(f"  ❌ 记录 '{record_name}' 的私钥格式错误: {e}")
                        continue

                    # 创建私钥昵称（使用记录名称）
                    nickname = f"{record_name}_key"

                    # 检查昵称是否已存在，如果存在则添加后缀
                    cursor.execute("SELECT COUNT(*) FROM private_keys WHERE nickname LIKE ?", (f"{nickname}%",))
                    count = cursor.fetchone()[0]
                    if count > 0:
                        nickname = f"{nickname}_{count + 1}"

                    # 插入私钥记录
                    cursor.execute("""
                        INSERT INTO private_keys (nickname, private_key, public_key, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (nickname, private_key, public_key, datetime.utcnow(), datetime.utcnow()))

                    key_id = cursor.lastrowid
                    migrated_keys[private_key] = key_id

                    print(f"  ✅ 创建私钥记录: {nickname} -> {public_key[:8]}...{public_key[-8:]}")

                # 更新监控记录的private_key_id
                cursor.execute("UPDATE monitor_records SET private_key_id = ? WHERE id = ?", (key_id, record_id))
                print(f"  🔗 更新监控记录 '{record_name}' 的私钥关联")

            except Exception as e:
                print(f"  ❌ 迁移记录 '{record_name}' 时出错: {e}")
                continue

        # 提交事务
        conn.commit()

        # 删除旧的private_key字段（可选，为了向后兼容先保留）
        # cursor.execute("ALTER TABLE monitor_records DROP COLUMN private_key")

        print("✅ 私钥数据迁移完成")
        print("⚠️  注意：旧的private_key字段已保留以确保向后兼容，可以手动删除")

        return True

    except Exception as e:
        print(f"❌ 迁移过程中出现错误: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


def update_database():
    """更新数据库结构"""

    print("🔧 正在更新数据库结构...")

    # 连接数据库
    conn = sqlite3.connect('config.db')
    cursor = conn.cursor()

    try:
        # 检查monitor_records表是否已有private_key_id字段
        cursor.execute("PRAGMA table_info(monitor_records)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'private_key_id' not in columns:
            print("📝 添加 private_key_id 字段...")
            cursor.execute("ALTER TABLE monitor_records ADD COLUMN private_key_id INTEGER")
            print("✅ private_key_id 字段添加成功")
        else:
            print("✅ private_key_id 字段已存在")

        # 检查是否已有private_keys表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='private_keys'")
        if not cursor.fetchone():
            print("📝 创建 private_keys 表...")
            cursor.execute("""
                CREATE TABLE private_keys (
                    id INTEGER PRIMARY KEY,
                    nickname VARCHAR NOT NULL,
                    private_key TEXT NOT NULL,
                    public_key VARCHAR NOT NULL,
                    created_at DATETIME,
                    updated_at DATETIME
                )
            """)
            print("✅ private_keys 表创建成功")
        else:
            print("✅ private_keys 表已存在")

        # 提交更改
        conn.commit()
        print("✅ 数据库结构更新完成")

        return True

    except Exception as e:
        print(f"❌ 更新数据库时出错: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    print("🚀 开始迁移私钥数据...")
    success = migrate_private_keys()

    if success:
        print("\n✅ 迁移完成！现在可以使用新的私钥管理功能了。")
        print("📝 请访问 http://localhost:8000/keys 管理您的私钥")
    else:
        print("\n❌ 迁移失败，请检查错误信息并重试")
        sys.exit(1)

    print("🚀 开始更新数据库...")
    success = update_database()
    if success:
        print("\n✅ 数据库更新成功！现在可以启动应用了。")
        print("📝 请运行: python main.py")
    else:
        print("\n❌ 数据库更新失败")
        sys.exit(1)
