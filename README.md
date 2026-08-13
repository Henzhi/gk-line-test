# 公考行测刷题系统 (gk-line-test)

一个前后端分离的公考行测刷题系统，用于练习行测五大模块（常识判断、言语理解、数量关系、判断推理、资料分析）。

## 技术栈

| 端 | 技术 |
|---|---|
| 后端 | Spring Boot 3.5.16 · Spring Security 6 · JWT(jjwt) · MyBatis-Plus 3.5.16 · MySQL 8 · Lombok · Validation |
| 前端 | Vue 3 · Vite 6 · Element Plus · Pinia · Vue Router 4 · Axios |

## 目录结构

```
gk-line-test/
├── backend/          # SpringBoot 后端 (包名 com.gklinetest)
├── frontend/         # Vue3 前端
├── docs/             # PRD、数据模型、题库解析方案
├── data/
│   ├── pdf/          # PDF 原卷（不入库，gitignore）
│   ├── json/         # 大模型解析出的题目 JSON（不入库）
│   └── sql/          # 建库建表 SQL
└── README.md
```

## 快速开始

### 1. 初始化数据库

```bash
mysql -uroot -p < data/sql/schema.sql
```

### 2. 配置后端

编辑 `backend/src/main/resources/application.yml`，把 `spring.datasource.password` 改成你的 MySQL 密码。

### 3. 启动后端

```bash
cd backend
mvn.cmd spring-boot:run    # 注意 Windows Git Bash 下用 mvn.cmd 而非 mvn
```

后端跑在 `http://localhost:8080`。

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端跑在 `http://localhost:5173`，已配置代理将 `/api` 转发到后端 8080。

## 已实现功能

- 用户注册 / 登录（BCrypt 密码加密）
- JWT 签发与鉴权（无状态，过滤器解析 Authorization 头）
- 受保护接口示例：`GET /api/user/me`
- 统一返回结构 `Result<T>` + 全局异常处理
- 前端登录/注册页、主布局、路由守卫、axios 拦截器

## 数据库核心表

`sys_user` / `question`(题目) / `paper`(试卷) / `paper_question`(卷题关联) / `answer_record`(答题记录) / `wrong_question_book`(错题本)

建表脚本见 `data/sql/schema.sql`，数据模型与题库解析方案见 `docs/题库解析方案.md`。

## 版本说明

Spring Boot 用的是 **3.5.16**（3.x 最后一个 OSS 版本，已于 2026-06-30 EOL）。
选它而非 4.x 的原因：Spring Security 6.x 教程最丰富、MyBatis-Plus boot3 starter 最成熟，学习项目踩坑最少。API 与 4.x 大体兼容，后续升级成本可控。若想跟最新版，改 parent 为 4.1.0 并将 starter 换成 `mybatis-plus-spring-boot4-starter` 即可。

## 下一步计划

- [ ] 题库解析管道：大模型解析 PDF → 结构化 JSON → 校对 → 入库
- [ ] 刷题练习模块（按模块/难度随机抽题）
- [ ] 模拟考试模块（整套卷子限时作答、自动判分）
- [ ] 错题本模块
- [ ] 答题统计与正确率分析
