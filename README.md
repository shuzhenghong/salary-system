# 编外人员管理系统

[![Build Docker Images](https://github.com/YOUR_USERNAME/salary-system/actions/workflows/build-docker.yml/badge.svg)](https://github.com/YOUR_USERNAME/salary-system/actions/workflows/build-docker.yml)
[![GitHub release](https://img.shields.io/github/release/YOUR_USERNAME/salary-system.svg)](https://github.com/YOUR_USERNAME/salary-system/releases)
[![Docker Pulls](https://img.shields.io/docker/pulls/bwryglxt/salary-system.svg)](https://hub.docker.com/r/bwryglxt/salary-system)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

一个轻量级的人员薪酬管理信息系统，支持多平台部署。

## ✨ 特性

- 🎯 **轻量高效** - 基于Flask + SQLite，资源占用极低
- 🐳 **容器化部署** - 支持Docker多架构镜像
- 🍎 **ARM原生支持** - Apple Silicon、树莓派、华为鲲鹏等
- 📱 **移动端适配** - 响应式设计，手机平板完美支持
- 🔒 **安全可靠** - 数据加密、权限控制、备份恢复
- 🌐 **跨平台** - Windows、Linux、macOS全平台支持

## 🚀 快速开始

### Docker部署（推荐）

```bash
# 拉取镜像（自动选择适合你CPU的版本）
docker pull ghcr.io/your_username/salary-system:latest

# 运行容器
docker run -d \
    --name salary-system \
    -p 5050:5050 \
    -v salary-data:/app/data \
    ghcr.io/your_username/salary-system:latest

# 访问系统
# http://localhost:5050
# 默认账号: admin / admin123
```

### 支持的平台

| 平台 | 架构 | 适用设备 |
|------|------|----------|
| ✅ linux/amd64 | x86_64 | 标准PC/服务器/云主机 |
| ✅ linux/arm64 | aarch64 | Apple M系列、树莓派4/5、华为鲲鹏 |
| ✅ linux/arm/v7 | armv7l | 树莓派3/Zero W |

### 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 运行
python app.py

# 访问 http://localhost:5050
```

## 📖 文档

- [Docker部署指南](Docker部署指南.md) - Docker详细部署文档
- [ARM部署指南](ARM_Docker部署指南.md) - ARM设备专项指南
- [GitHub Actions使用](GitHub_Actions使用指南.md) - 自动构建配置

## 🛠️ 功能模块

- ✅ 人员信息档案管理
- ✅ 薪资核算与记录
- ✅ 批量删除功能
- ✅ 数据导入导出
- ✅ 字段自定义配置
- ✅ 数据备份恢复
- ✅ 系统设置与权限

## 📊 技术栈

- **后端:** Python 3.11 + Flask
- **数据库:** SQLite
- **前端:** HTML5 + CSS3 + JavaScript
- **容器:** Docker + Buildx
- **CI/CD:** GitHub Actions

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

[MIT License](LICENSE)

---

**Made with ❤️ for simplicity and efficiency**
