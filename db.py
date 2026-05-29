import sqlite3
import os
import json
from datetime import datetime, timedelta

_DATA_DIR = os.environ.get('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(_DATA_DIR, 'salary.db')

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS sys_user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'operator',
            create_time TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS sys_settings (
            key TEXT PRIMARY KEY,
            value TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS staff_field_meta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            field_code TEXT UNIQUE NOT NULL,
            field_name TEXT NOT NULL,
            field_type TEXT DEFAULT 'text',
            default_val TEXT DEFAULT '',
            options TEXT DEFAULT '',
            link_field TEXT DEFAULT '',
            show_in_list INTEGER DEFAULT 0,
            sort_num INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS field_options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            field_code TEXT NOT NULL,
            option_value TEXT NOT NULL,
            option_label TEXT NOT NULL,
            sort_num INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS field_linkage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_field_code TEXT NOT NULL,
            source_option_value TEXT NOT NULL,
            target_field_code TEXT NOT NULL,
            target_option_value TEXT NOT NULL,
            create_time TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(source_field_code, source_option_value, target_field_code, target_option_value)
        );

        CREATE TABLE IF NOT EXISTS staff_base (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            gender TEXT DEFAULT '',
            dept TEXT DEFAULT '',
            unit TEXT DEFAULT '',
            birth_date TEXT DEFAULT '',
            work_start_date TEXT DEFAULT '',
            status TEXT DEFAULT '在职',
            is_locked INTEGER DEFAULT 0,
            retirement_date TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS staff_field_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            field_code TEXT NOT NULL,
            field_val TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS staff_assessment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            year INTEGER NOT NULL,
            grade TEXT NOT NULL,
            remark TEXT DEFAULT '',
            create_time TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS staff_change_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            staff_name TEXT NOT NULL,
            field_name TEXT NOT NULL,
            old_value TEXT DEFAULT '',
            new_value TEXT DEFAULT '',
            operator TEXT DEFAULT '',
            create_time TEXT DEFAULT (datetime('now','localtime')),
            change_source TEXT DEFAULT '',
            change_month TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS salary_book (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_name TEXT NOT NULL,
            remark TEXT DEFAULT '',
            create_time TEXT DEFAULT (datetime('now','localtime')),
            is_active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS salary_book_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            field_code TEXT NOT NULL,
            field_name TEXT NOT NULL,
            sort_num INTEGER DEFAULT 0,
            is_calc INTEGER DEFAULT 0,
            formula TEXT DEFAULT '',
            FOREIGN KEY (book_id) REFERENCES salary_book(id)
        );

        CREATE TABLE IF NOT EXISTS salary_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            value_str TEXT DEFAULT '',
            value_num REAL DEFAULT 0,
            update_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (staff_id) REFERENCES staff_base(id),
            FOREIGN KEY (book_id) REFERENCES salary_book(id),
            UNIQUE(staff_id, book_id)
        );

        CREATE TABLE IF NOT EXISTS salary_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            item_type TEXT DEFAULT 'income',
            filter_condition TEXT DEFAULT '[]',
            calc_formula TEXT DEFAULT '',
            sort_num INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS salary_calc_record (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            dept TEXT DEFAULT '',
            unit TEXT DEFAULT '',
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            staff_count INTEGER DEFAULT 0,
            total_income REAL DEFAULT 0,
            total_deduct REAL DEFAULT 0,
            total_real REAL DEFAULT 0,
            create_time TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS salary_month_record (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            calc_record_id INTEGER DEFAULT 0,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            item_values TEXT DEFAULT '{}',
            total_income REAL DEFAULT 0,
            total_deduct REAL DEFAULT 0,
            real_salary REAL DEFAULT 0,
            create_time TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS dept_unit_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dept TEXT NOT NULL,
            unit TEXT NOT NULL,
            sort_num INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS op_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 0,
            username TEXT DEFAULT '',
            action TEXT DEFAULT '',
            detail TEXT DEFAULT '',
            ip TEXT DEFAULT '',
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    c.execute("SELECT COUNT(*) as cnt FROM sys_user")
    if c.fetchone()['cnt'] == 0:
        import secrets as _secrets
        import string as _string
        alphabet = _string.ascii_letters + _string.digits + '!@#$%'
        temp_password = ''.join(_secrets.choice(alphabet) for _ in range(12))

        import hashlib as _hashlib
        salt = _secrets.token_hex(16)
        hashed = _hashlib.sha256((temp_password + salt).encode()).hexdigest()
        stored_password = f"{salt}${hashed}"

        c.execute("INSERT INTO sys_user (username, password, role) VALUES (?, ?, ?)",
                  ('admin', stored_password, 'admin'))
        print("=" * 60)
        print("  首次启动 - 管理员账户已创建")
        print(f"   用户名: admin")
        print(f"   初始密码: {temp_password}")
        print("   请立即登录并修改密码！")
        print("=" * 60)

    c.execute("SELECT COUNT(*) as cnt FROM pragma_table_info('staff_base') WHERE name='retirement_date'")
    if c.fetchone()['cnt'] == 0:
        c.execute("ALTER TABLE staff_base ADD COLUMN retirement_date TEXT DEFAULT ''")
        print("  数据库升级：添加退休日期字段")

    c.execute("SELECT id, birth_date, gender FROM staff_base WHERE birth_date != '' AND gender != ''")
    all_staff = c.fetchall()
    if all_staff:
        updated_count = 0
        for s in all_staff:
            birth_raw = str(s['birth_date'] or '').strip()
            if ' ' in birth_raw:
                birth_raw = birth_raw.split(' ')[0]
            if '/' in birth_raw:
                birth_raw = birth_raw.replace('/', '-')
            
            retire_date = calculate_retirement_date(birth_raw, s['gender'])
            if retire_date:
                c.execute("UPDATE staff_base SET retirement_date=? WHERE id=?", [retire_date, s['id']])
                updated_count += 1
        if updated_count > 0:
            print(f"  退休日期更新：已为 {updated_count} 名人员重新计算退休日期")

    conn.commit()
    conn.close()

def query_db(sql, args=None, one=False):
    conn = get_db()
    try:
        c = conn.execute(sql, args or [])
        if one:
            result = c.fetchone()
        else:
            result = c.fetchall()
        return result
    finally:
        conn.close()

def execute_db(sql, args=None):
    conn = get_db()
    try:
        c = conn.execute(sql, args or [])
        conn.commit()
        return c.lastrowid
    finally:
        conn.close()

def execute_db_many(sql, args_list):
    conn = get_db()
    try:
        c = conn.executemany(sql, args_list)
        conn.commit()
        return c.rowcount
    finally:
        conn.close()

def add_log(user_id, username, action, detail='', ip=''):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO op_log (user_id, username, action, detail, ip) VALUES (?,?,?,?,?)",
            [user_id, username, action, str(detail)[:500], ip]
        )
        conn.commit()
    except Exception as e:
        print(f'日志写入失败: {e}')
    finally:
        conn.close()

def clean_date_format(date_str):
    """
    清洗日期格式为 YYYY-MM
    支持的输入格式：
    - 1966-05, 1966-5
    - 1966-05-01, 1966/05/01
    - 1966/05, 1966/5
    - 1966-05-01 00:00:00
    - 1966年5月, 1966.5.1
    """
    if not date_str:
        return ''
    
    s = str(date_str).strip()
    
    if not s or s in ['nan', 'None', '', '0', '-']:
        return ''
    
    s = s.replace('年', '-').replace('月', '').replace('日', '')
    s = s.replace('/', '-')
    s = s.replace('.', '-')
    
    if ' ' in s:
        s = s.split(' ')[0]
    
    parts = s.split('-')
    
    if len(parts) >= 2:
        year = parts[0].strip()
        month = parts[1].strip()
        
        if year.isdigit() and len(year) == 4 and month.isdigit():
            month_int = int(month)
            if 1 <= month_int <= 12:
                return f"{year}-{month_int:02d}"
            else:
                return ''
        else:
            return ''
    
    return ''

def calculate_retirement_date(birth_date, gender):
    """
    计算退休日期
    男职工：原法定退休年龄60周岁，2025年后每4个月延迟1个月，最多到63周岁
    女职工：原法定退休年龄50周岁，2025年后每2个月延迟1个月，最多到55周岁
    
    计算逻辑：
    1. 先计算基础退休日期（按原法定年龄）
    2. 如果基础退休日期 > 2024-12（政策实施时间），则受延迟政策影响
    3. 计算从基础退休日到2024-12的月数差
    4. 月数差 ÷ 延迟间隔 = 向上取整得到间隔数
    5. 总延迟 = 间隔数 × 每月延迟量
    6. 实际延迟 = min(总延迟, 最大允许延迟)
    """
    if not birth_date or not gender:
        return None
    
    birth_clean = birth_date.strip()
    if ' ' in birth_clean:
        birth_clean = birth_clean.split(' ')[0]
    if '/' in birth_clean:
        birth_clean = birth_clean.replace('/', '-')
    
    try:
        if len(birth_clean) == 7:  # YYYY-M 或 YYYY-MM
            birth = datetime.strptime(birth_clean, '%Y-%m')
        elif len(birth_clean) == 10:  # YYYY-MM-DD
            birth = datetime.strptime(birth_clean, '%Y-%m-%d')
            birth_clean = birth.strftime('%Y-%m')
            birth = datetime.strptime(birth_clean, '%Y-%m')
        else:
            return None
    except:
        try:
            birth = datetime.strptime(birth_clean, '%Y/%m')
        except:
            return None
    
    from dateutil.relativedelta import relativedelta
    import math
    
    if gender == '男':
        base_age = 60
        max_age = 63
        delay_interval_months = 4
        delay_per_interval = 1
    elif gender == '女':
        base_age = 50
        max_age = 55
        delay_interval_months = 2
        delay_per_interval = 1
    else:
        return None
    
    retirement = birth + relativedelta(years=base_age)
    
    policy_end_year = 2024
    policy_end_month = 12
    policy_end = datetime(policy_end_year, policy_end_month, 28)
    
    if retirement > policy_end:
        months_diff = (retirement.year - policy_end_year) * 12 + (retirement.month - policy_end_month)
        
        if months_diff > 0:
            intervals = math.ceil(months_diff / delay_interval_months)
            
            total_delay = intervals * delay_per_interval
            
            max_delay_months = (max_age - base_age) * 12
            actual_delay = min(total_delay, max_delay_months)
            
            if actual_delay > 0:
                retirement += relativedelta(months=actual_delay)
    
    return retirement.strftime('%Y-%m')

def check_retirement_status(retirement_date):
    """
    检查退休状态
    返回: (status, message)
    status: 'normal' - 正常, 'approaching' - 接近退休, 'retired' - 已退休/超龄
    """
    if not retirement_date:
        return ('normal', '')
    
    try:
        retire = datetime.strptime(retirement_date.strip(), '%Y-%m')
    except:
        return ('normal', '')
    
    now = datetime.now()
    current_month = now.strftime('%Y-%m')
    
    if retire.strftime('%Y-%m') <= current_month:
        months_overdue = (now.year - retire.year) * 12 + (now.month - retire.month)
        if months_overdue >= 0:
            return ('retired', f'已达到退休时间（{retire.strftime("%Y年%m月")}），已超{months_overdue}个月')
    
    months_until_retire = (retire.year - now.year) * 12 + (retire.month - now.month)
    if 0 < months_until_retire <= 12:
        return ('approaching', f'即将于{retire.strftime("%Y年%m月")}退休，还有{months_until_retire}个月')
    
    return ('normal', f'预计{retire.strftime("%Y年%m月")}退休')
