# -*- mode: python ; coding: utf-8 -*-
"""
编外人员管理系统 - Linux/统信UOS PyInstaller打包配置
生成独立的Linux可执行文件
支持：统信UOS、深度Linux、Ubuntu、Debian等
"""

import sys
import os

block_cipher = None

# 项目根目录
PROJECT_DIR = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    [os.path.join(PROJECT_DIR, 'launcher_linux.py')],
    pathex=[PROJECT_DIR],
    binaries=[],
    datas=[
        # 静态资源文件（HTML/CSS/JS）
        (os.path.join(PROJECT_DIR, 'static'), 'static'),
        # 部门单位配置
        (os.path.join(PROJECT_DIR, 'dept_unit.json'), '.'),
        # 可选：包含示例数据库
        # ('data.db', '.'),
    ],
    hiddenimports=[
        # Flask核心
        'flask',
        'flask.app',
        'flask.cli',
        'jinja2',
        'jinja2.ext',
        'markupsafe',
        'werkzeug',
        'werkzeug.debug',
        'werkzeug.serving',
        
        # 数据处理
        'pandas',
        'pandas._libs',
        'openpyxl',
        'openpyxl.cell._writer',
        
        # 数据库
        'sqlite3',
        'sqlalchemy',
        
        # GTK/GI（系统托盘）
        'gi',
        'gi.repository',
        'gi.repository.Gtk',
        'gi.repository.AppIndicator3',
        'gi.repository.Gdk',
        'gi.repository.GObject',
        
        # 其他依赖
        'python_dateutil',
        'dateutil',
        'dateutil.relativedelta',
        
        # 网络相关
        'urllib',
        'urllib.request',
        'webbrowser',
        
        # 加密相关
        'hashlib',
        'secrets',
        'hmac',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的大型库，减小体积
        'matplotlib',
        'scipy',
        'IPython',
        'notebook',
        'pytest',
        'setuptools',
        'pip',
        'numpy.f2py',  # 排除numpy的Fortran部分
        'tkinter',     # Linux不需要tkinter
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='编外人员管理系统',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # 使用UPX压缩（如果安装了的话）
    console=True,  # Linux下显示控制台（方便查看日志）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name='编外人员管理系统',
)
