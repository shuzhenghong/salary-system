import sqlite3
import json
from datetime import datetime

def cleanup_duplicate_linkages():
    """清理 field_linkage 表中的重复数据"""
    
    print("=" * 60)
    print("🔧 CSV导入数据清理工具")
    print("=" * 60)
    print(f"⏰ 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    conn = sqlite3.connect('salary.db')
    cursor = conn.cursor()
    
    # 1. 统计当前数据
    print("📊 当前数据统计:")
    print("-" * 40)
    
    cursor.execute("SELECT COUNT(*) FROM staff_field_meta")
    total_fields = cursor.fetchone()[0]
    print(f"字段总数: {total_fields}")
    
    cursor.execute("SELECT COUNT(*) FROM field_linkage")
    total_linkages_before = cursor.fetchone()[0]
    print(f"联动记录总数(清理前): {total_linkages_before}")
    
    # 2. 查找并删除重复的联动配置
    print("\n🔍 检查重复数据...")
    print("-" * 40)
    
    # 找出所有重复的记录
    cursor.execute("""
        SELECT source_field_code, source_option_value, target_field_code, target_option_value, COUNT(*) as cnt
        FROM field_linkage 
        GROUP BY source_field_code, source_option_value, target_field_code, target_option_value 
        HAVING cnt > 1
        ORDER BY cnt DESC
    """)
    
    duplicates = cursor.fetchall()
    
    if not duplicates:
        print("✅ 没有发现重复数据！")
    else:
        print(f"⚠️  发现 {len(duplicates)} 组重复数据：\n")
        
        total_duplicates = 0
        for dup in duplicates:
            src_field, src_val, tgt_field, tgt_val, count = dup
            print(f"  - {src_field}.{src_val} -> {tgt_field}.{tgt_val} (重复 {count} 次)")
            total_duplicates += (count - 1)
        
        print(f"\n   总共需要删除 {total_duplicates} 条重复记录")
        
        # 删除重复记录（保留第一条）
        print("\n🗑️  开始清理...")
        
        # 创建临时表存储要保留的记录
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS temp_linkage_keep AS
            SELECT MIN(id) as id 
            FROM field_linkage 
            GROUP BY source_field_code, source_option_value, target_field_code, target_option_value
        """)
        
        # 删除不在保留列表中的记录
        cursor.execute("""
            DELETE FROM field_linkage 
            WHERE id NOT IN (SELECT id FROM temp_linkage_keep)
        """)
        
        # 删除临时表
        cursor.execute("DROP TABLE temp_linkage_keep")
        
        conn.commit()
        
        cursor.execute("SELECT COUNT(*) FROM field_linkage")
        total_linkages_after = cursor.fetchone()[0]
        
        deleted_count = total_linkages_before - total_linkages_after
        
        print(f"✅ 清理完成！")
        print(f"   删除了 {deleted_count} 条重复记录")
        print(f"   剩余联动记录: {total_linkages_after} 条")
    
    # 3. 验证每个字段的联动配置
    print("\n✅ 各字段联动配置详情:")
    print("-" * 40)
    
    cursor.execute("""
        SELECT f.field_code, f.field_name, f.link_field, 
               (SELECT COUNT(*) FROM field_linkage l WHERE l.target_field_code = f.field_code) as linkage_count
        FROM staff_field_meta f
        WHERE f.link_field IS NOT NULL AND f.link_field != ''
        ORDER BY f.sort_num, f.id
    """)
    
    fields_with_linkage = cursor.fetchall()
    
    if not fields_with_linkage:
        print("  （没有字段配置了联动）")
    else:
        for field in fields_with_linkage:
            code, name, link_field, count = field
            status = "✅" if count > 0 else "⚠️"
            print(f"  {status} [{code}] {name}")
            print(f"      联动字段: {link_field}, 联动规则数: {count}")
            
            # 显示具体的联动规则
            if count > 0:
                cursor.execute("""
                    SELECT source_option_value, GROUP_CONCAT(target_option_value, ', ') as targets
                    FROM field_linkage 
                    WHERE target_field_code = ?
                    GROUP BY source_option_value
                """, [code])
                
                rules = cursor.fetchall()
                for rule in rules:
                    src_opt, tgt_opts = rule
                    print(f"         • 当[{link_field}]={src_opt} → 显示: {tgt_opts}")
    
    # 4. 数据完整性检查
    print("\n🔍 数据完整性检查:")
    print("-" * 40)
    
    # 检查孤立的联动记录（指向不存在的字段）
    cursor.execute("""
        SELECT DISTINCT l.target_field_code
        FROM field_linkage l
        LEFT JOIN staff_field_meta f ON l.target_field_code = f.field_code
        WHERE f.id IS NULL
    """)
    
    orphan_targets = [row[0] for row in cursor.fetchall()]
    
    cursor.execute("""
        SELECT DISTINCT l.source_field_code
        FROM field_linkage l
        LEFT JOIN staff_field_meta f ON l.source_field_code = f.field_code
        WHERE f.id IS NULL
    """)
    
    orphan_sources = [row[0] for row in cursor.fetchall()]
    
    orphan_fields = set(orphan_targets + orphan_sources)
    
    if orphan_fields:
        print(f"⚠️  发现 {len(orphan_fields)} 个孤立字段引用:")
        for field in orphan_fields:
            print(f"   - {field} (在field_linkage中但不存在于staff_field_meta)")
            
        # 删除孤立记录
        print("\n🗑️  清理孤立记录...")
        
        for field in orphan_fields:
            cursor.execute("DELETE FROM field_linkage WHERE target_field_code=? OR source_field_code=?", [field, field])
            deleted = cursor.rowcount
            if deleted > 0:
                print(f"   删除了 {deleted} 条关于 {field} 的联动记录")
        
        conn.commit()
        print("✅ 孤立记录已清理")
    else:
        print("✅ 所有联动记录都指向有效的字段")
    
    # 5. 最终统计
    print("\n" + "=" * 60)
    print("📈 最终统计:")
    print("=" * 60)
    
    cursor.execute("SELECT COUNT(*) FROM staff_field_meta")
    final_fields = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM field_linkage")
    final_linkages = cursor.fetchone()[0]
    
    print(f"字段总数: {final_fields}")
    print(f"联动记录总数: {final_linkages}")
    print()
    
    if final_linkages < total_linkages_before:
        saved = total_linkages_before - final_linkages
        print(f"✨ 节省空间: 删除了 {saved} 条冗余数据 ({((saved/total_linkages_before)*100):.1f}%)")
    
    print("\n✅ 数据清理完成！")
    print("=" * 60)
    
    conn.close()

if __name__ == '__main__':
    try:
        cleanup_duplicate_linkages()
    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
