# 班级管理系统

一个基于 Flask 的班级综合管理平台，支持学生管理、活动报名、二维码签到、请假审批、班级基金、荣誉成果等功能。

## 功能特性

### 用户管理
- **多角色权限体系**：管理员、班主任、班长、学生四级角色
- **注册审核机制**：新用户注册后需管理员审核通过方可使用
- **班长申请流程**：学生可在线申请担任班长，等待管理员审批

### 班级管理
- 班级信息维护（名称、年级、班主任等）
- 学生信息管理
- 教师账号管理

### 活动管理
- 活动创建与发布（校级 / 班级活动）
- 学生在线报名与审批
- **二维码签到**：自动生成签到码，学生扫码签到
- 活动状态跟踪（报名中 / 已结束 / 已取消）

### 请假管理
- 学生在线提交请假申请
- 支持请假类型选择（事假 / 病假等）
- 附件上传功能
- 多级审批流程

### 荣誉成果
- 学生提交荣誉成果（学术 / 体育 / 艺术 / 竞赛 / 其他）
- 成果审核与管理
- 支持附件上传
- Excel 导出功能

### 班级基金
- 班费收支记录管理
- 财务报表查看
- 数据导出

### 数据统计
- 实时数据概览
- 定时数据清理任务（可配置保留年限）
- 可视化统计看板

### API 接口
- JWT Token 认证
- RESTful API 设计
- 支持前后端分离调用

## 技术栈

| 类别 | 技术 |
|------|------|
| Web 框架 | Flask 2.3.3 |
| ORM | Flask-SQLAlchemy 3.1.1 |
| 认证 | Flask-Login, PyJWT |
| 表单 | Flask-WTF, WTForms |
| 数据库 | SQLite（可迁移至 MySQL/PostgreSQL） |
| 定时任务 | APScheduler 3.10.4 |
| 图片处理 | Pillow |
| Excel | openpyxl |
| 二维码 | qrcode |

## 项目结构

`
class_management/
  app.py                  # 主应用入口
  config.py               # 配置文件
  models.py               # 数据模型
  requirements.txt        # Python 依赖
  templates/              # Jinja2 模板
    login.html
    register.html
    admin/              # 管理员页面
    teacher/            # 班主任页面
    monitor/            # 班长页面
    student/            # 学生页面
  static/                # 静态资源
    uploads/            # 上传文件目录
  utils/                # 工具模块
    decorators.py       # 权限装饰器
    jwt_utils.py        # JWT 工具
    excel_export.py     # Excel 导出
    qr_code.py          # 二维码生成
    data_cleanup.py     # 数据清理
`

## 快速开始

### 环境要求

- Python 3.8+
- pip

### 安装步骤

`ash
# 1. 克隆项目
git clone <你的仓库地址>
cd class_management

# 2. 创建虚拟环境
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行应用
python app.py
`

### 初始账号

系统首次启动时会自动创建默认管理员账号：

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | dmin | dmin123 |

> ⚠️ **重要提示**：首次登录后请立即修改默认密码！

访问 [http://127.0.0.1:5000](http://127.0.0.1:5000) 即可开始使用。

## 配置说明

可以通过环境变量或修改 config.py 进行配置：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| SECRET_KEY | Flask 密钥 | 需自行设置 |
| DATABASE_URL | 数据库连接字符串 | SQLite |
| JWT_SECRET_KEY | JWT 签名密钥 | 需自行设置 |
| DATA_RETENTION_YEARS | 数据保留年限 | 5年 |

生产环境建议使用环境变量配置敏感信息：

`ash
export SECRET_KEY=your-secret-key
export JWT_SECRET_KEY=your-jwt-secret-key
export DATABASE_URL=mysql+pymysql://user:pass@localhost/class_db
`

## 使用说明

### 管理员
- 管理用户账号（审核注册、分配角色）
- 管理班级信息
- 创建活动并发布
- 审核请假申请
- 审核荣誉成果
- 管理班级基金
- 查看数据统计
- 定时数据清理

### 班主任
- 查看所带班级信息
- 管理班级学生
- 审批请假和成果

### 班长
- 管理班级日常事务
- 协助老师审核
- 查看班级统计

### 学生
- 提交请假申请
- 报名参加活动
- 上传荣誉成果
- 扫码签到
- 申请班长职位

## 开发指南

### 添加新依赖

`ash
pip install <package> >> requirements.txt
`

### 数据库迁移

系统会在首次运行时自动创建数据库表。如需修改模型结构，修改 models.py 后重启应用即可。

## 许可证

本项目仅供学习交流使用。

## 作者

班级管理系统 - 基于 Flask 构建