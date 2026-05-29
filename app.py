import os
import json
import shutil
import sqlite3
import hashlib
import secrets
import string
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, send_file, session, g
from db import init_db, get_db, query_db, execute_db, execute_db_many, add_log, DB_PATH
from formula_engine import evaluate_formula, match_filter_conditions

DATA_DIR = os.environ.get('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(DATA_DIR, 'static')

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='')
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

def hash_password(password):
    """使用SHA256+盐值加密密码"""
    salt = os.urandom(16).hex()
    hashed = hashlib.sha256((password + salt).encode('utf-8')).hexdigest()
    return f"{salt}${hashed}"

def verify_password(stored_password, input_password):
    """验证密码"""
    if not stored_password or not input_password:
        return False
    try:
        parts = stored_password.split('$')
        if len(parts) != 2:
            return stored_password == input_password
        salt, hashed = parts
        new_hash = hashlib.sha256((input_password + salt).encode('utf-8')).hexdigest()
        return new_hash == hashed
    except Exception as e:
        print(f'密码验证异常: {e}')
        return False

def is_password_hashed(password):
    """判断密码是否已加密（包含盐值$哈希格式）"""
    if not password:
        return False
    parts = password.split('$')
    return len(parts) == 2 and len(parts[0]) == 32 and len(parts[1]) == 64

def generate_temp_password(length=12):
    """生成强随机密码"""
    alphabet = string.ascii_letters + string.digits + '!@#$%'
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def migrate_plain_passwords():
    """将明文密码迁移为加密格式"""
    try:
        users = query_db("SELECT id, username, password FROM sys_user", [])
        migrated_count = 0
        for user in users:
            pwd = user['password']
            if not is_password_hashed(pwd):
                new_pwd = hash_password(pwd)
                execute_db("UPDATE sys_user SET password=? WHERE id=?", [new_pwd, user['id']])
                migrated_count += 1
                print(f'  迁移用户 {user["username"]} 的密码')
        
        if migrated_count > 0:
            print(f'✅ 密码迁移完成：{migrated_count} 个账户')
        return migrated_count
    except Exception as e:
        print(f'❌ 密码迁移失败: {e}')
        return 0

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'code': 401, 'msg': '请先登录'}), 401
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'code': 401, 'msg': '请先登录'}), 401
        if session.get('role') != 'admin':
            return jsonify({'code': 403, 'msg': '需要管理员权限'}), 403
        return f(*args, **kwargs)
    return decorated

def generate_csrf_token():
    """生成CSRF Token"""
    import secrets
    token = secrets.token_hex(32)
    session['_csrf_token'] = token
    return token

def validate_csrf_token():
    """验证CSRF Token"""
    if request.method in ['GET', 'HEAD', 'OPTIONS']:
        return True
    
    token = session.get('_csrf_token')
    if not token:
        return False
    
    # 从Header或表单获取Token
    request_token = request.headers.get('X-CSRFToken') or request.form.get('_csrf_token')
    
    # 使用时间安全比较（防止时序攻击）
    import hmac
    try:
        return hmac.compare_digest(token, str(request_token))
    except Exception:
        return False

@app.after_request
def add_csrf_header(response):
    """在每个响应中添加CSRF Token"""
    if 'user_id' in session and '_csrf_token' in session:
        response.headers['X-CSRFToken'] = session['_csrf_token']
    return response

def get_field_link_options(field_code):
    """从 field_linkage 表读取字段的联动配置，返回字典格式"""
    rows = query_db(
        "SELECT source_option_value, target_option_value FROM field_linkage WHERE target_field_code=?",
        [field_code]
    )
    link_options = {}
    for r in rows:
        src_opt = r['source_option_value']
        tgt_val = r['target_option_value']
        if src_opt not in link_options:
            link_options[src_opt] = []
        link_options[src_opt].append(tgt_val)
    
    result = {}
    for key in link_options:
        result[key] = ','.join(link_options[key])
    return result

def enrich_field_with_linkages(field_dict):
    """为字段字典添加联动配置（从 field_linkage 表读取）"""
    if field_dict.get('link_field'):
        field_dict['link_options'] = get_field_link_options(field_dict.get('field_code', '') or field_dict.get('id', ''))
    else:
        field_dict['link_options'] = {}
    return field_dict

def _log(action, detail=''):
    add_log(session.get('user_id', 0), session.get('username', ''), action, detail, request.remote_addr)

def safe_get_page_params():
    """安全获取分页参数，防止边界问题"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 15))
        
        # 边界检查
        page = max(1, min(page, 10000))  # 防止超大页码
        per_page = max(1, min(per_page, 100))  # 限制每页最多100条
        
        return page, per_page
    except (ValueError, TypeError):
        return 1, 15

import logging

# 确保日志目录存在
LOG_DIR = os.path.join(DATA_DIR, 'logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOG_DIR, 'app.log'), encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)
logger.info('日志系统初始化完成')

@app.errorhandler(400)
def bad_request(e):
    return jsonify({'code': 400, 'msg': '请求参数错误'}), 400

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'code': 404, 'msg': '接口不存在'}), 404
    return e.get_description(), 404

@app.errorhandler(500)
def internal_error(e):
    print(f'服务器内部错误: {str(e)}')
    return jsonify({'code': 500, 'msg': '服务器内部错误，请稍后重试'}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    error_detail = traceback.format_exc()
    
    # 记录详细日志到服务器（不返回给客户端）
    logger.error(f'未捕获异常: {type(e).__name__}: {str(e)}\n{error_detail}')
    
    if request.path.startswith('/api/'):
        # 生产环境只返回通用提示，开发环境可以返回详细信息
        if app.debug:
            return jsonify({'code': 500, 'msg': f'服务器错误: {str(e)}'}), 500
        else:
            return jsonify({'code': 500, 'msg': '服务器内部错误，请稍后重试'}), 500
    return jsonify({'code': 500, 'msg': '服务器内部错误'}), 500

@app.route('/')
def index():
    return send_from_directory(STATIC_DIR, 'login.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(STATIC_DIR, filename)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '')
    password = data.get('password', '')
    user = query_db("SELECT * FROM sys_user WHERE username = ?", [username], one=True)
    if not user or not verify_password(user['password'], password):
        return jsonify({'code': 400, 'msg': '用户名或密码错误'})
    
    if not is_password_hashed(user['password']):
        new_hashed_pwd = hash_password(password)
        execute_db("UPDATE sys_user SET password=? WHERE id=?", [new_hashed_pwd, user['id']])
    
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']
    add_log(user['id'], username, '登录', '用户登录系统', request.remote_addr)
    return jsonify({'code': 200, 'msg': '登录成功', 'data': {
        'id': user['id'], 'username': user['username'], 'role': user['role']
    }})

@app.route('/api/logout', methods=['POST'])
def logout():
    _log('退出', '用户退出系统')
    session.clear()
    return jsonify({'code': 200, 'msg': '已退出'})

@app.route('/api/user/info', methods=['GET'])
@login_required
def user_info():
    csrf_token = generate_csrf_token()
    return jsonify({'code': 200, 'data': {
        'id': session.get('user_id'),
        'username': session.get('username'),
        'role': session.get('role'),
        'csrf_token': csrf_token
    }})

@app.route('/api/user/list', methods=['GET'])
@admin_required
def get_users():
    page, per_page = safe_get_page_params()
    offset = (page - 1) * per_page
    
    rows = query_db("SELECT id, username, role, create_time FROM sys_user ORDER BY id LIMIT ? OFFSET ?", [per_page, offset])
    total = query_db("SELECT COUNT(*) as cnt FROM sys_user", [], one=True)['cnt']
    
    return jsonify({'code': 200, 'data': {
        'list': [dict(r) for r in rows],
        'total': total,
        'page': page,
        'per_page': per_page
    }})

@app.route('/api/user', methods=['POST'])
@admin_required
def add_user():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    role = data.get('role', 'operator')
    if not username or not password:
        return jsonify({'code': 400, 'msg': '用户名和密码不能为空'})
    if len(password) < 6:
        return jsonify({'code': 400, 'msg': '密码长度不能少于6位'})
    existing = query_db("SELECT id FROM sys_user WHERE username=?", [username], one=True)
    if existing:
        return jsonify({'code': 400, 'msg': '用户名已存在'})
    
    hashed_pwd = hash_password(password)
    execute_db("INSERT INTO sys_user (username, password, role) VALUES (?,?,?)", [username, hashed_pwd, role])
    _log('新增用户', f'新增用户: {username}')
    return jsonify({'code': 200, 'msg': '添加成功'})

@app.route('/api/user/<int:uid>', methods=['DELETE'])
@admin_required
def delete_user(uid):
    if uid == session.get('user_id'):
        return jsonify({'code': 400, 'msg': '不能删除自己'})
    execute_db("DELETE FROM sys_user WHERE id=?", [uid])
    _log('删除用户', f'删除用户ID: {uid}')
    return jsonify({'code': 200, 'msg': '删除成功'})

@app.route('/api/user/reset_password', methods=['POST'])
@admin_required
def reset_password():
    data = request.get_json()
    uid = data.get('user_id')
    new_pwd = data.get('new_password', '').strip()
    if not new_pwd:
        return jsonify({'code': 400, 'msg': '新密码不能为空'})
    if len(new_pwd) < 6:
        return jsonify({'code': 400, 'msg': '密码长度不能少于6位'})
    
    hashed_pwd = hash_password(new_pwd)
    execute_db("UPDATE sys_user SET password=? WHERE id=?", [hashed_pwd, uid])
    _log('重置密码', f'重置用户ID: {uid} 的密码')
    return jsonify({'code': 200, 'msg': '密码重置成功'})

@app.route('/api/user/<int:uid>', methods=['PUT'])
@admin_required
def update_user(uid):
    data = request.get_json()
    role = data.get('role', 'operator')
    password = data.get('password', '')
    if password:
        if len(password) < 6:
            return jsonify({'code': 400, 'msg': '密码长度不能少于6位'})
        hashed_pwd = hash_password(password)
        execute_db("UPDATE sys_user SET role=?, password=? WHERE id=?", [role, hashed_pwd, uid])
        _log('修改用户', f'修改用户ID: {uid} 角色和密码')
    else:
        execute_db("UPDATE sys_user SET role=? WHERE id=?", [role, uid])
        _log('修改用户', f'修改用户ID: {uid} 角色')
    return jsonify({'code': 200, 'msg': '更新成功'})

@app.route('/api/user/change_password', methods=['POST'])
@login_required
def change_password():
    data = request.get_json()
    old_pwd = data.get('old_password', '')
    new_pwd = data.get('new_password', '')
    user = query_db("SELECT * FROM sys_user WHERE id = ?", [session['user_id']], one=True)
    
    if not verify_password(user['password'], old_pwd):
        return jsonify({'code': 400, 'msg': '原密码错误'})
    if len(new_pwd) < 6:
        return jsonify({'code': 400, 'msg': '新密码长度不能少于6位'})
    
    hashed_new_pwd = hash_password(new_pwd)
    execute_db("UPDATE sys_user SET password = ? WHERE id = ?", [hashed_new_pwd, session['user_id']])
    _log('修改密码', '修改个人密码')
    return jsonify({'code': 200, 'msg': '密码修改成功'})

@app.route('/api/settings', methods=['GET'])
@admin_required
def get_settings():
    rows = query_db("SELECT * FROM sys_settings")
    settings = {r['key']: r['value'] for r in rows}
    return jsonify({'code': 200, 'data': settings})

@app.route('/api/settings', methods=['POST'])
@admin_required
def save_settings():
    data = request.get_json()
    for key, value in data.items():
        existing = query_db("SELECT key FROM sys_settings WHERE key=?", [key], one=True)
        if existing:
            execute_db("UPDATE sys_settings SET value=? WHERE key=?", [value, key])
        else:
            execute_db("INSERT INTO sys_settings (key, value) VALUES (?,?)", [key, value])
    _log('修改设置', f'修改系统设置: {json.dumps(data, ensure_ascii=False)}')
    return jsonify({'code': 200, 'msg': '保存成功'})

@app.route('/api/backup', methods=['POST'])
@admin_required
def backup_db():
    backup_dir = os.path.join(DATA_DIR, 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_dir, f'salary_backup_{ts}.db')
    shutil.copy2(DB_PATH, backup_path)
    _log('数据备份', f'备份文件: salary_backup_{ts}.db')
    return jsonify({'code': 200, 'msg': '备份成功', 'data': {'file': f'salary_backup_{ts}.db'}})

@app.route('/api/backup/list', methods=['GET'])
@admin_required
def list_backups():
    page, per_page = safe_get_page_params()
    offset = (page - 1) * per_page
    
    backup_dir = os.path.join(DATA_DIR, 'backups')
    if not os.path.exists(backup_dir):
        return jsonify({'code': 200, 'data': {'list': [], 'total': 0, 'page': 1, 'per_page': per_page}})
    files = [f for f in os.listdir(backup_dir) if f.endswith('.db')]
    files.sort(reverse=True)
    total = len(files)
    paginated = files[offset:offset + per_page]
    result = []
    for f in paginated:
        fp = os.path.join(backup_dir, f)
        result.append({'name': f, 'size': os.path.getsize(fp), 'time': datetime.fromtimestamp(os.path.getmtime(fp)).strftime('%Y-%m-%d %H:%M:%S')})
    return jsonify({'code': 200, 'data': {
        'list': result,
        'total': total,
        'page': page,
        'per_page': per_page
    }})

@app.route('/api/backup/restore', methods=['POST'])
@admin_required
def restore_db():
    data = request.get_json()
    filename = data.get('filename', '')
    
    # 文件名安全检查
    if not filename or '..' in filename or '/' in filename or '\\' in filename:
        return jsonify({'code': 400, 'msg': '非法文件名'})
    
    backup_dir = os.path.join(DATA_DIR, 'backups')
    backup_path = os.path.join(backup_dir, filename)
    
    # 检查文件是否存在
    if not os.path.exists(backup_path):
        return jsonify({'code': 400, 'msg': '备份文件不存在'})
    
    # 校验文件大小（不能为空或过小）
    file_size = os.path.getsize(backup_path)
    if file_size < 1024:  # 小于1KB可能是损坏的
        return jsonify({'code': 400, 'msg': f'备份文件可能已损坏（大小：{file_size}字节）'})
    
    # 校验是否为有效的SQLite文件
    try:
        import tempfile
        test_conn = sqlite3.connect(backup_path)
        test_conn.execute("SELECT count(*) FROM sqlite_master")
        test_conn.close()
    except Exception as e:
        logger.error(f'备份文件校验失败: {filename} - {str(e)}')
        return jsonify({'code': 400, 'msg': '无效的数据库文件或文件已损坏'})
    
    shutil.copy2(backup_path, DB_PATH)
    _log('数据恢复', f'恢复备份: {filename} (大小: {file_size/1024:.1f}KB)')
    return jsonify({'code': 200, 'msg': '恢复成功，请重启系统'})

@app.route('/api/backup/delete', methods=['POST'])
@admin_required
def delete_backup():
    data = request.get_json()
    filename = data.get('filename', '')
    backup_dir = os.path.join(DATA_DIR, 'backups')
    backup_path = os.path.join(backup_dir, filename)
    if not os.path.exists(backup_path):
        return jsonify({'code': 400, 'msg': '备份文件不存在'})
    if '..' in filename or '/' in filename or '\\' in filename:
        return jsonify({'code': 400, 'msg': '非法文件名'})
    os.remove(backup_path)
    _log('删除备份', f'删除备份: {filename}')
    return jsonify({'code': 200, 'msg': '删除成功'})

@app.route('/api/backup/download', methods=['GET'])
@admin_required
def download_backup():
    filename = request.args.get('filename', '')
    if not filename or '..' in filename or '/' in filename or '\\' in filename:
        return jsonify({'code': 400, 'msg': '非法文件名'})
    backup_dir = os.path.join(DATA_DIR, 'backups')
    backup_path = os.path.join(backup_dir, filename)
    if not os.path.exists(backup_path):
        return jsonify({'code': 400, 'msg': '备份文件不存在'})
    _log('下载备份', f'下载备份: {filename}')
    return send_file(backup_path, as_attachment=True, download_name=filename)

@app.route('/api/log', methods=['GET'])
@admin_required
def get_logs():
    page, per_page = safe_get_page_params()
    action = request.args.get('action', '')
    where = "WHERE 1=1"
    params = []
    if action:
        where += " AND action LIKE ?"
        params.append(f'%{action}%')
    total = query_db(f"SELECT COUNT(*) as cnt FROM op_log {where}", params, one=True)['cnt']
    rows = query_db(
        f"SELECT * FROM op_log {where} ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [per_page, (page - 1) * per_page]
    )
    return jsonify({'code': 200, 'data': {
        'list': [dict(r) for r in rows], 'total': total, 'page': page, 'per_page': per_page
    }})

@app.route('/api/field_meta', methods=['GET'])
@login_required
def get_field_metas():
    page, per_page = safe_get_page_params()
    offset = (page - 1) * per_page
    
    rows = query_db("SELECT * FROM staff_field_meta ORDER BY sort_num, id LIMIT ? OFFSET ?", [per_page, offset])
    total = query_db("SELECT COUNT(*) as cnt FROM staff_field_meta", [], one=True)['cnt']
    
    result = []
    for r in rows:
        item = dict(r)
        item['link_options'] = {}
        if item.get('link_field'):
            item['link_options'] = get_field_link_options(item.get('field_code', ''))
        result.append(item)
    
    return jsonify({'code': 200, 'data': {
        'list': result,
        'total': total,
        'page': page,
        'per_page': per_page
    }})

@app.route('/api/field_meta/all', methods=['GET'])
@login_required
def get_all_field_metas():
    rows = query_db("SELECT * FROM staff_field_meta ORDER BY sort_num, id")
    result = []
    for r in rows:
        item = dict(r)
        item['link_options'] = {}
        if item.get('link_field'):
            item['link_options'] = get_field_link_options(item.get('field_code', ''))
        result.append(item)
    return jsonify({'code': 200, 'data': result})

@app.route('/api/field_meta', methods=['POST'])
@admin_required
def add_field_meta():
    data = request.get_json()
    field_code = data.get('field_code', '').strip()
    field_name = data.get('field_name', '').strip()
    field_type = data.get('field_type', 'text')
    default_val = data.get('default_val', '')
    options = data.get('options', '')
    link_field = data.get('link_field', '')
    show_in_list = data.get('show_in_list', 0)
    sort_num = data.get('sort_num', 0)

    if not field_code or not field_name:
        return jsonify({'code': 400, 'msg': '字段编码和名称不能为空'})

    reserved = ['id', 'work_years', 'taogai_years']
    if field_code in reserved:
        return jsonify({'code': 400, 'msg': f'字段编码 {field_code} 为系统保留'})

    existing = query_db("SELECT id FROM staff_field_meta WHERE field_code = ?", [field_code], one=True)
    if existing:
        return jsonify({'code': 400, 'msg': f'字段编码 {field_code} 已存在'})

    last_id = execute_db(
        "INSERT INTO staff_field_meta (field_code, field_name, field_type, default_val, options, link_field, show_in_list, sort_num) VALUES (?,?,?,?,?,?,?,?)",
        [field_code, field_name, field_type, default_val, options, link_field, show_in_list, sort_num]
    )
    
    # 如果有联动配置，直接写入 field_linkage 表
    if link_field and isinstance(data.get('link_options'), dict) and len(data['link_options']) > 0:
        for src_opt, tgt_opts in data['link_options'].items():
            tgt_list = tgt_opts.split(',') if isinstance(tgt_opts, str) else []
            for tgt_val in tgt_list:
                tgt_val = tgt_val.strip()
                if not tgt_val: continue
                execute_db(
                    "INSERT INTO field_linkage (source_field_code, source_option_value, target_field_code, target_option_value) VALUES (?,?,?,?)",
                    [link_field, src_opt.strip(), field_code, tgt_val]
                )
    
    _log('新增字段', f'新增字段: {field_code}({field_name})')
    return jsonify({'code': 200, 'msg': '添加成功', 'data': {'id': last_id}})

@app.route('/api/field_meta/<int:fid>', methods=['PUT'])
@admin_required
def update_field_meta(fid):
    data = request.get_json()

    execute_db(
        "UPDATE staff_field_meta SET field_name=?, field_type=?, default_val=?, options=?, is_active=?, link_field=?, show_in_list=?, sort_num=? WHERE id=?",
        [data.get('field_name', ''), data.get('field_type', 'text'), data.get('default_val', ''),
         data.get('options', ''), data.get('is_active', 1), data.get('link_field', ''),
         data.get('show_in_list', 0), data.get('sort_num', 0), fid]
    )
    _log('修改字段', f'修改字段ID: {fid}')
    return jsonify({'code': 200, 'msg': '更新成功'})

@app.route('/api/field_meta/<int:fid>', methods=['DELETE'])
@admin_required
def delete_field_meta(fid):
    meta = query_db("SELECT field_code FROM staff_field_meta WHERE id=?", [fid], one=True)
    if meta:
        field_code = meta['field_code']
        
        # 删除字段的自定义数据
        execute_db("DELETE FROM staff_field_data WHERE field_code=?", [field_code])
        
        # 删除字段的联动配置（作为目标字段）
        linkages_as_target = query_db("SELECT COUNT(*) as cnt FROM field_linkage WHERE target_field_code=?", [field_code], one=True)
        deleted_target = linkages_as_target['cnt'] if linkages_as_target else 0
        execute_db("DELETE FROM field_linkage WHERE target_field_code=?", [field_code])
        
        # 删除字段的联动配置（作为源字段）
        linkages_as_source = query_db("SELECT COUNT(*) as cnt FROM field_linkage WHERE source_field_code=?", [field_code], one=True)
        deleted_source = linkages_as_source['cnt'] if linkages_as_source else 0
        execute_db("DELETE FROM field_linkage WHERE source_field_code=?", [field_code])
        
        total_deleted = deleted_target + deleted_source
        print(f'删除字段 {field_code}: 联动配置 {total_deleted} 条 (目标:{deleted_target}, 源:{deleted_source})')
    
    execute_db("DELETE FROM staff_field_meta WHERE id=?", [fid])
    _log('删除字段', f'删除字段ID: {fid}' + (f', 联动配置{total_deleted}条' if meta else ''))
    return jsonify({'code': 200, 'msg': '删除成功'})

@app.route('/api/field_meta/export', methods=['GET'])
@admin_required
def export_field_metas():
    rows = query_db("SELECT * FROM staff_field_meta ORDER BY sort_num, id")
    result = []
    for r in rows:
        item = dict(r)
        item['link_options'] = {}
        if item.get('link_field'):
            item['link_options'] = get_field_link_options(item.get('field_code', ''))
        result.append(item)
    
    linkages = query_db("SELECT * FROM field_linkage ORDER BY id")
    linkage_list = [dict(l) for l in linkages]
    
    return jsonify({'code': 200, 'data': {'fields': result, 'linkages': linkage_list}})

@app.route('/api/field_meta/import', methods=['POST'])
@admin_required
def import_field_metas():
    conn = get_db()
    try:
        data = request.get_json()
        if not data:
            return jsonify({'code': 400, 'msg': '请求数据为空'})
        
        fields = data.get('fields', [])
        linkages = data.get('linkages', [])
        overwrite = data.get('overwrite', False)
        
        print(f'=== 导入字段开始 ===')
        print(f'字段数量: {len(fields)}')
        for idx, f in enumerate(fields):
            print(f'  字段{idx}: {f.get("field_code")}, link_field={f.get("link_field")}')
        
        if not fields:
            return jsonify({'code': 400, 'msg': '没有可导入的字段数据'})
        
        # 开始事务
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION")
        
        added = 0
        skipped = 0
        updated = 0
        link_added = 0
        errors = []
        
        for f in fields:
            field_code = f.get('field_code', '').strip()
            field_name = f.get('field_name', '').strip()
            
            # 输入验证
            if len(field_code) > 50:
                errors.append(f'字段编码过长: {field_code} (最多50字符)')
                continue
            if len(field_name) > 100:
                errors.append(f'字段名称过长: {field_name} (最多100字符)')
                continue
            
            if not field_code or not field_name:
                errors.append(f'字段编码或名称为空: {f}')
                continue
            
            try:
                cursor.execute("SELECT id FROM staff_field_meta WHERE field_code=?", [field_code])
                existing = cursor.fetchone()
                
                if existing:
                    if overwrite:
                        cursor.execute(
                            "UPDATE staff_field_meta SET field_name=?, field_type=?, default_val=?, options=?, is_active=?, link_field=?, show_in_list=?, sort_num=? WHERE id=?",
                            [field_name, f.get('field_type', 'text'), f.get('default_val', ''),
                             f.get('options', ''), f.get('is_active', 1), f.get('link_field', ''),
                             f.get('show_in_list', 0), f.get('sort_num', 0), existing['id']]
                        )
                        print(f'  ✓ 更新字段: {field_code}')
                        
                        link_field = f.get('link_field', '').strip()
                        if link_field and isinstance(f.get('link_options'), dict) and len(f['link_options']) > 0:
                            cursor.execute("DELETE FROM field_linkage WHERE target_field_code=?", [field_code])
                            for src_opt, tgt_opts in f['link_options'].items():
                                tgt_list = tgt_opts.split(',') if isinstance(tgt_opts, str) else []
                                for tgt_val in tgt_list:
                                    tgt_val = tgt_val.strip()
                                    if not tgt_val: continue
                                    cursor.execute(
                                        "INSERT INTO field_linkage (source_field_code, source_option_value, target_field_code, target_option_value) VALUES (?,?,?,?)",
                                        [link_field, src_opt.strip(), field_code, tgt_val]
                                    )
                                    link_added += 1
                        
                        updated += 1
                    else:
                        skipped += 1
                        print(f'  - 跳过已存在字段: {field_code}')
                else:
                    cursor.execute(
                        "INSERT INTO staff_field_meta (field_code, field_name, field_type, default_val, options, link_field, show_in_list, sort_num) VALUES (?,?,?,?,?,?,?,?)",
                        [field_code, field_name, f.get('field_type', 'text'), f.get('default_val', ''),
                         f.get('options', ''), f.get('link_field', ''),
                         f.get('show_in_list', 0), f.get('sort_num', 0)]
                    )
                    print(f'  + 新增字段: {field_code}')
                    
                    link_field = f.get('link_field', '').strip()
                    if link_field and isinstance(f.get('link_options'), dict) and len(f['link_options']) > 0:
                        for src_opt, tgt_opts in f['link_options'].items():
                            tgt_list = tgt_opts.split(',') if isinstance(tgt_opts, str) else []
                            for tgt_val in tgt_list:
                                tgt_val = tgt_val.strip()
                                if not tgt_val: continue
                                cursor.execute(
                                    "INSERT INTO field_linkage (source_field_code, source_option_value, target_field_code, target_option_value) VALUES (?,?,?,?)",
                                    [link_field, src_opt.strip(), field_code, tgt_val]
                                )
                                link_added += 1
                    
                    added += 1
                    
            except Exception as e:
                error_msg = f'处理字段 {field_code} 时出错: {str(e)}'
                print(f'  ✗ {error_msg}')
                errors.append(error_msg)
        
        for l in linkages:
            source_field = l.get('source_field_code', '').strip()
            source_value = l.get('source_option_value', '').strip()
            target_field = l.get('target_field_code', '').strip()
            target_value = l.get('target_option_value', '').strip()
            if not source_field or not source_value or not target_field or not target_value:
                continue
            
            cursor.execute(
                "SELECT id FROM field_linkage WHERE source_field_code=? AND source_option_value=? AND target_field_code=? AND target_option_value=?",
                [source_field, source_value, target_field, target_value]
            )
            existing_link = cursor.fetchone()
            if not existing_link:
                cursor.execute(
                    "INSERT INTO field_linkage (source_field_code, source_option_value, target_field_code, target_option_value) VALUES (?,?,?,?)",
                    [source_field, source_value, target_field, target_value]
                )
                link_added += 1
        
        # 提交事务
        conn.commit()
        
        result_msg = f'导入完成：新增{added}个，更新{updated}个，跳过{skipped}个，联动{link_added}条'
        print(f'\n=== 导入成功 ===')
        print(result_msg)
        if errors:
            print(f'警告 ({len(errors)}个):')
            for err in errors[:5]:
                print(f'  - {err}')
        
        _log('导入字段', result_msg)
        return jsonify({
            'code': 200,
            'msg': result_msg,
            'data': {
                'added': added,
                'updated': updated,
                'skipped': skipped,
                'link_added': link_added,
                'errors': errors[:10]
            }
        })
        
    except Exception as e:
        # 回滚事务
        try:
            conn.rollback()
            print('\n⚠️ 导入失败，事务已回滚')
        except Exception as rollback_err:
            print(f'\n❌ 回滚失败: {rollback_err}')
        
        import traceback
        error_detail = traceback.format_exc()
        print(f'\n❌ 导入失败: {str(e)}')
        print(error_detail)
        return jsonify({
            'code': 500,
            'msg': f'导入失败: {str(e)}',
            'error': error_detail
        }), 500
    finally:
        try:
            conn.close()
        except Exception:
            pass

@app.route('/api/field_link_options', methods=['GET'])
@login_required
def get_link_options():
    field_code = request.args.get('field', '')
    link_value = request.args.get('value', '')
    link_field = request.args.get('link_field', '')
    
    if not field_code:
        return jsonify({'code': 200, 'data': []})
    
    if link_value and link_field:
        rows = query_db(
            "SELECT DISTINCT target_option_value FROM field_linkage WHERE source_field_code=? AND source_option_value=? AND target_field_code=?",
            [link_field, link_value, field_code]
        )
        if rows:
            return jsonify({'code': 200, 'data': [r['target_option_value'] for r in rows]})
    
    meta = query_db("SELECT options FROM staff_field_meta WHERE field_code=? AND is_active=1", [field_code], one=True)
    if meta and meta['options']:
        return jsonify({'code': 200, 'data': meta['options'].split(',')})
    return jsonify({'code': 200, 'data': []})

@app.route('/api/field/<int:field_id>/linkage', methods=['GET'])
@admin_required
def get_field_linkage(field_id):
    field_meta = query_db("SELECT * FROM staff_field_meta WHERE id=?", [field_id], one=True)
    if not field_meta:
        return jsonify({'code': 404, 'msg': '字段不存在'})
    
    source_code = field_meta['link_field']
    target_code = field_meta['field_code']
    
    if not source_code:
        return jsonify({'code': 200, 'data': []})
    
    source_meta = query_db("SELECT options FROM staff_field_meta WHERE field_code=?", [source_code], one=True)
    source_opts = source_meta['options'].split(',') if source_meta and source_meta['options'] else []
    
    linkages = query_db(
        "SELECT source_option_value, GROUP_CONCAT(target_option_value, ',') as targets FROM field_linkage WHERE target_field_code=? AND source_field_code=? GROUP BY source_option_value",
        [target_code, source_code]
    )
    
    linkage_map = {}
    for l in linkages:
        linkage_map[l['source_option_value']] = l['targets'] or ''
    
    result = []
    for opt in source_opts:
        opt = opt.strip()
        result.append({
            'source_option': opt,
            'target_options': linkage_map.get(opt, '')
        })
    
    return jsonify({'code': 200, 'data': result})

@app.route('/api/field/<int:field_id>/linkage', methods=['PUT'])
@admin_required
def update_field_linkage(field_id):
    data = request.get_json()
    linkage_list = data.get('linkages', [])
    
    field_meta = query_db("SELECT * FROM staff_field_meta WHERE id=?", [field_id], one=True)
    if not field_meta:
        return jsonify({'code': 404, 'msg': '字段不存在'})
    
    target_code = field_meta['field_code']
    source_code = field_meta['link_field']
    
    if not source_code:
        execute_db("DELETE FROM field_linkage WHERE target_field_code=?", [target_code])
        return jsonify({'code': 200, 'msg': '更新成功'})
    
    execute_db("DELETE FROM field_linkage WHERE target_field_code=? AND source_field_code=?", [target_code, source_code])
    
    for link in linkage_list:
        src_opt = link.get('source_option', '').strip()
        tgt_opts = link.get('target_options', '').strip()
        if src_opt and tgt_opts:
            for tgt_opt in tgt_opts.split(','):
                tgt_opt = tgt_opt.strip()
                if tgt_opt:
                    execute_db(
                        "INSERT INTO field_linkage (source_field_code, source_option_value, target_field_code, target_option_value) VALUES (?, ?, ?, ?)",
                        [source_code, src_opt, target_code, tgt_opt]
                    )
    
    _log('更新字段联动', f'字段 {field_meta["field_name"]} 联动规则')
    return jsonify({'code': 200, 'msg': '更新成功'})

@app.route('/api/field_display', methods=['PUT'])
@admin_required
def update_field_display():
    data = request.get_json()
    items = data.get('items', [])
    for item in items:
        execute_db(
            "UPDATE staff_field_meta SET show_in_list=?, sort_num=? WHERE id=?",
            [item.get('show_in_list', 0), item.get('sort_num', 0), item['id']]
        )
    _log('修改显示配置', '修改列表显示字段配置')
    return jsonify({'code': 200, 'msg': '更新成功'})

def _calc_work_years(work_start_date, calc_year=None):
    if not work_start_date:
        return 0
    try:
        start_year = int(work_start_date[:4])
        target_year = calc_year if calc_year else datetime.now().year
        return target_year - start_year + 1
    except (ValueError, IndexError):
        return 0

def _calc_taogai_years(staff_id, work_start_date, calc_year=None):
    work_years = _calc_work_years(work_start_date, calc_year)
    if work_years <= 0:
        return 0
    target_year = calc_year if calc_year else datetime.now().year
    bad_years = query_db(
        "SELECT COUNT(*) as cnt FROM staff_assessment WHERE staff_id=? AND year<? AND grade='称职以下'",
        [staff_id, target_year], one=True
    )['cnt']
    return work_years - bad_years

def _build_staff_context(staff, calc_year=None):
    context = {}
    base_fields = ['name', 'gender', 'dept', 'unit', 'birth_date', 'work_start_date', 'status']
    for key in base_fields:
        context[key] = staff.get(key, '')

    context['work_years'] = _calc_work_years(staff.get('work_start_date', ''), calc_year)
    context['taogai_years'] = _calc_taogai_years(staff.get('id', 0), staff.get('work_start_date', ''), calc_year)

    field_metas = query_db("SELECT field_code, field_type FROM staff_field_meta WHERE is_active=1")
    custom_data = query_db(
        "SELECT field_code, field_val FROM staff_field_data WHERE staff_id=?",
        [staff['id']]
    )
    custom_map = {fd['field_code']: fd['field_val'] for fd in custom_data}

    for fm in field_metas:
        code = fm['field_code']
        if code in base_fields:
            continue
        val = custom_map.get(code, '0')
        if fm['field_type'] == 'number':
            try:
                context[code] = float(val) if val else 0
            except (ValueError, TypeError):
                context[code] = 0
        else:
            context[code] = val

    return context

@app.route('/api/staff', methods=['GET'])
@login_required
def get_staff_list():
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    dept = request.args.get('dept', '')
    unit = request.args.get('unit', '')
    name = request.args.get('name', '')
    status = request.args.get('status', '在职')

    where = "WHERE 1=1"
    params = []
    if status:
        where += " AND status = ?"
        params.append(status)
    if dept:
        where += " AND dept LIKE ?"
        params.append(f'%{dept}%')
    if unit:
        where += " AND unit LIKE ?"
        params.append(f'%{unit}%')
    if name:
        where += " AND name LIKE ?"
        params.append(f'%{name}%')

    total = query_db(f"SELECT COUNT(*) as cnt FROM staff_base {where}", params, one=True)['cnt']
    rows = query_db(
        f"SELECT * FROM staff_base {where} ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [per_page, (page - 1) * per_page]
    )

    staff_list = [dict(r) for r in rows]
    field_metas = query_db("SELECT * FROM staff_field_meta WHERE is_active=1 ORDER BY sort_num, id")
    
    fields_list = []
    for f in field_metas:
        item = dict(f)
        item['link_options'] = {}
        if item.get('link_field'):
            item['link_options'] = get_field_link_options(item.get('field_code', ''))
        fields_list.append(item)

    for staff in staff_list:
        custom_data = query_db(
            "SELECT field_code, field_val FROM staff_field_data WHERE staff_id=?",
            [staff['id']]
        )
        for fd in custom_data:
            staff[fd['field_code']] = fd['field_val']
        staff['work_years'] = _calc_work_years(staff.get('work_start_date', ''))
        staff['taogai_years'] = _calc_taogai_years(staff['id'], staff.get('work_start_date', ''))
        
        from db import check_retirement_status
        retirement_status, retirement_msg = check_retirement_status(staff.get('retirement_date', ''))
        staff['retirement_status'] = retirement_status
        staff['retirement_msg'] = retirement_msg

    return jsonify({
        'code': 200,
        'data': {
            'list': staff_list,
            'total': total,
            'page': page,
            'per_page': per_page,
            'fields': fields_list
        }
    })

@app.route('/api/staff/<int:sid>', methods=['GET'])
@login_required
def get_staff_detail(sid):
    staff = query_db("SELECT * FROM staff_base WHERE id=?", [sid], one=True)
    if not staff:
        return jsonify({'code': 404, 'msg': '人员不存在'})
    staff = dict(staff)
    custom_data = query_db("SELECT field_code, field_val FROM staff_field_data WHERE staff_id=?", [sid])
    for fd in custom_data:
        staff[fd['field_code']] = fd['field_val']
    staff['work_years'] = _calc_work_years(staff.get('work_start_date', ''))
    staff['taogai_years'] = _calc_taogai_years(sid, staff.get('work_start_date', ''))

    field_metas = query_db("SELECT * FROM staff_field_meta WHERE is_active=1 ORDER BY sort_num, id")
    fields_list = []
    for f in field_metas:
        item = dict(f)
        item['link_options'] = {}
        if item.get('link_field'):
            item['link_options'] = get_field_link_options(item.get('field_code', ''))
        fields_list.append(item)
    staff['_fields'] = fields_list

    assessments = query_db("SELECT * FROM staff_assessment WHERE staff_id=? ORDER BY year DESC", [sid])
    staff['_assessments'] = [dict(a) for a in assessments]

    return jsonify({'code': 200, 'data': staff})

@app.route('/api/link_map', methods=['GET'])
@login_required
def get_link_map():
    # 从 field_linkage 表读取所有联动配置，构建映射
    linkages = query_db("SELECT source_field_code, source_option_value, target_field_code, target_option_value FROM field_linkage ORDER BY id")
    result = {}
    for l in linkages:
        key = f"{l['source_field_code']}->{l['target_field_code']}"
        if key not in result:
            result[key] = {}
        src_opt = l['source_option_value']
        tgt_val = l['target_option_value']
        if src_opt not in result[key]:
            result[key][src_opt] = []
        result[key][src_opt].append(tgt_val)
    
    return jsonify({'code': 200, 'data': result})

@app.route('/api/staff', methods=['POST'])
@login_required
def add_staff():
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'code': 400, 'msg': '姓名不能为空'})

    birth_date = data.get('birth_date', '').strip()
    gender = data.get('gender', '').strip()
    
    from db import clean_date_format
    birth_date = clean_date_format(birth_date) if birth_date else ''
    work_start_date = clean_date_format(data.get('work_start_date', '').strip()) if data.get('work_start_date', '').strip() else ''
    
    retirement_date = ''
    if birth_date and gender:
        from db import calculate_retirement_date
        retirement_date = calculate_retirement_date(birth_date, gender) or ''

    last_id = execute_db(
        "INSERT INTO staff_base (name, gender, dept, unit, birth_date, work_start_date, status, retirement_date) VALUES (?,?,?,?,?,?,?,?)",
        [name, gender, data.get('dept', ''), data.get('unit', ''),
         birth_date, work_start_date, data.get('status', '在职'), retirement_date]
    )

    base_codes = {'name', 'gender', 'dept', 'unit', 'birth_date', 'work_start_date', 'status'}
    field_metas = query_db("SELECT field_code FROM staff_field_meta WHERE is_active=1")
    custom_values = []
    for fm in field_metas:
        code = fm['field_code']
        if code in base_codes:
            continue
        val = data.get(code, '')
        if val != '':
            custom_values.append((last_id, code, str(val)))
    if custom_values:
        execute_db_many(
            "INSERT INTO staff_field_data (staff_id, field_code, field_val) VALUES (?,?,?)",
            custom_values
        )
    _log('新增人员', f'新增人员: {name}')
    return jsonify({'code': 200, 'msg': '添加成功', 'data': {'id': last_id}})

@app.route('/api/staff/<int:sid>', methods=['PUT'])
@login_required
def update_staff(sid):
    data = request.get_json()
    
    staff = query_db("SELECT * FROM staff_base WHERE id=?", [sid], one=True)
    if not staff:
        return jsonify({'code': 404, 'msg': '人员不存在'})
    staff = dict(staff)
    
    field_name_map = {
        'name': '姓名', 'gender': '性别', 'dept': '部门', 'unit': '单位',
        'birth_date': '出生年月', 'work_start_date': '参加工作时间', 'status': '状态'
    }
    
    operator = session.get('username', '')
    change_logs = []
    
    base_fields = ['name', 'gender', 'dept', 'unit', 'birth_date', 'work_start_date', 'status']
    need_recalc_retirement = False
    
    from db import clean_date_format
    
    for code in base_fields:
        old_val = str(staff.get(code, '') or '')
        new_val = str(data.get(code, '') or '')
        
        if code in ['birth_date', 'work_start_date'] and new_val:
            new_val = clean_date_format(new_val)
        
        if old_val != new_val and new_val != '':
            # 普通编辑不记录变更日志
            execute_db("UPDATE staff_base SET " + code + "=? WHERE id=?", [new_val, sid])
            if code in ['gender', 'birth_date']:
                need_recalc_retirement = True
    
    if need_recalc_retirement:
        from db import calculate_retirement_date
        new_birth_date = data.get('birth_date', staff.get('birth_date', '') or '').strip()
        new_gender = data.get('gender', staff.get('gender', '') or '').strip()
        
        new_birth_date = clean_date_format(new_birth_date) if new_birth_date else ''
        
        if new_birth_date and new_gender:
            new_retirement = calculate_retirement_date(new_birth_date, new_gender) or ''
            execute_db("UPDATE staff_base SET retirement_date=? WHERE id=?", [new_retirement, sid])
    
    base_codes = {'name', 'gender', 'dept', 'unit', 'birth_date', 'work_start_date', 'status'}
    field_metas = query_db("SELECT field_code, field_name FROM staff_field_meta WHERE is_active=1")
    for fm in field_metas:
        code = fm['field_code']
        if code in base_codes:
            continue
        val = str(data.get(code, ''))
        existing = query_db(
            "SELECT id, field_val FROM staff_field_data WHERE staff_id=? AND field_code=?",
            [sid, code], one=True
        )
        if existing:
            if str(existing['field_val'] or '') != val:
                # 普通编辑不记录变更日志
                execute_db("UPDATE staff_field_data SET field_val=? WHERE staff_id=? AND field_code=?", [val, sid, code])
        else:
            if val != '':
                execute_db("INSERT INTO staff_field_data (staff_id, field_code, field_val) VALUES (?,?,?)", [sid, code, val])
    
    _log('修改人员', f'修改人员: {staff["name"]}')
    return jsonify({'code': 200, 'msg': '更新成功'})

@app.route('/api/staff/<int:sid>', methods=['DELETE'])
@login_required
def delete_staff(sid):
    execute_db("DELETE FROM staff_field_data WHERE staff_id=?", [sid])
    execute_db("DELETE FROM staff_assessment WHERE staff_id=?", [sid])
    execute_db("DELETE FROM staff_change_log WHERE staff_id=?", [sid])
    execute_db("DELETE FROM staff_base WHERE id=?", [sid])
    _log('删除人员', f'删除人员ID: {sid}')
    return jsonify({'code': 200, 'msg': '删除成功'})

@app.route('/api/staff/batch_delete', methods=['POST'])
@login_required
def batch_delete_staff():
    data = request.get_json()
    ids = data.get('ids', [])
    
    if not ids or not isinstance(ids, list):
        return jsonify({'code': 400, 'msg': '请选择要删除的人员'})
    
    if len(ids) > 100:
        return jsonify({'code': 400, 'msg': '单次批量删除不能超过100人'})
    
    deleted_count = 0
    for sid in ids:
        try:
            execute_db("DELETE FROM staff_field_data WHERE staff_id=?", [sid])
            execute_db("DELETE FROM staff_assessment WHERE staff_id=?", [sid])
            execute_db("DELETE FROM staff_change_log WHERE staff_id=?", [sid])
            execute_db("DELETE FROM staff_base WHERE id=?", [sid])
            deleted_count += 1
        except Exception as e:
            continue
    
    _log('批量删除人员', f'批量删除{deleted_count}个人员')
    return jsonify({
        'code': 200, 
        'msg': f'成功删除{deleted_count}个人员',
        'data': {'deleted_count': deleted_count}
    })

@app.route('/api/staff/<int:sid>/lock', methods=['POST'])
@login_required
def lock_staff(sid):
    staff = query_db("SELECT * FROM staff_base WHERE id=?", [sid], one=True)
    if not staff:
        return jsonify({'code': 404, 'msg': '人员不存在'})
    execute_db("UPDATE staff_base SET is_locked=1 WHERE id=?", [sid])
    _log('锁定人员', f'锁定人员ID: {sid}, 姓名: {staff["name"]}')
    return jsonify({'code': 200, 'msg': '锁定成功'})

@app.route('/api/staff/<int:sid>/unlock', methods=['POST'])
@login_required
def unlock_staff(sid):
    staff = query_db("SELECT * FROM staff_base WHERE id=?", [sid], one=True)
    if not staff:
        return jsonify({'code': 404, 'msg': '人员不存在'})
    execute_db("UPDATE staff_base SET is_locked=0 WHERE id=?", [sid])
    _log('解锁人员', f'解锁人员ID: {sid}, 姓名: {staff["name"]}')
    return jsonify({'code': 200, 'msg': '解锁成功'})

@app.route('/api/staff/<int:sid>/detail', methods=['GET'])
@login_required
def get_staff_full_detail(sid):
    staff = query_db("SELECT * FROM staff_base WHERE id=?", [sid], one=True)
    if not staff:
        return jsonify({'code': 404, 'msg': '人员不存在'})
    staff = dict(staff)
    
    # 获取自定义字段
    custom_data = query_db("SELECT field_code, field_val FROM staff_field_data WHERE staff_id=?", [sid])
    for fd in custom_data:
        staff[fd['field_code']] = fd['field_val']
    staff['work_years'] = _calc_work_years(staff.get('work_start_date', ''))
    staff['taogai_years'] = _calc_taogai_years(sid, staff.get('work_start_date', ''))
    
    # 获取字段元数据
    field_metas = query_db("SELECT * FROM staff_field_meta WHERE is_active=1 ORDER BY sort_num, id")
    staff['_fields'] = [dict(f) for f in field_metas]
    
    # 获取考核记录
    assessments = query_db("SELECT * FROM staff_assessment WHERE staff_id=? ORDER BY year DESC", [sid])
    staff['_assessments'] = [dict(a) for a in assessments]
    
    # 获取变更记录（只显示变更页面的记录）
    changes = query_db("SELECT * FROM staff_change_log WHERE staff_id=? AND change_source='change_page' ORDER BY id DESC", [sid])
    staff['_changes'] = [dict(c) for c in changes]
    
    # 获取工资记录
    salary_rows = query_db("SELECT * FROM salary_month_record WHERE staff_id=? ORDER BY year DESC, month DESC", [sid])
    staff['_salary_records'] = []
    for sr in salary_rows:
        sr_dict = dict(sr)
        try:
            sr_dict['item_values'] = json.loads(sr_dict['item_values'])
        except:
            sr_dict['item_values'] = {}
        staff['_salary_records'].append(sr_dict)
    
    return jsonify({'code': 200, 'data': staff})

@app.route('/api/staff/<int:sid>/change', methods=['POST'])
@login_required
def staff_change(sid):
    try:
        staff = query_db("SELECT * FROM staff_base WHERE id=?", [sid], one=True)
        if not staff:
            return jsonify({'code': 404, 'msg': '人员不存在'})
        
        staff = dict(staff)
        
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'code': 400, 'msg': '请求数据格式错误'})
        
        field_code = data.get('field_code', '')
        new_value = data.get('new_value', '')
        remark = data.get('remark', '')
        change_month = data.get('change_month', '')
        
        if not field_code:
            return jsonify({'code': 400, 'msg': '请选择变更项目'})
        
        field_meta = query_db("SELECT field_name FROM staff_field_meta WHERE field_code=?", [field_code], one=True)
        field_name = field_meta['field_name'] if field_meta else field_code
        
        base_fields = ['name', 'gender', 'dept', 'unit', 'birth_date', 'work_start_date', 'status']
        change_source = 'change_page'
        operator = session.get('username', '')
        
        if field_code in base_fields:
            old_value = str(staff.get(field_code, '') or '')
            if old_value != new_value and new_value != '':
                execute_db("UPDATE staff_base SET " + field_code + "=? WHERE id=?", [new_value, sid])
                execute_db(
                    "INSERT INTO staff_change_log (staff_id, staff_name, field_name, old_value, new_value, operator, change_source, change_month) VALUES (?,?,?,?,?,?,?,?)",
                    [sid, staff['name'], field_name, old_value, new_value, operator, change_source, change_month]
                )
                if remark:
                    _log('人员变更', f'人员: {staff["name"]}, 项目: {field_name}, 备注: {remark}')
        else:
            existing = query_db(
                "SELECT id, field_val FROM staff_field_data WHERE staff_id=? AND field_code=?",
                [sid, field_code], one=True
            )
            old_value = str(existing['field_val'] or '') if existing else ''
            if existing:
                if old_value != new_value:
                    execute_db("UPDATE staff_field_data SET field_val=? WHERE staff_id=? AND field_code=?", [new_value, sid, field_code])
                    execute_db(
                        "INSERT INTO staff_change_log (staff_id, staff_name, field_name, old_value, new_value, operator, change_source, change_month) VALUES (?,?,?,?,?,?,?,?)",
                        [sid, staff['name'], field_name, old_value, new_value, operator, change_source, change_month]
                    )
            else:
                if new_value:
                    execute_db("INSERT INTO staff_field_data (staff_id, field_code, field_val) VALUES (?,?,?)", [sid, field_code, new_value])
                    execute_db(
                        "INSERT INTO staff_change_log (staff_id, staff_name, field_name, old_value, new_value, operator, change_source, change_month) VALUES (?,?,?,?,?,?,?,?)",
                        [sid, staff['name'], field_name, old_value, new_value, operator, change_source, change_month]
                    )
        
        _log('人员变更', f'人员: {staff["name"]}, 项目: {field_name}')
        return jsonify({'code': 200, 'msg': '变更成功'})
    except Exception as e:
        print(f'变更异常: {type(e).__name__}: {str(e)}')
        import traceback
        traceback.print_exc()
        return jsonify({'code': 500, 'msg': f'变更失败: {str(e)}'})

@app.route('/api/staff/<int:sid>/changes', methods=['GET'])
@login_required
def get_staff_changes(sid):
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    
    total = query_db(
        "SELECT COUNT(*) as cnt FROM staff_change_log WHERE staff_id=?",
        [sid], one=True
    )['cnt']
    
    rows = query_db(
        "SELECT * FROM staff_change_log WHERE staff_id=? ORDER BY id DESC LIMIT ? OFFSET ?",
        [sid, per_page, (page - 1) * per_page]
    )
    
    return jsonify({
        'code': 200,
        'data': {
            'list': [dict(r) for r in rows],
            'total': total,
            'page': page,
            'per_page': per_page
        }
    })

@app.route('/api/assessment/<int:sid>', methods=['GET'])
@login_required
def get_assessments(sid):
    rows = query_db("SELECT * FROM staff_assessment WHERE staff_id=? ORDER BY year DESC", [sid])
    return jsonify({'code': 200, 'data': [dict(r) for r in rows]})

@app.route('/api/assessment', methods=['POST'])
@login_required
def save_assessment():
    data = request.get_json()
    staff_id = data.get('staff_id')
    year = data.get('year')
    grade = data.get('grade', '')
    remark = data.get('remark', '')

    if not staff_id or not year or not grade:
        return jsonify({'code': 400, 'msg': '参数不完整'})

    existing = query_db(
        "SELECT id FROM staff_assessment WHERE staff_id=? AND year=?",
        [staff_id, year], one=True
    )
    if existing:
        execute_db("UPDATE staff_assessment SET grade=?, remark=? WHERE id=?", [grade, remark, existing['id']])
    else:
        execute_db("INSERT INTO staff_assessment (staff_id, year, grade, remark) VALUES (?,?,?,?)", [staff_id, year, grade, remark])
    _log('设置考核', f'人员ID:{staff_id} {year}年考核: {grade}')
    return jsonify({'code': 200, 'msg': '保存成功'})

@app.route('/api/assessment/<int:aid>', methods=['DELETE'])
@login_required
def delete_assessment(aid):
    execute_db("DELETE FROM staff_assessment WHERE id=?", [aid])
    return jsonify({'code': 200, 'msg': '删除成功'})

@app.route('/api/salary_book', methods=['GET'])
@login_required
def get_salary_books():
    rows = query_db("SELECT * FROM salary_book WHERE is_active=1 ORDER BY id DESC")
    return jsonify({'code': 200, 'data': [dict(r) for r in rows]})

@app.route('/api/salary_book', methods=['POST'])
@admin_required
def add_salary_book():
    data = request.get_json()
    book_name = data.get('book_name', '').strip()
    if not book_name:
        return jsonify({'code': 400, 'msg': '帐套名称不能为空'})
    last_id = execute_db("INSERT INTO salary_book (book_name, remark) VALUES (?,?)", [book_name, data.get('remark', '')])
    _log('新增帐套', f'新增帐套: {book_name}')
    return jsonify({'code': 200, 'msg': '添加成功', 'data': {'id': last_id}})

@app.route('/api/salary_book/<int:bid>', methods=['PUT'])
@admin_required
def update_salary_book(bid):
    data = request.get_json()
    execute_db("UPDATE salary_book SET book_name=?, remark=? WHERE id=?", [data.get('book_name', ''), data.get('remark', ''), bid])
    return jsonify({'code': 200, 'msg': '更新成功'})

@app.route('/api/salary_book/<int:bid>', methods=['DELETE'])
@admin_required
def delete_salary_book(bid):
    execute_db("UPDATE salary_book SET is_active=0 WHERE id=?", [bid])
    _log('删除帐套', f'删除帐套ID: {bid}')
    return jsonify({'code': 200, 'msg': '删除成功'})

@app.route('/api/salary_book/export', methods=['GET'])
@admin_required
def export_salary_books():
    import csv
    import io
    
    books = query_db("SELECT * FROM salary_book WHERE is_active=1 ORDER BY id")
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['记录类型', '帐套名称', '备注', '字段编码', '字段名称', '排序', '是否计算', '公式', 
                     '工资项目名称', '项目类型', '筛选条件', '计算公式', '是否启用'])
    
    book_name_map = {}
    for b in books:
        book_dict = dict(b)
        book_name_map[b['id']] = b['book_name']
        remark = book_dict.get('remark', '') if 'remark' in book_dict else ''
        writer.writerow(['book', b['book_name'], remark, '', '', '', '', '',
                         '', '', '', '', ''])
        
        items = query_db("SELECT * FROM salary_book_item WHERE book_id=? ORDER BY sort_num, id", [b['id']])
        for item in items:
            item_dict = dict(item)
            writer.writerow(['item', b['book_name'], '', item_dict.get('field_code', ''), item_dict.get('field_name', ''),
                             item_dict.get('sort_num', 0), item_dict.get('is_calc', 0), item_dict.get('formula', ''),
                             '', '', '', '', ''])
        
        salary_items = query_db("SELECT * FROM salary_item WHERE book_id=? AND is_active=1 ORDER BY sort_num, id", [b['id']])
        for si in salary_items:
            si_dict = dict(si)
            filter_cond = ''
            try:
                fc = json.loads(si_dict['filter_condition']) if si_dict.get('filter_condition') else []
                filter_cond = json.dumps(fc, ensure_ascii=False) if fc else ''
            except:
                filter_cond = si_dict.get('filter_condition', '') or ''
            writer.writerow(['salary_item', b['book_name'], '', '', '', '', '', '',
                             si_dict.get('item_name', ''), si_dict.get('item_type', 'income'), filter_cond,
                             si_dict.get('calc_formula', ''), si_dict.get('is_active', 1)])
    
    _log('导出帐套', f'导出{len(books)}个帐套')
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'salary_books_{datetime.now().strftime("%Y%m%d")}.csv'
    )

@app.route('/api/salary_book/import', methods=['POST'])
@admin_required
def import_salary_books():
    import csv
    import io
    
    conn = get_db()
    try:
        if 'file' not in request.files:
            return jsonify({'code': 400, 'msg': '请上传CSV文件'})
        
        file = request.files['file']
        if not file.filename or not file.filename.endswith('.csv'):
            return jsonify({'code': 400, 'msg': '请上传CSV格式的文件'})
        
        overwrite = request.form.get('overwrite', 'false') == 'true'
        
        file_content = file.read().decode('utf-8-sig')
        
        reader = csv.reader(io.StringIO(file_content))
        rows = list(reader)
        
        if len(rows) < 2:
            return jsonify({'code': 400, 'msg': 'CSV文件内容为空或只有表头'})
        
        header = rows[0]
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION")
        
        added = 0
        updated = 0
        skipped = 0
        item_count = 0
        salary_item_count = 0
        errors = []
        book_name_to_id = {}
        
        for row in rows[1:]:
            if not row or len(row) < 2:
                continue
            
            record_type = (row[0] or '').strip()
            
            if record_type == 'book':
                book_name = (row[1] or '').strip()
                remark = (row[2] or '').strip() if len(row) > 2 else ''
                
                if not book_name:
                    continue
                
                try:
                    cursor.execute("SELECT id FROM salary_book WHERE book_name=? AND is_active=1", [book_name])
                    existing = cursor.fetchone()
                    
                    if existing:
                        if overwrite:
                            cursor.execute(
                                "UPDATE salary_book SET book_name=?, remark=? WHERE id=?",
                                [book_name, remark, existing['id']]
                            )
                            book_name_to_id[book_name] = existing['id']
                            updated += 1
                        else:
                            book_name_to_id[book_name] = existing['id']
                            skipped += 1
                    else:
                        new_id = cursor.execute(
                            "INSERT INTO salary_book (book_name, remark) VALUES (?,?)",
                            [book_name, remark]
                        ).lastrowid
                        book_name_to_id[book_name] = new_id
                        added += 1
                        
                except Exception as e:
                    errors.append(f'处理帐套 {book_name} 时出错: {str(e)}')
            
            elif record_type == 'item':
                book_name = (row[1] or '').strip()
                field_code = (row[3] or '').strip() if len(row) > 3 else ''
                field_name = (row[4] or '').strip() if len(row) > 4 else ''
                sort_num = int(row[5] or 0) if len(row) > 5 and row[5] else 0
                is_calc = int(row[6] or 0) if len(row) > 6 and row[6] else 0
                formula = (row[7] or '').strip() if len(row) > 7 else ''
                
                new_book_id = book_name_to_id.get(book_name)
                if not new_book_id or not field_code:
                    continue
                
                try:
                    cursor.execute(
                        "DELETE FROM salary_book_item WHERE book_id=? AND field_code=?",
                        [new_book_id, field_code]
                    )
                    cursor.execute(
                        "INSERT INTO salary_book_item (book_id, field_code, field_name, sort_num, is_calc, formula) VALUES (?,?,?,?,?,?)",
                        [new_book_id, field_code, field_name, sort_num, is_calc, formula]
                    )
                    item_count += 1
                except Exception as e:
                    errors.append(f'处理帐套项目 {field_code} 时出错: {str(e)}')
            
            elif record_type == 'salary_item':
                book_name = (row[1] or '').strip()
                item_name = (row[8] or '').strip() if len(row) > 8 else ''
                item_type = (row[9] or 'income').strip() if len(row) > 9 else 'income'
                filter_cond = (row[10] or '').strip() if len(row) > 10 else ''
                calc_formula = (row[11] or '').strip() if len(row) > 11 else ''
                is_active = int(row[12] or 1) if len(row) > 12 and row[12] else 1
                
                new_book_id = book_name_to_id.get(book_name)
                if not new_book_id or not item_name:
                    continue
                
                try:
                    cursor.execute(
                        "INSERT OR REPLACE INTO salary_item (book_id, item_name, item_type, filter_condition, calc_formula, is_active) VALUES (?,?,?,?,?,?)",
                        [new_book_id, item_name, item_type, filter_cond, calc_formula, is_active]
                    )
                    salary_item_count += 1
                except Exception as e:
                    errors.append(f'处理工资项目 {item_name} 时出错: {str(e)}')
        
        conn.commit()
        
        result_msg = f'导入完成：新增{added}个帐套，更新{updated}个，跳过{skipped}个，帐套项目{item_count}项，工资项目{salary_item_count}项'
        _log('导入帐套', result_msg)
        return jsonify({
            'code': 200,
            'msg': result_msg,
            'data': {
                'added': added,
                'updated': updated,
                'skipped': skipped,
                'item_count': item_count,
                'salary_item_count': salary_item_count,
                'errors': errors[:10]
            }
        })
        
    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
        import traceback
        print(f'导入帐套失败: {str(e)}\n{traceback.format_exc()}')
        return jsonify({'code': 500, 'msg': f'导入失败: {str(e)}'}), 500

@app.route('/api/salary_item/<int:book_id>', methods=['GET'])
@login_required
def get_salary_items(book_id):
    rows = query_db("SELECT * FROM salary_item WHERE book_id=? AND is_active=1 ORDER BY sort_num, id", [book_id])
    items = []
    for r in rows:
        item = dict(r)
        try:
            item['filter_condition'] = json.loads(item['filter_condition']) if item['filter_condition'] else []
        except:
            item['filter_condition'] = []
        items.append(item)
    return jsonify({'code': 200, 'data': items})

@app.route('/api/salary_item', methods=['POST'])
@admin_required
def add_salary_item():
    data = request.get_json()
    book_id = data.get('book_id')
    item_name = data.get('item_name', '').strip()
    if not item_name:
        return jsonify({'code': 400, 'msg': '项目名称不能为空'})
    filter_cond = data.get('filter_condition', [])
    if isinstance(filter_cond, list):
        filter_cond = json.dumps(filter_cond, ensure_ascii=False)
    last_id = execute_db(
        "INSERT INTO salary_item (book_id, item_name, item_type, filter_condition, calc_formula, sort_num) VALUES (?,?,?,?,?,?)",
        [book_id, item_name, data.get('item_type', 'income'), filter_cond, data.get('calc_formula', ''), data.get('sort_num', 0)]
    )
    _log('新增工资项目', f'帐套ID:{book_id} 项目: {item_name}')
    return jsonify({'code': 200, 'msg': '添加成功', 'data': {'id': last_id}})

@app.route('/api/salary_item/<int:item_id>', methods=['PUT'])
@admin_required
def update_salary_item(item_id):
    data = request.get_json()
    filter_cond = data.get('filter_condition', [])
    if isinstance(filter_cond, list):
        filter_cond = json.dumps(filter_cond, ensure_ascii=False)
    execute_db(
        "UPDATE salary_item SET item_name=?, item_type=?, filter_condition=?, calc_formula=?, sort_num=? WHERE id=?",
        [data.get('item_name', ''), data.get('item_type', 'income'), filter_cond, data.get('calc_formula', ''), data.get('sort_num', 0), item_id]
    )
    return jsonify({'code': 200, 'msg': '更新成功'})

@app.route('/api/salary_item/<int:item_id>', methods=['DELETE'])
@admin_required
def delete_salary_item(item_id):
    execute_db("UPDATE salary_item SET is_active=0 WHERE id=?", [item_id])
    return jsonify({'code': 200, 'msg': '删除成功'})

@app.route('/api/salary_item/test_formula', methods=['POST'])
@admin_required
def test_formula():
    data = request.get_json()
    formula = data.get('calc_formula', '')
    test_context = data.get('test_context', {})
    try:
        result = evaluate_formula(formula, test_context)
        return jsonify({'code': 200, 'data': {'result': result}})
    except Exception as e:
        return jsonify({'code': 400, 'msg': f'公式计算错误: {str(e)}'})

@app.route('/api/salary_calc', methods=['POST'])
@admin_required
def calc_salary():
    data = request.get_json()
    book_id = data.get('book_id')
    year = data.get('year')
    month = data.get('month')
    dept = data.get('dept', '')
    unit = data.get('unit', '')

    if not book_id or not year or not month:
        return jsonify({'code': 400, 'msg': '请选择帐套、年份、月份'})

    where = "WHERE status='在职'"
    params = []
    if dept:
        where += " AND dept LIKE ?"
        params.append(f'%{dept}%')
    if unit:
        where += " AND unit LIKE ?"
        params.append(f'%{unit}%')

    staff_rows = query_db(f"SELECT * FROM staff_base {where}", params)
    items = query_db("SELECT * FROM salary_item WHERE book_id=? AND is_active=1 ORDER BY sort_num, id", [book_id])

    if not items:
        return jsonify({'code': 400, 'msg': '该帐套下没有工资项目'})

    calc_record_id = execute_db(
        "INSERT INTO salary_calc_record (book_id, dept, unit, year, month) VALUES (?,?,?,?,?)",
        [book_id, dept, unit, year, month]
    )

    results = []
    total_income_all = 0
    total_deduct_all = 0
    total_real_all = 0

    for staff in staff_rows:
        staff = dict(staff)
        context = _build_staff_context(staff, calc_year=year)
        item_values = {}
        total_income = 0
        total_deduct = 0

        for item in items:
            item = dict(item)
            try:
                conditions = json.loads(item['filter_condition']) if item['filter_condition'] else []
            except:
                conditions = []
            if not match_filter_conditions(conditions, context):
                continue
            val = evaluate_formula(item['calc_formula'], context)
            item_values[item['item_name']] = val
            if item['item_type'] == 'income':
                total_income += val
            else:
                total_deduct += val
            context[item['item_name']] = val

        real_salary = round(total_income - total_deduct, 2)
        total_income_all += total_income
        total_deduct_all += total_deduct
        total_real_all += real_salary

        existing = query_db(
            "SELECT id FROM salary_month_record WHERE staff_id=? AND book_id=? AND year=? AND month=?",
            [staff['id'], book_id, year, month], one=True
        )
        if existing:
            execute_db(
                "UPDATE salary_month_record SET calc_record_id=?, item_values=?, total_income=?, total_deduct=?, real_salary=?, create_time=datetime('now','localtime') WHERE id=?",
                [calc_record_id, json.dumps(item_values, ensure_ascii=False), total_income, total_deduct, real_salary, existing['id']]
            )
        else:
            execute_db(
                "INSERT INTO salary_month_record (staff_id, book_id, calc_record_id, year, month, item_values, total_income, total_deduct, real_salary) VALUES (?,?,?,?,?,?,?,?,?)",
                [staff['id'], book_id, calc_record_id, year, month, json.dumps(item_values, ensure_ascii=False), total_income, total_deduct, real_salary]
            )

        results.append({
            'staff_id': staff['id'],
            'name': staff['name'],
            'dept': staff['dept'],
            'unit': staff['unit'],
            'item_values': item_values,
            'total_income': round(total_income, 2),
            'total_deduct': round(total_deduct, 2),
            'real_salary': real_salary
        })

    execute_db(
        "UPDATE salary_calc_record SET staff_count=?, total_income=?, total_deduct=?, total_real=? WHERE id=?",
        [len(results), round(total_income_all, 2), round(total_deduct_all, 2), round(total_real_all, 2), calc_record_id]
    )

    _log('薪资核算', f'帐套ID:{book_id} {year}年{month}月 共{len(results)}人')
    return jsonify({
        'code': 200,
        'msg': f'核算完成，共处理 {len(results)} 人',
        'data': {
            'calc_record_id': calc_record_id,
            'staff_count': len(results),
            'total_income': round(total_income_all, 2),
            'total_deduct': round(total_deduct_all, 2),
            'total_real': round(total_real_all, 2),
            'details': results
        }
    })

@app.route('/api/salary_calc_records', methods=['GET'])
@login_required
def get_calc_records():
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 15))
    total = query_db("SELECT COUNT(*) as cnt FROM salary_calc_record", one=True)['cnt']
    rows = query_db(
        """SELECT c.*, b.book_name FROM salary_calc_record c
           LEFT JOIN salary_book b ON c.book_id=b.id
           ORDER BY c.id DESC LIMIT ? OFFSET ?""",
        [per_page, (page - 1) * per_page]
    )
    return jsonify({'code': 200, 'data': {
        'list': [dict(r) for r in rows], 'total': total, 'page': page, 'per_page': per_page
    }})

@app.route('/api/salary_calc_record/<int:rid>', methods=['GET'])
@login_required
def get_calc_record_detail(rid):
    record = query_db(
        """SELECT c.*, b.book_name FROM salary_calc_record c
           LEFT JOIN salary_book b ON c.book_id=b.id WHERE c.id=?""",
        [rid], one=True
    )
    if not record:
        return jsonify({'code': 404, 'msg': '记录不存在'})

    rows = query_db(
        """SELECT r.*, s.name, s.dept, s.unit, s.gender
           FROM salary_month_record r
           LEFT JOIN staff_base s ON r.staff_id=s.id
           WHERE r.calc_record_id=? ORDER BY s.dept, s.unit, s.name""",
        [rid]
    )
    details = []
    for r in rows:
        rec = dict(r)
        try:
            rec['item_values'] = json.loads(rec['item_values']) if rec['item_values'] else {}
        except:
            rec['item_values'] = {}
        details.append(rec)

    result = dict(record)
    result['details'] = details
    return jsonify({'code': 200, 'data': result})

@app.route('/api/salary_calc_record/<int:rid>', methods=['DELETE'])
@admin_required
def delete_calc_record(rid):
    execute_db("DELETE FROM salary_month_record WHERE calc_record_id=?", [rid])
    execute_db("DELETE FROM salary_calc_record WHERE id=?", [rid])
    _log('删除核算记录', f'删除核算记录ID: {rid}')
    return jsonify({'code': 200, 'msg': '删除成功'})

@app.route('/api/salary_calc_record/batch_delete', methods=['POST'])
@admin_required
def batch_delete_calc_records():
    data = request.get_json()
    ids = data.get('ids', [])
    
    if not ids or not isinstance(ids, list):
        return jsonify({'code': 400, 'msg': '请选择要删除的核算记录'})
    
    if len(ids) > 50:
        return jsonify({'code': 400, 'msg': '单次批量删除不能超过50条'})
    
    deleted_count = 0
    for rid in ids:
        try:
            execute_db("DELETE FROM salary_month_record WHERE calc_record_id=?", [rid])
            execute_db("DELETE FROM salary_calc_record WHERE id=?", [rid])
            deleted_count += 1
        except Exception as e:
            continue
    
    _log('批量删除核算记录', f'批量删除{deleted_count}条核算记录')
    return jsonify({
        'code': 200,
        'msg': f'成功删除{deleted_count}条核算记录',
        'data': {'deleted_count': deleted_count}
    })

@app.route('/api/salary_record', methods=['GET'])
@login_required
def query_salary_records():
    book_id = request.args.get('book_id', '')
    year = request.args.get('year', '')
    month = request.args.get('month', '')
    dept = request.args.get('dept', '')
    unit = request.args.get('unit', '')
    name = request.args.get('name', '')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))

    where = "WHERE 1=1"
    params = []
    if book_id:
        where += " AND r.book_id=?"
        params.append(book_id)
    if year:
        where += " AND r.year=?"
        params.append(year)
    if month:
        where += " AND r.month=?"
        params.append(month)
    if dept:
        where += " AND s.dept LIKE ?"
        params.append(f'%{dept}%')
    if unit:
        where += " AND s.unit LIKE ?"
        params.append(f'%{unit}%')
    if name:
        where += " AND s.name LIKE ?"
        params.append(f'%{name}%')

    total = query_db(
        f"SELECT COUNT(*) as cnt FROM salary_month_record r LEFT JOIN staff_base s ON r.staff_id=s.id {where}",
        params, one=True
    )['cnt']

    rows = query_db(
        f"""SELECT r.*, s.name, s.dept, s.unit, s.gender, b.book_name
            FROM salary_month_record r
            LEFT JOIN staff_base s ON r.staff_id=s.id
            LEFT JOIN salary_book b ON r.book_id=b.id
            {where}
            ORDER BY r.year DESC, r.month DESC, s.dept, s.name
            LIMIT ? OFFSET ?""",
        params + [per_page, (page - 1) * per_page]
    )

    records = []
    for r in rows:
        rec = dict(r)
        try:
            rec['item_values'] = json.loads(rec['item_values']) if rec['item_values'] else {}
        except:
            rec['item_values'] = {}
        records.append(rec)

    return jsonify({'code': 200, 'data': {
        'list': records, 'total': total, 'page': page, 'per_page': per_page
    }})

@app.route('/api/salary_record/<int:rid>', methods=['PUT'])
@admin_required
def update_salary_record(rid):
    data = request.get_json()
    item_values = data.get('item_values', {})
    total_income = data.get('total_income', 0)
    total_deduct = data.get('total_deduct', 0)
    real_salary = round(total_income - total_deduct, 2)
    execute_db(
        "UPDATE salary_month_record SET item_values=?, total_income=?, total_deduct=?, real_salary=? WHERE id=?",
        [json.dumps(item_values, ensure_ascii=False), total_income, total_deduct, real_salary, rid]
    )
    _log('修改薪资', f'修改薪资记录ID: {rid}')
    return jsonify({'code': 200, 'msg': '修改成功'})

@app.route('/api/export/staff', methods=['GET'])
@login_required
def export_staff():
    import pandas as pd
    from io import BytesIO
    from flask import make_response

    staff_rows = query_db("SELECT * FROM staff_base ORDER BY id")
    field_metas = query_db("SELECT * FROM staff_field_meta WHERE is_active=1 ORDER BY sort_num, id")

    data_list = []
    for s in staff_rows:
        s = dict(s)
        custom = query_db("SELECT field_code, field_val FROM staff_field_data WHERE staff_id=?", [s['id']])
        custom_map = {c['field_code']: c['field_val'] for c in custom}
        row = {'姓名': s['name'], '性别': s['gender'], '部门': s['dept'], '单位': s['unit'],
               '出生年月': s['birth_date'], '参加工作时间': s['work_start_date'], '状态': s['status']}
        for fm in field_metas:
            if fm['field_code'] in ('name', 'gender', 'dept', 'unit', 'birth_date', 'work_start_date', 'status'):
                continue
            row[fm['field_name']] = custom_map.get(fm['field_code'], '')
        row['工龄'] = _calc_work_years(s.get('work_start_date', ''))
        row['套改年限'] = _calc_taogai_years(s['id'], s.get('work_start_date', ''))
        data_list.append(row)

    df = pd.DataFrame(data_list)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='人员档案')
    output.seek(0)

    _log('导出人员', '导出人员档案Excel')
    resp = make_response(output.read())
    resp.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    resp.headers['Content-Disposition'] = 'attachment; filename=staff_export.xlsx'
    return resp

@app.route('/api/import/template', methods=['GET'])
@login_required
def download_import_template():
    import pandas as pd
    from io import BytesIO
    from flask import make_response

    field_metas = query_db("SELECT * FROM staff_field_meta WHERE is_active=1 ORDER BY sort_num, id")

    base_fields = [
        ('name', '姓名', '必填'),
        ('gender', '性别', '如：男/女'),
        ('dept', '部门', ''),
        ('unit', '单位', ''),
        ('birth_date', '出生年月', '格式：2020-01'),
        ('work_start_date', '参加工作时间', '格式：2020-01'),
        ('status', '状态', '如：在职/离职'),
    ]

    headers = []
    sample_row = []
    field_code_list = []

    for code, name, hint in base_fields:
        headers.append(name)
        sample_row.append(hint)
        field_code_list.append(code)

    for fm in field_metas:
        if fm['field_code'] in ('name', 'gender', 'dept', 'unit', 'birth_date', 'work_start_date', 'status'):
            continue
        headers.append(fm['field_name'])
        field_code_list.append(fm['field_code'])
        opts = fm['options'] if fm['options'] else ''
        if fm['field_type'] == 'select' and opts:
            sample_row.append('如：' + opts)
        elif fm['field_type'] == 'number':
            sample_row.append('数字')
        elif fm['field_type'] in ('date', 'dateym'):
            sample_row.append('格式：2020-01')
        else:
            sample_row.append('')

    df = pd.DataFrame([sample_row], columns=headers)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='人员导入模板')
        ws = writer.sheets['人员导入模板']
        for col_idx in range(len(headers)):
            col_letter = chr(65 + col_idx) if col_idx < 26 else chr(64 + col_idx // 26) + chr(65 + col_idx % 26)
            max_len = max(len(str(headers[col_idx])), len(str(sample_row[col_idx]))) + 4
            ws.column_dimensions[col_letter].width = max(max_len, 12)
    output.seek(0)

    resp = make_response(output.read())
    resp.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    resp.headers['Content-Disposition'] = 'attachment; filename=staff_import_template.xlsx'
    return resp

@app.route('/api/import/staff', methods=['POST'])
@admin_required
def import_staff():
    import pandas as pd

    if 'file' not in request.files:
        return jsonify({'code': 400, 'msg': '请选择文件'})
    file = request.files['file']
    if not file.filename:
        return jsonify({'code': 400, 'msg': '文件名为空'})
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'code': 400, 'msg': '仅支持Excel文件（.xlsx/.xls）'})

    try:
        df = pd.read_excel(file, dtype=str)
        df = df.fillna('')
    except Exception as e:
        return jsonify({'code': 400, 'msg': f'文件读取失败: {str(e)}'})

    if df.empty:
        return jsonify({'code': 400, 'msg': '文件内容为空'})

    field_metas = query_db("SELECT * FROM staff_field_meta WHERE is_active=1 ORDER BY sort_num, id")
    name_to_code = {}
    base_codes = {'name', 'gender', 'dept', 'unit', 'birth_date', 'work_start_date', 'status'}
    base_name_map = {'姓名': 'name', '性别': 'gender', '部门': 'dept', '单位': 'unit',
                     '出生年月': 'birth_date', '参加工作时间': 'work_start_date', '状态': 'status'}
    name_to_code.update(base_name_map)
    for fm in field_metas:
        name_to_code[fm['field_name']] = fm['field_code']

    columns = list(df.columns)
    col_mapping = {}
    for col in columns:
        col_stripped = col.strip()
        if col_stripped in name_to_code:
            col_mapping[col] = name_to_code[col_stripped]

    if 'name' not in col_mapping.values():
        return jsonify({'code': 400, 'msg': '模板中未找到"姓名"列，请使用系统下载的导入模板'})

    added = 0
    updated = 0
    skipped = 0
    errors = []

    for idx, row in df.iterrows():
        row_num = idx + 2
        row_data = {}
        for col in columns:
            if col in col_mapping:
                val = str(row[col]).strip() if row[col] else ''
                if val == 'nan' or val == 'None':
                    val = ''
                row_data[col_mapping[col]] = val

        from db import clean_date_format
        
        if 'birth_date' in row_data and row_data['birth_date']:
            row_data['birth_date'] = clean_date_format(row_data['birth_date'])
        
        if 'work_start_date' in row_data and row_data['work_start_date']:
            row_data['work_start_date'] = clean_date_format(row_data['work_start_date'])

        name_val = row_data.get('name', '').strip()
        if not name_val:
            errors.append(f'第{row_num}行：姓名为空，已跳过')
            skipped += 1
            continue

        existing = query_db("SELECT id FROM staff_base WHERE name=?", [name_val], one=True)

        if existing:
            sid = existing['id']
            base_updates = {}
            for code in base_codes:
                if code == 'name':
                    continue
                if code in row_data and row_data[code]:
                    base_updates[code] = row_data[code]
            if base_updates:
                need_recalc = False
                if 'gender' in base_updates or 'birth_date' in base_updates:
                    need_recalc = True
                
                set_clause = ', '.join([f"{k}=?" for k in base_updates.keys()])
                execute_db(f"UPDATE staff_base SET {set_clause} WHERE id=?", list(base_updates.values()) + [sid])
                
                if need_recalc:
                    from db import calculate_retirement_date
                    update_gender = row_data.get('gender', '').strip()
                    update_birth = row_data.get('birth_date', '').strip()
                    
                    if not update_gender or not update_birth:
                        existing_staff = query_db("SELECT gender, birth_date FROM staff_base WHERE id=?", [sid], one=True)
                        if existing_staff:
                            if not update_gender:
                                update_gender = dict(existing_staff).get('gender', '') or ''
                            if not update_birth:
                                update_birth = dict(existing_staff).get('birth_date', '') or ''
                    
                    if update_gender and update_birth:
                        new_retire = calculate_retirement_date(update_birth, update_gender) or ''
                        execute_db("UPDATE staff_base SET retirement_date=? WHERE id=?", [new_retire, sid])

            for fm in field_metas:
                code = fm['field_code']
                if code in base_codes:
                    continue
                if code in row_data and row_data[code]:
                    fd = query_db("SELECT id FROM staff_field_data WHERE staff_id=? AND field_code=?", [sid, code], one=True)
                    if fd:
                        execute_db("UPDATE staff_field_data SET field_val=? WHERE staff_id=? AND field_code=?", [row_data[code], sid, code])
                    else:
                        execute_db("INSERT INTO staff_field_data (staff_id, field_code, field_val) VALUES (?,?,?)", [sid, code, row_data[code]])
            updated += 1
        else:
            import_gender = row_data.get('gender', '').strip()
            import_birth = row_data.get('birth_date', '').strip()
            
            retirement_date = ''
            if import_birth and import_gender:
                from db import calculate_retirement_date
                retirement_date = calculate_retirement_date(import_birth, import_gender) or ''
            
            last_id = execute_db(
                "INSERT INTO staff_base (name, gender, dept, unit, birth_date, work_start_date, status, retirement_date) VALUES (?,?,?,?,?,?,?,?)",
                [name_val, import_gender, row_data.get('dept', ''), row_data.get('unit', ''),
                 import_birth, row_data.get('work_start_date', ''), row_data.get('status', '在职'), retirement_date]
            )

            custom_values = []
            for fm in field_metas:
                code = fm['field_code']
                if code in base_codes:
                    continue
                if code in row_data and row_data[code]:
                    custom_values.append((last_id, code, row_data[code]))
            if custom_values:
                execute_db_many(
                    "INSERT INTO staff_field_data (staff_id, field_code, field_val) VALUES (?,?,?)",
                    custom_values
                )
            added += 1

    result_msg = f'导入完成：新增{added}人，更新{updated}人，跳过{skipped}行'
    if errors:
        result_msg += f'，{len(errors)}个警告'
    _log('导入人员', result_msg)

    return jsonify({
        'code': 200,
        'msg': result_msg,
        'data': {
            'added': added,
            'updated': updated,
            'skipped': skipped,
            'errors': errors[:20]
        }
    })

@app.route('/api/export/salary', methods=['GET'])
@login_required
def export_salary():
    import pandas as pd
    from io import BytesIO
    from flask import make_response

    book_id = request.args.get('book_id', '')
    year = request.args.get('year', '')
    month = request.args.get('month', '')

    where = "WHERE 1=1"
    params = []
    if book_id:
        where += " AND r.book_id=?"
        params.append(book_id)
    if year:
        where += " AND r.year=?"
        params.append(year)
    if month:
        where += " AND r.month=?"
        params.append(month)

    rows = query_db(
        f"""SELECT r.*, s.name, s.dept, s.unit, s.gender, b.book_name
            FROM salary_month_record r
            LEFT JOIN staff_base s ON r.staff_id=s.id
            LEFT JOIN salary_book b ON r.book_id=b.id
            {where} ORDER BY s.dept, s.unit, s.name""",
        params
    )

    all_item_names = set()
    records = []
    for r in rows:
        rec = dict(r)
        try:
            iv = json.loads(rec['item_values']) if rec['item_values'] else {}
        except:
            iv = {}
        rec['item_values'] = iv
        all_item_names.update(iv.keys())
        records.append(rec)

    item_names = sorted(all_item_names)
    data_list = []
    for rec in records:
        row = {'帐套': rec.get('book_name', ''), '姓名': rec.get('name', ''),
               '性别': rec.get('gender', ''), '部门': rec.get('dept', ''), '单位': rec.get('unit', ''),
               '年份': rec['year'], '月份': rec['month']}
        for iname in item_names:
            row[iname] = rec['item_values'].get(iname, 0)
        row['应发合计'] = rec.get('total_income', 0)
        row['扣款合计'] = rec.get('total_deduct', 0)
        row['实发工资'] = rec.get('real_salary', 0)
        data_list.append(row)

    df = pd.DataFrame(data_list)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='薪资明细')
    output.seek(0)

    _log('导出薪资', '导出薪资明细Excel')
    resp = make_response(output.read())
    resp.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    resp.headers['Content-Disposition'] = 'attachment; filename=salary_export.xlsx'
    return resp

@app.route('/api/dept_list', methods=['GET'])
@login_required
def get_dept_list():
    rows = query_db("SELECT DISTINCT dept FROM staff_base WHERE dept != '' ORDER BY dept")
    return jsonify({'code': 200, 'data': [r['dept'] for r in rows]})

@app.route('/api/dept_unit_map', methods=['GET'])
@login_required
def get_dept_unit_map():
    rows = query_db("SELECT DISTINCT dept, unit FROM staff_base WHERE dept != '' AND unit != '' ORDER BY dept, unit")
    result = {}
    for r in rows:
        if r['dept'] not in result:
            result[r['dept']] = []
        if r['unit'] not in result[r['dept']]:
            result[r['dept']].append(r['unit'])
    return jsonify({'code': 200, 'data': result})

@app.route('/api/unit_list', methods=['GET'])
@login_required
def get_unit_list():
    dept = request.args.get('dept', '')
    if dept:
        rows = query_db("SELECT DISTINCT unit FROM staff_base WHERE dept=? AND unit != '' ORDER BY unit", [dept])
    else:
        rows = query_db("SELECT DISTINCT unit FROM staff_base WHERE unit != '' ORDER BY unit")
    return jsonify({'code': 200, 'data': [r['unit'] for r in rows]})

@app.route('/api/dashboard', methods=['GET'])
@login_required
def dashboard():
    staff_total = query_db("SELECT COUNT(*) as cnt FROM staff_base WHERE status='在职'", one=True)['cnt']
    book_total = query_db("SELECT COUNT(*) as cnt FROM salary_book WHERE is_active=1", one=True)['cnt']
    dept_total = query_db("SELECT COUNT(DISTINCT dept) as cnt FROM staff_base WHERE dept != '' AND status='在职'", one=True)['cnt']
    calc_total = query_db("SELECT COUNT(*) as cnt FROM salary_calc_record", one=True)['cnt']
    return jsonify({
        'code': 200,
        'data': {'staff_total': staff_total, 'book_total': book_total, 'dept_total': dept_total, 'calc_total': calc_total}
    })

@app.route('/shutdown', methods=['GET', 'POST'])
def shutdown():
    func = request.environ.get('werkzeug.server.shutdown')
    if func:
        func()
    return 'Shutting down...'

if __name__ == '__main__':
    init_db()
    
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--prod':
        print("生产模式启动...")
        app.run(host='0.0.0.0', port=5050, debug=False, use_reloader=False)
    else:
        print("开发模式启动...")
        app.run(host='127.0.0.1', port=5050, debug=False, use_reloader=False)
