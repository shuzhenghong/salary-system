#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
编外人员管理系统 - Linux/统信UOS 启动器
适配：统信UOS、深度Linux、Ubuntu、Debian等Linux发行版
"""

import sys
import os
import threading
import webbrowser
import subprocess
import signal
import platform

# 获取程序运行目录
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def ensure_dirs():
    """创建必要的目录"""
    dirs = ['logs', 'backups', 'static']
    for d in dirs:
        p = os.path.join(BASE_DIR, d)
        if not os.path.exists(p):
            try:
                os.makedirs(p)
                print(f"✅ 已创建目录: {p}")
            except Exception as e:
                print(f"⚠️  创建目录失败: {p} - {e}")

def ensure_static():
    """确保静态资源文件存在"""
    static_dst = os.path.join(BASE_DIR, 'static')
    if not os.path.exists(static_dst) and getattr(sys, 'frozen', False):
        import shutil
        src = os.path.join(sys._MEIPASS, 'static')
        if os.path.exists(src):
            try:
                shutil.copytree(src, static_dst)
                print(f"✅ 已复制静态资源到: {static_dst}")
            except Exception as e:
                print(f"⚠️  复制静态资源失败: {e}")

def init_database():
    """初始化数据库和默认管理员账号"""
    from db import init_db, query_db, execute_db
    import hashlib
    import secrets
    
    print("📦 正在初始化数据库...")
    init_db()
    
    # 设置默认管理员账号
    salt = secrets.token_hex(16)
    default_password = 'admin123'
    pwd_hash = hashlib.sha256((default_password + salt).encode('utf-8')).hexdigest()
    stored = salt + '$' + pwd_hash
    
    admin = query_db("SELECT id FROM sys_user WHERE username='admin'", one=True)
    if admin:
        execute_db("UPDATE sys_user SET password=? WHERE username='admin'", [stored])
        print(f"✅ 管理员密码已重置为: {default_password}")
    else:
        execute_db("INSERT INTO sys_user (username, password, role) VALUES (?, ?, ?)", 
                   ['admin', stored, 'admin'])
        print(f"✅ 已创建默认管理员: admin / {default_password}")

class LinuxTrayIcon:
    """Linux系统托盘图标（使用gi.repository/GTK）"""
    
    def __init__(self, name='编外人员管理系统'):
        self.name = name
        self.icon = None
        self.menu = None
        self.indicator = None
        
    def create_icon(self):
        """创建系统托盘图标"""
        try:
            from gi.repository import Gtk, AppIndicator3
            
            # 创建AppIndicator（适用于Unity/GNOME/Deepin）
            self.indicator = AppIndicator3.AppIndicator3.new(
                self.name,
                'system-users',
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS
            )
            self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
            
            # 创建菜单
            self.menu = Gtk.Menu()
            
            # 打开系统菜单项
            item_open = Gtk.MenuItem(label='打开系统')
            item_open.connect('activate', self.on_open)
            self.menu.append(item_open)
            
            # 分隔线
            sep = Gtk.SeparatorMenuItem()
            self.menu.append(sep)
            
            # 退出菜单项
            item_quit = Gtk.MenuItem(label='退出系统')
            item_quit.connect('activate', self.on_quit)
            self.menu.append(item_quit)
            
            self.menu.show_all()
            self.indicator.set_menu(self.menu)
            
            print("✅ 系统托盘图标已创建")
            return True
            
        except ImportError:
            print("⚠️  未安装GTK库，将使用简化模式")
            return False
        except Exception as e:
            print(f"⚠️  创建托盘图标失败: {e}")
            return False
    
    def on_open(self, widget, data=None):
        """打开浏览器"""
        open_browser()
    
    def on_quit(self, widget, data=None):
        """退出程序"""
        print("正在退出系统...")
        stop_server()
        Gtk.main_quit()
        sys.exit(0)

def open_browser():
    """打开默认浏览器"""
    url = f'http://127.0.0.1:{PORT}'
    try:
        webbrowser.open(url)
        print(f"✅ 已打开浏览器: {url}")
    except Exception as e:
        print(f"⚠️  无法打开浏览器，请手动访问: {url}")

def run_server():
    """运行Flask服务器"""
    global running
    while running[0]:
        try:
            app.run(
                host='0.0.0.0',
                port=PORT,
                debug=False,
                use_reloader=False,
                threaded=True
            )
        except OSError as e:
            if "Address already in use" in str(e):
                print(f"⚠️  端口{PORT}已被占用，尝试使用备用端口...")
                global PORT
                PORT += 1
            else:
                raise e
        except Exception as e:
            print(f"❌ 服务器错误: {e}")
            break

def stop_server():
    """停止服务器"""
    global running
    running[0] = False
    try:
        import urllib.request
        urllib.request.urlopen(f'http://127.0.0.1:{PORT}/shutdown', timeout=2)
    except:
        pass

def signal_handler(signum, frame):
    """处理信号（Ctrl+C等）"""
    print("\n\n🛑 收到停止信号，正在关闭...")
    stop_server()
    sys.exit(0)

# 主程序入口
if __name__ == '__main__':
    print("=" * 60)
    print("  编外人员管理系统 - Linux/统信UOS 版本")
    print("=" * 60)
    print(f"  操作系统: {platform.platform()}")
    print(f"  Python版本: {platform.python_version()}")
    print(f"  运行目录: {BASE_DIR}")
    print("=" * 60)
    
    # 初始化环境
    ensure_dirs()
    ensure_static()
    
    # 设置环境变量
    os.environ['DATA_DIR'] = BASE_DIR
    
    # 导入应用
    sys.argv.append('--prod')
    from app import app
    
    # 初始化数据库和管理员账号
    init_database()
    
    # 配置端口
    PORT = 5050
    server_thread = None
    running = [True]
    
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 尝试创建系统托盘
    tray = LinuxTrayIcon()
    has_tray = tray.create_icon()
    
    # 启动服务器线程
    print(f"\n🚀 正在启动Web服务器 (端口: {PORT})...\n")
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # 等待服务器启动
    import time
    time.sleep(2)
    
    # 打开浏览器
    open_browser()
    
    print("\n" + "=" * 60)
    print("  ✅ 系统已启动！")
    print(f"  🌐 访问地址: http://127.0.0.1:{PORT}")
    print("  🔑 默认账号: admin / admin123")
    print("  💡 按 Ctrl+C 停止服务")
    if has_tray:
        print("  🖱️  可通过系统托盘图标控制")
    print("=" * 60 + "\n")
    
    # 如果有托盘，进入GTK主循环；否则保持运行
    if has_tray:
        try:
            from gi.repository import Gtk
            Gtk.main()
        except KeyboardInterrupt:
            pass
    else:
        # 无托盘模式：保持主线程运行
        try:
            while running[0] and server_thread.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    
    # 清理
    print("\n👋 感谢使用编外人员管理系统！")
    stop_server()
