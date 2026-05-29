import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlite3
import json
from db import init_db, get_db

DB_PATH = 'salary_system.db'

def init_test_data():
    print("=" * 50)
    print("  初始化数据库...")
    print("=" * 50)
    
    init_db()
    conn = get_db()
    c = conn.cursor()
    
    print("\n" + "=" * 50)
    print("  创建联动测试数据")
    print("=" * 50)
    
    # 1. 创建测试部门-单位人员数据（用于部门-单位联动）
    print("\n[1/3] 创建测试部门和人员数据...")
    
    test_staff = [
        ('张三', '男', '财务部', '会计科', '1990-01-15', '2015-03-01', '在职'),
        ('李四', '女', '财务部', '出纳科', '1992-05-20', '2016-07-15', '在职'),
        ('王五', '男', '技术部', '开发一组', '1988-11-08', '2012-02-01', '在职'),
        ('赵六', '女', '技术部', '开发二组', '1995-03-25', '2018-09-10', '在职'),
        ('孙七', '男', '技术部', '测试组', '1991-07-12', '2014-06-20', '在职'),
        ('周八', '女', '行政部', '综合办', '1993-09-30', '2017-04-05', '在职'),
        ('吴九', '男', '人事处', '招聘组', '1989-04-18', '2013-11-22', '在职'),
        ('郑十', '女', '人事处', '培训组', '1994-12-05', '2019-01-08', '在职'),
    ]
    
    c.execute("DELETE FROM staff_field_data")
    c.execute("DELETE FROM staff_base")
    
    for staff in test_staff:
        c.execute(
            "INSERT INTO staff_base (name, gender, dept, unit, birth_date, work_start_date, status) VALUES (?,?,?,?,?,?,?)",
            staff
        )
    
    print(f"   已插入 {len(test_staff)} 条测试人员")
    
    # 2. 创建自定义字段：部门类型 + 岗位（用于字段联动）
    print("\n[2/3] 创建联动测试字段...")
    
    c.execute("DELETE FROM staff_field_meta WHERE field_code IN ('dept_type', 'position')")
    
    # 字段1: 部门类型 (select类型，作为联动源)
    c.execute("""INSERT INTO staff_field_meta 
        (field_code, field_name, field_type, default_val, options, is_active, link_field, link_options, show_in_list, sort_num)
        VALUES (?, ?, ?, ?, ?, 1, '', '{}', 1, 10)""", 
        ['dept_type', '部门类型', 'select', '', '行政岗,技术岗,业务岗']
    )
    
    # 字段2: 岗位 (select类型，联动到部门类型)
    link_options = json.dumps({
        "行政岗": "文员,前台,司机,后勤",
        "技术岗": "前端工程师,后端工程师,测试工程师",
        "业务岗": "销售经理,客户代表,市场专员"
    }, ensure_ascii=False)
    
    c.execute("""INSERT INTO staff_field_meta 
        (field_code, field_name, field_type, default_val, options, is_active, link_field, link_options, show_in_list, sort_num)
        VALUES (?, ?, ?, ?, ?, 1, ?, ?, 1, 11)""", 
        ['position', '岗位', 'select', '', '', 'dept_type', link_options]
    )
    
    print("   已创建字段:")
    print("     - 部门类型 (dept_type): 下拉选项 = 行政岗, 技术岗, 业务岗")
    print("     - 岗位 (position): 联动到 [部门类型]")
    print("       联动映射:")
    print("         行政岗 -> 文员, 前台, 司机, 后勤")
    print("         技术岗 -> 前端工程师, 后端工程师, 测试工程师")
    print("         业务岗 -> 销售经理, 客户代表, 市场专员")
    
    # 3. 给部分人员设置字段值
    print("\n[3/3] 设置人员字段值...")
    
    staff_ids = list(c.execute("SELECT id FROM staff_base"))
    
    field_values = [
        (staff_ids[0][0], 'dept_type', '行政岗'),
        (staff_ids[0][0], 'position', '文员'),
        (staff_ids[2][0], 'dept_type', '技术岗'),
        (staff_ids[2][0], 'position', '后端工程师'),
        (staff_ids[4][0], 'dept_type', '技术岗'),
        (staff_ids[4][0], 'position', '测试工程师'),
        (staff_ids[5][0], 'dept_type', '行政岗'),
        (staff_ids[5][0], 'position', '前台'),
        (staff_ids[6][0], 'dept_type', '业务岗'),
        (staff_ids[6][0], 'position', '销售经理'),
    ]
    
    for fv in field_values:
        c.execute("INSERT INTO staff_field_data (staff_id, field_code, field_val) VALUES (?,?,?)", fv)
    
    print(f"   已设置 {len(field_values)} 条字段值")
    
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 50)
    print("  测试数据创建完成！")
    print("=" * 50)
    print("\n请刷新浏览器页面测试以下功能:")
    print("")
    print("【功能1】部门-单位联动（搜索区域）")
    print("  1. 打开 人员档案管理 页面")
    print("  2. 在搜索区选择部门（如：财务部、技术部）")
    print("  3. 单位下拉框应自动更新为对应选项")
    print("")
    print("【功能2】部门-单位联动（编辑表单）")
    print("  1. 点击新增或编辑人员")
    print("  2. 选择部门后，单位自动联动")
    print("")
    print("【功能3】自定义字段联动（新功能）")
    print("  1. 编辑人员时找到「部门类型」和「岗位」字段")
    print("  2. 选择「部门类型」= 技术岗")
    print("  3. 「岗位」下拉框应变为: 前端工程师, 后端工程师, 测试工程师")

if __name__ == '__main__':
    init_test_data()
