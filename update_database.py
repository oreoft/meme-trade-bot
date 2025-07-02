#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库结构更新脚本
"""

import logging
import sqlite3
import sys
from datetime import datetime

from birdeye_api import BirdEyeAPI

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

def update_database_schema():
    """更新数据库结构，添加token元数据字段"""
    logger.info("🔧 正在更新数据库结构...")

    conn = sqlite3.connect('config.db')
    cursor = conn.cursor()

    try:
        # 检查monitor_records表结构
        cursor.execute("PRAGMA table_info(monitor_records)")
        columns = [col[1] for col in cursor.fetchall()]

        # 需要添加的新字段
        new_fields = [
            ('token_name', 'VARCHAR'),
            ('token_symbol', 'VARCHAR'),
            ('token_logo_uri', 'VARCHAR'),
            ('token_decimals', 'INTEGER')
        ]

        # 逐个添加缺失的字段
        for field_name, field_type in new_fields:
            if field_name not in columns:
                logger.info(f"📝 添加字段: {field_name}")
                cursor.execute(f"ALTER TABLE monitor_records ADD COLUMN {field_name} {field_type}")
                logger.info(f"✅ {field_name} 字段添加成功")
            else:
                logger.info(f"✅ {field_name} 字段已存在")

        # 提交更改
        conn.commit()
        logger.info("✅ 数据库结构更新完成")
        return True

    except Exception as e:
        logger.error(f"❌ 更新数据库结构失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def fetch_token_metadata_for_existing_records():
    """为现有的监控记录获取token元数据"""
    logger.info("🔍 正在为现有监控记录获取Token元数据...")

    conn = sqlite3.connect('config.db')
    cursor = conn.cursor()

    try:
        # 获取所有没有token元数据的监控记录
        cursor.execute("""
            SELECT id, name, token_address 
            FROM monitor_records 
            WHERE token_name IS NULL OR token_name = ''
        """)
        records = cursor.fetchall()

        if not records:
            logger.info("✅ 所有监控记录都已有Token元数据")
            return True

        logger.info(f"📋 找到 {len(records)} 个需要更新的监控记录")

        # 创建BirdEye API实例
        api = BirdEyeAPI()

        success_count = 0
        failed_count = 0

        for record_id, record_name, token_address in records:
            try:
                logger.info(f"🔄 处理记录: {record_name} ({token_address})")

                # 获取token元数据
                token_meta_data = api.get_token_meta_data(token_address)

                if token_meta_data:
                    token_name = token_meta_data.get('name')
                    token_symbol = token_meta_data.get('symbol')
                    token_logo_uri = token_meta_data.get('logo_uri')
                    token_decimals = token_meta_data.get('decimals')

                    # 更新记录
                    cursor.execute("""
                        UPDATE monitor_records 
                        SET token_name = ?, token_symbol = ?, token_logo_uri = ?, token_decimals = ?, updated_at = ?
                        WHERE id = ?
                    """, (token_name, token_symbol, token_logo_uri, token_decimals, datetime.utcnow(), record_id))

                    logger.info(f"  ✅ 已更新: {token_name or 'Unknown'} ({token_symbol or 'N/A'})")
                    success_count += 1
                else:
                    logger.warning(f"  ⚠️  无法获取Token元数据: {token_address}")
                    failed_count += 1

            except Exception as e:
                logger.error(f"  ❌ 处理记录失败 [{record_name}]: {e}")
                failed_count += 1

        # 提交更改
        conn.commit()

        logger.info(f"📊 Token元数据更新完成:")
        logger.info(f"  ✅ 成功: {success_count} 个")
        logger.info(f"  ❌ 失败: {failed_count} 个")

        return True

    except Exception as e:
        logger.error(f"❌ 获取Token元数据失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def main():
    """主函数"""
    logger.info("🚀 开始数据库更新过程...")

    # 1. 更新数据库结构
    if not update_database_schema():
        logger.error("❌ 数据库结构更新失败，终止操作")
        return

    # 2. 为现有记录获取token元数据
    if not fetch_token_metadata_for_existing_records():
        logger.error("❌ Token元数据获取失败")
        return

    logger.info("🎉 数据库更新完成！")

if __name__ == "__main__":
    # 先运行旧的数据库更新（确保基础结构存在）
    print("🚀 开始更新数据库...")
    success = update_database()

    if success:
        print("✅ 基础数据库结构更新成功！")
        # 运行新的主函数（添加token元数据）
        main()
    else:
        print("\n❌ 数据库更新失败")
        sys.exit(1)
