#!/bin/bash
# ========================================
# 编外人员管理系统 - Linux/统信UOS 打包脚本
# 使用方法: chmod +x build_linux.sh && ./build_linux.sh
# ========================================

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  编外人员管理系统 - Linux打包工具${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检测操作系统
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS_NAME=$NAME
        OS_VERSION=$VERSION_ID
        echo -e "${GREEN}✓ 检测到系统: $OS_NAME $OS_VERSION${NC}"
        
        # 判断是否为统信/深度系统
        if [[ "$OS_NAME" == *"UOS"* ]] || [[ "$OS_NAME" == *"Deepin"* ]]; then
            echo -e "${GREEN}✓ 统信/深度系统，已优化兼容性${NC}"
            IS_UOS=true
        else
            IS_UOS=false
        fi
    else
        echo -e "${YELLOW}⚠ 无法检测操作系统，继续使用通用配置${NC}"
        IS_UOS=false
    fi
}

# 检查Python环境
check_python() {
    echo -e "\n${BLUE}[1/6] 检查Python环境...${NC}"
    
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
        echo -e "${GREEN}✓ Python版本: $PYTHON_VERSION${NC}"
        
        # 检查版本是否 >= 3.7
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
        
        if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 7 ]); then
            echo -e "${RED}✗ Python版本过低，需要3.7+${NC}"
            exit 1
        fi
    else
        echo -e "${RED}✗ 未找到Python3${NC}"
        exit 1
    fi
}

# 安装依赖
install_dependencies() {
    echo -e "\n${BLUE}[2/6] 检查并安装依赖...${NC}"
    
    # 系统依赖（GTK用于系统托盘）
    if [ "$IS_UOS" = true ] || command -v apt-get &> /dev/null; then
        echo "安装系统依赖（GTK开发库）..."
        sudo apt-get update -qq
        sudo apt-get install -y -qq \
            python3-gi \
            python3-gi-cairo \
            gir1.2-appindicator3-0.1 \
            libgtk-3-dev \
            libgirepository1.0-dev \
            upx-ucl 2>/dev/null || true
        echo -e "${GREEN}✓ 系统依赖已安装${NC}"
    elif command -v yum &> /dev/null; then
        echo "安装系统依赖..."
        sudo yum install -y \
            python3-gobject \
            gtk3-devel \
            gobject-introspection-devel \
            upx 2>/dev/null || true
        echo -e "${GREEN}✓ 系统依赖已安装${NC}"
    fi
    
    # Python依赖
    echo "检查Python包..."
    pip3 install --upgrade pip -q 2>/dev/null || true
    pip3 install \
        pyinstaller==6.20.0 \
        flask \
        pandas \
        openpyxl \
        pystray \
        pillow \
        python-dateutil \
        Flask-SQLAlchemy \
        Flask-Login \
        Flask-WTF \
        -q
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Python依赖已安装${NC}"
    else
        echo -e "${RED}✗ Python依赖安装失败${NC}"
        exit 1
    fi
}

# 清理旧的构建文件
clean_build() {
    echo -e "\n${BLUE}[3/6] 清理旧的构建文件...${NC}"
    
    rm -rf build/
    rm -rf dist_linux/
    rm -rf *.spec
    
    echo -e "${GREEN}✓ 清理完成${NC}"
}

# 执行PyInstaller打包
build_exe() {
    echo -e "\n${BLUE}[4/6] 开始PyInstaller打包...${NC}"
    echo "这可能需要几分钟时间，请耐心等待..."
    echo ""
    
    pyinstaller build_linux.spec --clean --noconfirm --distpath dist_linux
    
    if [ $? -eq 0 ]; then
        echo -e "\n${GREEN}✓ PyInstaller打包成功！${NC}"
    else
        echo -e "\n${RED}✗ 打包失败！${NC}"
        exit 1
    fi
}

# 创建启动脚本和桌面快捷方式
create_launchers() {
    echo -e "\n${BLUE}[5/6] 创建启动脚本和快捷方式...${NC}"
    
    DIST_DIR="dist_linux/编外人员管理系统"
    
    # 创建启动脚本
    cat > "$DIST_DIR/start.sh" << 'EOF'
#!/bin/bash
# 编外人员管理系统启动脚本

cd "$(dirname "$0")"

# 设置权限
chmod +x 编外人员管理系统 2>/dev/null || true

# 启动程序
./编外人员管理系统

EOF
    chmod +x "$DIST_DIR/start.sh"
    echo -e "${GREEN}✓ 创建启动脚本: start.sh${NC}"
    
    # 创建桌面快捷方式
    cat > "$DIST_DIR/编外人员管理系统.desktop" << EOF
[Desktop Entry]
Name=编外人员管理系统
Name[zh_CN]=编外人员管理系统
Comment=人员薪酬管理信息系统
Comment[zh_CN]=人员薪酬管理信息系统
Exec=bash -c "cd $(pwd)/$DIST_DIR && ./start.sh"
Icon=system-users
Terminal=false
Type=Application
Categories=Office;Finance;
StartupNotify=true
EOF
    chmod +x "$DIST_DIR/编外人员管理系统.desktop"
    echo -e "${GREEN}✓ 创建桌面快捷方式: 编外人员管理系统.desktop${NC}"
    
    # 创建README
    cat > "$DIST_DIR/README.txt" << 'EOF'
========================================
  编外人员管理系统 - Linux版使用说明
========================================

【运行方式】
方式1：双击 "编外人员管理系统" 可执行文件
方式2：双击 "start.sh" 启动脚本
方式3：在终端执行: ./start.sh

【访问地址】
http://127.0.0.1:5050

【默认账号】
用户名: admin
密码: admin123

【首次使用】
1. 双击运行程序
2. 等待浏览器自动打开
3. 使用默认账号登录
4. 建议立即修改密码

【目录说明】
├── 编外人员管理系统      主程序
├── start.sh              启动脚本
├── static/               前端页面资源
├── logs/                 日志目录
├── backups/              备份目录
└── salary.db             数据库文件

【常见问题】
Q: 提示权限不足？
A: 执行: chmod +x 编外人员管理系统 start.sh

Q: 无法打开浏览器？
A: 手动访问 http://127.0.0.1:5050

Q: 端口被占用？
A: 编辑 launcher_linux.py 修改 PORT = 5050

【技术支持】
日志位置: logs/app.log
系统要求: Linux内核3.10+, Python3.7+

========================================
EOF
    echo -e "${GREEN}✓ 创建说明文档: README.txt${NC}"
}

# 显示结果
show_result() {
    echo -e "\n${BLUE}[6/6] 打包完成！${NC}"
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  ✅ Linux版打包成功！${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "📦 输出目录: dist_linux/编外人员管理系统/"
    echo ""
    
    # 显示文件大小
    if [ -d "dist_linux/编外人员管理系统" ]; then
        echo "📋 文件列表:"
        ls -lh dist_linux/编外人员管理系统/ | grep -v "^总"
        
        EXE_SIZE=$(du -sh "dist_linux/编外人员管理系统/编外人员管理系统" 2>/dev/null | cut -f1)
        TOTAL_SIZE=$(du -sh "dist_linux/编外人员管理系统/" | cut -f1)
        
        echo ""
        echo "📊 大小统计:"
        echo "   主程序大小: $EXE_SIZE"
        echo "   总计大小: $TOTAL_SIZE"
    fi
    
    echo ""
    echo -e "${BLUE}🚀 使用方法:${NC}"
    echo "   1. 进入目录: cd dist_linux/编外人员管理系统/"
    echo "   2. 运行程序: ./编外人员管理系统"
    echo "   或: ./start.sh"
    echo ""
    echo -e "${BLUE}💡 安装到系统（可选）:${NC}"
    echo "   sudo cp -r dist_linux/编外人员管理系统/ /opt/编外人员管理系统/"
    echo "   sudo ln -sf /opt/编外人员管理系统/start.sh /usr/local/bin/编外人员管理系统"
    echo "   cp dist_linux/编外人员管理系统/编外人员管理系统.desktop ~/Desktop/"
    echo ""
    echo -e "${YELLOW}提示: 可将整个 dist_linux/编外人员管理系统/ 文件夹分发给其他用户${NC}"
    echo ""
}

# 主流程
main() {
    detect_os
    check_python
    install_dependencies
    clean_build
    build_exe
    create_launchers
    show_result
}

# 执行主函数
main "$@"
