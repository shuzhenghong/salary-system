import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlite3
import json
from db import init_db, get_db

def migrate_linkages():
    print("=" * 50)
    print("  迁移字段联动数据到关联表")
    print("=" * 50)

    init_db()
    conn = get_db()
    c = conn.cursor()

    # 获取所有有联动配置的字段
    fields = c.execute("SELECT id, field_code, link_field, link_options FROM staff_field_meta WHERE link_field IS NOT NULL AND link_options IS NOT NULL AND link_options != ''").fetchall()

    migrated_count = 0
    for f in fields:
        fid, target_code, source_code, link_options_str = f
        print(f"\n处理字段: {target_code} (ID: {fid})")

        try:
            link_options = json.loads(link_options_str)
            
            # 删除旧的联动记录（避免重复）
            c.execute("DELETE FROM field_linkage WHERE target_field_code = ? AND source_field_code = ?", [target_code, source_code])
            
            count = 0
            for src_opt, tgt_opts_str in link_options.items():
                tgt_opts = tgt_opts_str.split(',')
                for tgt_opt in tgt_opts:
                    tgt_opt = tgt_opt.strip()
                    if tgt_opt:
                        c.execute(
                            "INSERT INTO field_linkage (source_field_code, source_option_value, target_field_code, target_option_value) VALUES (?, ?, ?, ?)",
                            [source_code, src_opt, target_code, tgt_opt]
                        )
                        count += 1
            
            migrated_count += count
            print(f"  - 导入了 {count} 条联动规则")

            # 清空 link_options 字段（可选）
            # c.execute("UPDATE staff_field_meta SET link_options = '' WHERE id = ?", [fid])

        except Exception as e:
            print(f"  - 解析失败: {e}")
            continue

    conn.commit()
    print(f"\n迁移完成！共导入 {migrated_count} 条联动规则。")

if __name__ == '__main__':
    migrate_linkages()
