#!/bin/bash
# ============================================
# 编外人员管理系统 - Docker管理脚本 (Linux/Mac)
# 使用方法: chmod +x docker-manager.sh && ./docker-manager.sh
# ============================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 项目目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查Docker是否安装
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ 错误：未检测到Docker！${NC}"
        echo ""
        echo "请先安装Docker："
        echo "  Ubuntu/Debian: curl -fsSL https://get.docker.com | sh"
        echo "  Mac: 下载 Docker Desktop from https://www.docker.com/products/docker-desktop/"
        echo ""
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        echo -e "${RED}❌ 错误：Docker未运行！${NC}"
        echo ""
        echo "请先启动Docker Desktop或Docker服务："
        echo "  Linux: sudo systemctl start docker"
        echo "  Mac/Windows: 启动Docker Desktop应用"
        echo ""
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        echo -e "${RED}❌ 错误：未检测到Docker Compose！${NC}"
        echo ""
        echo "请安装Docker Compose（Docker Desktop通常已包含）"
        exit 1
    fi
}

# 获取docker-compose命令
get_compose_cmd() {
    if docker compose version &> /dev/null; then
        echo "docker compose"
    else
        echo "docker-compose"
    fi
}

# 显示菜单
show_menu() {
    clear
    echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║   编外人员管理系统 - Docker管理工具     ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"
    echo ""
    echo "请选择操作："
    echo ""
    echo -e "  ${GREEN}1)${NC} 🚀 启动服务（首次运行会自动构建）"
    echo -e "  ${GREEN}2)${NC} ⏹️  停止服务"
    echo -e "  ${GREEN}3)${NC} 🔄 重启服务"
    echo -e "  ${GREEN}4)${NC} 📊 查看状态"
    echo -e "  ${GREEN}5)${NC} 📋 查看日志"
    echo -e "  ${GREEN}6)${NC} 🔧 进入容器Shell（调试）"
    echo -e "  ${GREEN}7)${NC} 💾 备份数据"
    echo -e "  ${GREEN}8)${NC} ♻️  清理并重新构建"
    echo -e "  ${GREEN}9)${NC} 🗑️  完全卸载（删除所有数据）"
    echo -e "  ${GREEN}0)${NC} ❌ 退出"
    echo ""
}

# 启动服务
start_service() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  🚀 正在启动服务...${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    # 检查.env文件
    if [ ! -f ".env" ]; then
        echo -e "${YELLOW}ℹ️ 首次运行，创建默认配置...${NC}"
        cp .env.example .env
        echo -e "${GREEN}✅ 配置文件已创建: .env${NC}"
    fi
    
    COMPOSE_CMD=$(get_compose_cmd)
    
    # 构建并启动
    $COMPOSE_CMD up -d --build
    
    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}  ✅ 服务启动成功！${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo ""
        
        # 获取端口号
        PORT=$(grep "^PORT" .env | cut -d'=' -f2)
        PORT=${PORT:-5050}
        
        echo -e "  🌐 访问地址: ${CYAN}http://localhost:${PORT}${NC}"
        echo -e "  🔑 默认账号: admin"
        echo -e "  🔑 默认密码: admin123"
        echo ""
        echo -e "  💡 提示:"
        echo "     - 首次启动可能需要几分钟构建镜像"
        echo "     - 数据保存在Docker卷中（持久化）"
        echo ""
        
        # 尝试打开浏览器
        if command -v xdg-open &> /dev/null; then
            xdg-open "http://localhost:${PORT}" &
        elif command -v open &> /dev/null; then
            open "http://localhost:${PORT}" &
        fi
        
        sleep 2
    else
        echo -e "${RED}❌ 启动失败！请检查上方错误信息${NC}"
    fi
    
    read -p "按回车键继续..."
}

# 停止服务
stop_service() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  ⏹️  正在停止服务...${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    COMPOSE_CMD=$(get_compose_cmd)
    $COMPOSE_CMD down
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ 服务已停止${NC}"
    else
        echo -e "${YELLOW}⚠️ 停止时出现警告（可能本来就没运行）${NC}"
    fi
    
    read -p "按回车键继续..."
}

# 重启服务
restart_service() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  🔄 正在重启服务...${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    COMPOSE_CMD=$(get_compose_cmd)
    $COMPOSE_CMD restart
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ 服务重启成功${NC}"
        sleep 3
        
        PORT=$(grep "^PORT" .env | cut -d'=' -f2)
        PORT=${PORT:-5050}
        
        if command -v xdg-open &> /dev/null; then
            xdg-open "http://localhost:${PORT}" &
        elif command -v open &> /dev/null; then
            open "http://localhost:${PORT}" &
        fi
    else
        echo -e "${RED}❌ 重启失败${NC}"
    fi
    
    read -p "按回车键继续..."
}

# 查看状态
show_status() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  📊 容器运行状态${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    COMPOSE_CMD=$(get_compose_cmd)
    $COMPOSE_CMD ps
    
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  📈 资源使用情况${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    docker stats --no-stream bwryglxt-system 2>/dev/null || echo -e "${YELLOW}⚠️ 容器未运行${NC}"
    
    read -p "按回车键继续..."
}

# 查看日志
show_logs() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  📋 实时日志（按Ctrl+C退出）${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    COMPOSE_CMD=$(get_compose_cmd)
    $COMPOSE_CMD logs -f --tail=100
}

# 进入容器Shell
enter_shell() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  🔧 进入容器Shell${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo -e "输入 ${YELLOW}exit${NC} 退出容器"
    echo ""
    
    docker exec -it bwryglxt-system /bin/bash || docker exec -it bwryglxt-system /bin/sh
}

# 备份数据
backup_data() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  💾 备份数据${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    # 创建备份目录
    mkdir -p backups
    
    # 生成备份文件名
    BACKUP_FILE="backups/salary_backup_$(date +%Y%m%d_%H%M%S).tar.gz"
    
    echo -e "正在备份数据到: ${CYAN}${BACKUP_FILE}${NC}"
    echo ""
    
    # 执行备份
    docker run --rm \
        -v bwryglxt-data:/data \
        -v "$(pwd)/backups":/backups \
        alpine tar czf "/backups/salary_backup_$(date +%Y%m%d_%H%M%S).tar.gz" -C /data .
    
    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✅ 备份成功！${NC}"
        echo -e "📦 备份文件: ${BACKUP_FILE}"
        ls -lh "${BACKUP_FILE}" | awk '{print "📏 文件大小:", $5}'
    else
        echo -e "${RED}❌ 备份失败${NC}"
    fi
    
    read -p "按回车键继续..."
}

# 清理并重建
rebuild() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  ♻️ 清理并重新构建${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    echo -e "${YELLOW}⚠️ 这将：${NC}"
    echo "   - 停止当前运行的容器"
    echo "   - 删除旧镜像"
    echo "   - 重新构建新镜像"
    echo "   - 数据不会丢失（数据在独立卷中）"
    echo ""
    read -p "确认继续？(y/n): " confirm
    
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        echo ""
        echo "正在清理..."
        COMPOSE_CMD=$(get_compose_cmd)
        $COMPOSE_CMD down --rmi all --volumes 2>/dev/null || true
        
        echo "正在重新构建..."
        $COMPOSE_CMD up -d --build
        
        if [ $? -eq 0 ]; then
            echo ""
            echo -e "${GREEN}✅ 重建完成！${NC}"
            
            PORT=$(grep "^PORT" .env | cut -d'=' -f2)
            PORT=${PORT:-5050}
            
            if command -v xdg-open &> /dev/null; then
                xdg-open "http://localhost:${PORT}" &
            elif command -v open &> /dev/null; then
                open "http://localhost:${PORT}" &
            fi
        else
            echo -e "${RED}❌ 重建失败${NC}"
        fi
    else
        echo -e "${YELLOW}已取消${NC}"
    fi
    
    read -p "按回车键继续..."
}

# 完全卸载
cleanup() {
    echo ""
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}  🗑️ 完全卸载${NC}"
    echo -e "${RED}========================================${NC}"
    echo ""
    echo -e "${RED}⚠️⚠️⚠️ 警告 ⚠️⚠️⚠️${NC}"
    echo "此操作将："
    echo "  - 停止并删除所有容器"
    echo "  - 删除所有镜像"
    echo "  - 删除所有数据卷（数据库、日志等）"
    echo "  - **所有数据将永久丢失且无法恢复**"
    echo ""
    read -p "确认完全卸载？(输入 YES 确认): " confirm
    
    if [ "$confirm" = "YES" ]; then
        echo ""
        echo "正在完全卸载..."
        
        COMPOSE_CMD=$(get_compose_cmd)
        $COMPOSE_CMD down --rmi all --volumes --remove-orphans 2>/dev/null || true
        docker volume rm bwryglxt-data 2>/dev/null || true
        docker network rm bwryglxt-network 2>/dev/null || true
        
        echo ""
        echo -e "${GREEN}✅ 卸载完成！所有数据已清除${NC}"
    else
        echo -e "${YELLOW}已取消${NC}"
    fi
    
    read -p "按回车键继续..."
}

# 主程序
main() {
    check_docker
    
    while true; do
        show_menu
        read -p "请输入选项编号 (0-9): " choice
        
        case $choice in
            1) start_service ;;
            2) stop_service ;;
            3) restart_service ;;
            4) show_status ;;
            5) show_logs ;;
            6) enter_shell ;;
            7) backup_data ;;
            8) rebuild ;;
            9) cleanup ;;
            0) 
                echo ""
                echo -e "${GREEN}👋 感谢使用编外人员管理系统Docker版！${NC}"
                exit 0
                ;;
            *)
                echo -e "${YELLOW}⚠️ 无效选项，请重新选择${NC}"
                sleep 2
                ;;
        esac
    done
}

# 运行主程序
main "$@"
