# ============================================
# 编外人员管理系统 - Dockerfile (生产优化版)
# 多阶段构建，体积更小，安全性更高
# ============================================

# ---------------------------
# 阶段1: 构建阶段
# ---------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 创建虚拟环境
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 安装Python依赖（利用Docker缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ---------------------------
# 阶段2: 运行阶段（最终镜像）
# ---------------------------
FROM python:3.11-slim AS runtime

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 安装运行时依赖（最小化）
RUN apt-get update && apt-get install -y --no-install-recommends \
    # curl用于健康检查
    curl \
    # 清理缓存减小镜像体积
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# 从构建阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 创建非root用户（安全最佳实践）
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# 设置工作目录
WORKDIR /app

# 创建数据目录并设置权限
RUN mkdir -p /app/data/logs /app/data/backups /app/data/static && \
    chown -R appuser:appuser /app

# 复制应用代码
COPY --chown=appuser:appuser . .

# 复制静态资源
COPY --chown=appuser:appuser static/ /app/static/

# 切换到非root用户
USER appuser

# 暴露端口
EXPOSE 5050

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5050/ || exit 1

# 启动命令
CMD ["python", "run.py"]
