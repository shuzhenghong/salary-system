import sys
import os
import threading
import webbrowser

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def ensure_dirs():
    for d in ['logs', 'backups']:
        p = os.path.join(BASE_DIR, d)
        if not os.path.exists(p):
            os.makedirs(p)

def ensure_static():
    static_dst = os.path.join(BASE_DIR, 'static')
    if not os.path.exists(static_dst) and getattr(sys, 'frozen', False):
        import shutil
        src = os.path.join(sys._MEIPASS, 'static')
        if os.path.exists(src):
            shutil.copytree(src, static_dst)

ensure_dirs()
ensure_static()

os.environ['DATA_DIR'] = BASE_DIR

sys.argv.append('--prod')

from app import app
from db import init_db

init_db()

from db import query_db, execute_db
import hashlib, secrets

salt = secrets.token_hex(16)
pwd_hash = hashlib.sha256(('admin123' + salt).encode()).hexdigest()
stored = salt + '$' + pwd_hash
admin = query_db("SELECT id FROM sys_user WHERE username='admin'", one=True)
if admin:
    execute_db("UPDATE sys_user SET password=? WHERE username='admin'", [stored])
    print("管理员密码已重置为: admin123")
else:
    execute_db("INSERT INTO sys_user (username, password, role) VALUES (?, ?, ?)", ['admin', stored, 'admin'])
    print("已创建默认管理员账号: admin / admin123")

PORT = 5050
server_thread = None
running = [True]

def run_server():
    while running[0]:
        try:
            app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False, threaded=True)
        except Exception:
            pass

def start_server():
    global server_thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

def stop_server():
    running[0] = False
    import urllib.request
    try:
        urllib.request.urlopen(f'http://127.0.0.1:{PORT}/shutdown', timeout=3)
    except Exception:
        pass

def open_system():
    webbrowser.open(f'http://127.0.0.1:{PORT}')

def restart():
    stop_server()
    import time
    time.sleep(2)
    running[0] = True
    start_server()

def on_exit(icon, item):
    stop_server()
    icon.stop()

try:
    from pystray import Icon, Menu, MenuItem
    from PIL import Image, ImageDraw

    def create_image():
        img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse([8, 8, 56, 56], fill='#1890ff', outline='#096dd9', width=2)
        d.text((22, 16), '编', fill='white')
        return img

    icon = Icon('salary', create_image(), '人员薪酬管理系统')
    icon.menu = Menu(
        MenuItem('打开系统', lambda i, item: open_system()),
        MenuItem('重启服务', lambda i, item: restart()),
        MenuItem('退出系统', on_exit),
    )

    start_server()
    open_system()
    icon.run()
except ImportError:
    print("正在启动人员薪酬管理系统...")
    print(f"访问地址: http://127.0.0.1:{PORT}")
    print("按 Ctrl+C 停止服务")
    start_server()
    try:
        while True:
            input()
    except KeyboardInterrupt:
        stop_server()
