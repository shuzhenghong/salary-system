#!/bin/bash
# ============================================
# 编外人员管理系统 - ARM多架构镜像构建脚本
# 支持: linux/amd64, linux/arm64, linux/arm/v7
# 使用: chmod +x build-arm.sh && ./build-arm.sh
# ============================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# 配置变量
IMAGE_NAME="bwryglxt/salary-system"
VERSION="${VERSION:-1.0.0}"
REGISTRY="${REGISTRY:-docker.io}"  # 可改为私有仓库地址

echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  编外人员管理系统 - ARM镜像构建工具   ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"
echo ""

# 检查Docker和buildx
check_prerequisites() {
    echo -e "${BLUE}[1/5] 检查环境...${NC}"
    
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ 错误：未安装Docker${NC}"
        exit 1
    fi
    
    if ! docker buildx version &> /dev/null; then
        echo -e "${YELLOW}⚠️ docker buildx未启用，正在配置...${NC}"
        
        # 尝试启用buildx
        if [ -d ~/.docker/cli-plugins ]; then
            mkdir -p ~/.docker/cli-plugins
        fi
        
        # 下载buildx（如果可用）
        BUILDX_URL="https://github.com/docker/buildx/releases/download/v0.11.2/buildx-v0.11.2.linux-amd64"
        curl -fsSL "$BUILDX_URL" -o ~/.docker/cli-plugins/docker-buildx
        chmod +x ~/.docker/cli-plugins/docker-buildx
        
        if docker buildx version &> /dev/null; then
            echo -e "${GREEN}✅ docker buildx已启用${NC}"
        else
            echo -e "${RED}❌ 无法启用buildx，请手动安装${NC}"
            exit 1
        fi
    else
        echo -e "${GREEN}✅ Docker版本: $(docker --version)${NC}"
        echo -e "${GREEN}✅ BuildX版本: $(docker buildx version)${NC}"
    fi
    
    # 检查QEMU模拟器（用于跨平台构建）
    if ! docker run --rm --privileged tonistiigi/binfmt:latest > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️ QEMU模拟器可能未安装，跨平台构建可能失败${NC}"
        echo -e "   安装命令: docker run --privileged --rm tonistiigi/binfmt --install all${NC}"
    fi
}

# 创建buildx构建器（如需要）
setup_builder() {
    echo ""
    echo -e "${BLUE}[2/5] 配置BuildX构建器...${NC}"
    
    BUILDER_NAME="arm-builder"
    
    # 检查是否已存在
    if docker buildx ls | grep -q "$BUILDER_NAME"; then
        echo -e "${GREEN}✅ 构建器 '$BUILDER_NAME' 已存在${NC}"
    else
        echo -e "📦 创建多架构构建器..."
        docker buildx create --name "$BUILDER_NAME" --driver docker-container --use
        echo -e "${GREEN}✅ 构建器已创建${NC}"
    fi
    
    docker buildx inspect --bootstrap "$BUILDER_NAME" > /dev/null 2>&1 || true
}

# 显示菜单
show_menu() {
    echo ""
    echo -e "${BLUE}请选择构建目标：${NC}"
    echo ""
    echo -e "  ${GREEN}1)${NC} 🍎 仅构建 ARM64 (Apple M1/M2/M3, 树莓派4/5, 华为鲲鹏)"
    echo -e "  ${GREEN}2)${NC} 🥧 仅构建 ARM32 (树莓派3/Zero/Zero W)"
    echo -e "  ${GREEN}3)${NC} 🖥️  仅构建 AMD64 (标准x86_64服务器)"
    echo -e "  ${GREEN}4)${NC} 🌍 构建多架构 (AMD64 + ARM64 + ARM32) ⭐推荐"
    echo -e "  ${GREEN}5)${NC} 🚀 构建并推送到仓库"
    echo -e "  ${GREEN}6)${NC} 🔧 在本地测试ARM镜像 (使用QEMU)"
    echo -e "  ${GREEN}7)${NC} 📋 查看已构建的镜像"
    echo -e "  ${GREEN}0)${NC} ❌ 退出"
    echo ""
}

# 构建指定平台的镜像
build_image() {
    local platforms=$1
    local tag_suffix=$2
    local description=$3
    
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  🏗️  构建 $description 镜像${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    echo -e "平台: ${CYAN}$platforms${NC}"
    echo -e "标签: ${CYAN}${IMAGE_NAME}:${VERSION}${tag_suffix}${NC}"
    echo ""
    
    # 使用ARM优化的Dockerfile
    if [ -f "Dockerfile.arm" ]; then
        DOCKERFILE="-f Dockerfile.arm"
        echo -e "使用ARM优化版 Dockerfile"
    else
        DOCKERFILE="-f Dockerfile"
        echo -e "使用默认 Dockerfile"
    fi
    
    # 执行构建
    docker buildx build \
        --platform "$platforms" \
        --tag "${IMAGE_NAME}:${VERSION}${tag_suffix}" \
        --tag "${IMAGE_NAME}:latest${tag_suffix}" \
        $DOCKERFILE \
        --push=false \
        --load \
        .
    
    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}  ✅ 构建成功！${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo ""
        echo -e "镜像标签:"
        echo -e "  ${CYAN}${IMAGE_NAME}:${VERSION}${tag_suffix}${NC}"
        echo -e "  ${CYAN}${IMAGE_NAME}:latest${tag_suffix}${NC}"
        echo ""
        
        # 显示镜像大小
        docker images "${IMAGE_NAME}:${VERSION}${tag_suffix}" 2>/dev/null | tail -1 | awk '{printf "  📏 大小: %s\n", $7}'
    else
        echo -e "${RED}❌ 构建失败！${NC}"
        return 1
    fi
}

# 构建并推送镜像
build_and_push() {
    local platforms=$1
    
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  🚀 构建并推送多架构镜像${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    # 确认推送
    read -p "确认推送到 '${REGISTRY}/${IMAGE_NAME}'? (y/n): " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}已取消${NC}"
        return
    fi
    
    echo ""
    echo -e "目标平台: ${CYAN}$platforms${NC}"
    echo -e "镜像名称: ${CYAN}${REGISTRY}/${IMAGE_NAME}:${VERSION}${NC}"
    echo ""
    echo -e "正在构建并推送（这可能需要较长时间）..."
    echo ""
    
    # 使用ARM优化的Dockerfile
    if [ -f "Dockerfile.arm" ]; then
        DOCKERFILE="-f Dockerfile.arm"
    else
        DOCKERFILE="-f Dockerfile"
    fi
    
    # 构建并直接推送（不保存到本地）
    docker buildx build \
        --platform "$platforms" \
        --tag "${REGISTRY}/${IMAGE_NAME}:${VERSION}" \
        --tag "${REGISTRY}/${IMAGE_NAME}:latest" \
        $DOCKERFILE \
        --push \
        .
    
    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}  ✅ 构建并推送成功！${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo ""
        echo -e "镜像地址:"
        echo -e "  ${CYAN}${REGISTRY}/${IMAGE_NAME}:${VERSION}${NC}"
        echo -e "  ${CYAN}${REGISTRY}/${IMAGE_NAME}:latest${NC}"
        echo ""
        echo -e "拉取命令:"
        echo -e "  docker pull ${REGISTRY}/${IMAGE_NAME}:${VERSION}"
        echo ""
    else
        echo -e "${RED}❌ 构建或推送失败！${NC}"
    fi
}

# 在本地测试ARM镜像（使用QEMU模拟）
test_arm_locally() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  🔧 本地测试ARM镜像 (QEMU模拟)${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    # 检查是否有ARM镜像
    if ! docker images | grep -q "${IMAGE_NAME}.*arm"; then
        echo -e "${YELLOW}⚠️ 未找到ARM镜像，先构建一个...${NC}"
        build_image "linux/arm64" "-arm" "ARM64" || return 1
    fi
    
    echo -e "启动ARM64容器（使用QEMU用户态模拟）..."
    echo -e "注意：性能会比原生慢10-50倍"
    echo ""
    
    # 运行容器
    CONTAINER_ID=$(docker run -d \
        --platform linux/arm64 \
        --name "bwryglxt-test-arm" \
        -p 5051:5050 \
        -v "salary-data-arm:/app/data" \
        "${IMAGE_NAME}:${VERSION}-arm")
    
    if [ $? -eq 0 ]; then
        sleep 5
        
        # 健康检查
        if curl -sf http://localhost:5051/ > /dev/null 2>&1; then
            echo -e "${GREEN}✅ ARM容器运行成功！${NC}"
            echo ""
            echo -e "访问地址: ${CYAN}http://localhost:5051${NC}"
            echo -e "容器ID: ${CONTAINER_ID:0:12}"
            echo ""
            echo -e "停止容器: docker stop bwryglxt-test-arm"
            echo -e "删除容器: docker rm bwryglxt-test-arm"
            
            # 尝试打开浏览器
            if command -v xdg-open &> /dev/null; then
                xdg-open "http://localhost:5051" &
            elif command -v open &> /dev/null; then
                open "http://localhost:5051" &
            fi
        else
            echo -e "${YELLOW}⚠️ 容器已启动但健康检查失败，查看日志：${NC}"
            echo -e "  docker logs bwryglxt-test-arm"
        fi
    else
        echo -e "${RED}❌ 启动失败${NC}"
    fi
}

# 显示已构建的镜像
list_images() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  📋 已构建的镜像列表${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    docker images | grep -E "(REPOSITORY|${IMAGE_NAME})" || echo -e "${YELLOW}暂无镜像${NC}"
    
    echo ""
    echo -e "${BLUE}BuildX构建器状态:${NC}"
    docker buildx ls 2>/dev/null | head -20
}

# 主程序
main() {
    check_prerequisites
    setup_builder
    
    while true; do
        show_menu
        read -p "请选择操作 (0-7): " choice
        
        case $choice in
            1)
                # ARM64
                build_image "linux/arm64" "-arm" "ARM64 (aarch64)"
                ;;
            2)
                # ARM32
                build_image "linux/arm/v7" "-arm32" "ARM32 (armv7l)"
                ;;
            3)
                # AMD64
                build_image "linux/amd64" "" "AMD64 (x86_64)"
                ;;
            4)
                # 多架构
                build_image "linux/amd64,linux/arm64,linux/arm/v7" "-multi" "多架构"
                echo -e "${YELLOW}💡 提示: 多架构镜像通常用于推送，本地只能加载当前平台${NC}"
                ;;
            5)
                # 构建并推送
                build_and_push "linux/amd64,linux/arm64,linux/arm/v7"
                ;;
            6)
                # 本地测试
                test_arm_locally
                ;;
            7)
                # 列表
                list_images
                ;;
            0)
                echo ""
                echo -e "${GREEN}👋 再见！${NC}"
                exit 0
                ;;
            *)
                echo -e "${YELLOW}⚠️ 无效选项${NC}"
                ;;
        esac
        
        echo ""
        read -p "按回车键继续..." 
    done
}

# 运行主程序
main "$@"
