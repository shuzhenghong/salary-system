﻿# -*- mode: python ; coding: utf-8 -*-
"""
编外人员管理系统 - PyInstaller打包配置文件
生成独立的Windows可执行文件（含系统托盘功能）
"""

import sys
import os

block_cipher = None

# 项目根目录
PROJECT_DIR = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    [os.path.join(PROJECT_DIR, 'launcher.py')],
    pathex=[PROJECT_DIR],
    binaries=[],
    datas=[
        # 静态资源文件（HTML/CSS/JS）
        (os.path.join(PROJECT_DIR, 'static'), 'static'),
        # 部门单位配置
        (os.path.join(PROJECT_DIR, 'dept_unit.json'), '.'),
        # 如果有其他数据文件，可以在这里添加
        # ('data.db', '.'),  # 可选：包含示例数据库
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
        
        # 系统托盘
        'pystray',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        
        # 其他依赖
        'python_dateutil',
        'dateutil',
        'dateutil.relativedelta',
        
        # Windows特定
        'win32api',
        'win32con',
        'pywintypes',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的大型库，减小体积
        'matplotlib',
        'scipy',
        'tkinter',
        'IPython',
        'notebook',
        'pytest',
        'setuptools',
        'pip',
        'numpy.f2py',  # 排除numpy的Fortran部分
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='人员管理系统',
    debug=False,              # 不显示调试信息
    bootloader_ignore_signals=False,
    strip=False,             # 不剥离符号（保留调试信息）
    upx=True,                # 使用UPX压缩（如果安装了的话）
    console=False,           # 不显示控制台窗口（GUI模式）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,               # 可以指定图标：icon='icon.ico'
    version=None,            # 可以添加版本信息：version='version.txt'
)
