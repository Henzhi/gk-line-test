-- =====================================================
-- 公考行测刷题系统 数据库初始化脚本
-- 数据库: gk_line_test (字符集 utf8mb4)
-- =====================================================

CREATE DATABASE IF NOT EXISTS gk_line_test
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_general_ci;

USE gk_line_test;

-- -----------------------------------------------------
-- 用户表
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS sys_user (
    id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    username    VARCHAR(50)  NOT NULL COMMENT '用户名',
    password    VARCHAR(100) NOT NULL COMMENT '密码(BCrypt加密)',
    nickname    VARCHAR(50)  DEFAULT NULL COMMENT '昵称',
    email       VARCHAR(100) DEFAULT NULL COMMENT '邮箱',
    created_at  DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at  DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_username (username)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT ='用户表';

-- -----------------------------------------------------
-- 题目表（核心）
-- 行测五大模块: 常识判断/言语理解/数量关系/判断推理/资料分析
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS question (
    id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    module      VARCHAR(20)  NOT NULL COMMENT '模块: 常识/言语/数量/判断/资料',
    sub_module  VARCHAR(50)  DEFAULT NULL COMMENT '子模块: 图推/定义/类比/逻辑等',
    stem        TEXT         NOT NULL COMMENT '题干文本',
    option_a    TEXT COMMENT '选项A',
    option_b    TEXT COMMENT '选项B',
    option_c    TEXT COMMENT '选项C',
    option_d    TEXT COMMENT '选项D',
    answer      CHAR(1)      NOT NULL COMMENT '正确答案 A/B/C/D',
    analysis    TEXT COMMENT '解析',
    images      JSON         DEFAULT NULL COMMENT '题干图片URL数组(图形推理/资料分析图表)',
    difficulty  TINYINT      DEFAULT 3 COMMENT '难度 1-5',
    source      VARCHAR(100) DEFAULT NULL COMMENT '来源(如 2023国考行测)',
    created_at  DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at  DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    KEY idx_module (module),
    KEY idx_difficulty (difficulty)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT ='题目表';

-- -----------------------------------------------------
-- 试卷表
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS paper (
    id           BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    name         VARCHAR(100) NOT NULL COMMENT '卷子名称',
    year         VARCHAR(10)  DEFAULT NULL COMMENT '年份',
    exam_type    VARCHAR(20)  DEFAULT NULL COMMENT '考试类型: 国考/省考/联考',
    total_score  DECIMAL(5, 1) DEFAULT NULL COMMENT '总分',
    duration_min INT          DEFAULT NULL COMMENT '考试时长(分钟)',
    description  TEXT COMMENT '描述',
    created_at   DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at   DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT ='试卷表';

-- -----------------------------------------------------
-- 试卷-题目关联表（记录题号顺序和分值）
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS paper_question (
    id          BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
    paper_id    BIGINT        NOT NULL COMMENT '试卷ID',
    question_id BIGINT        NOT NULL COMMENT '题目ID',
    sort        INT           DEFAULT 0 COMMENT '题号顺序',
    score       DECIMAL(5, 1) DEFAULT NULL COMMENT '分值',
    PRIMARY KEY (id),
    KEY idx_paper (paper_id),
    KEY idx_question (question_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT ='试卷题目关联表';

-- -----------------------------------------------------
-- 答题记录表
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS answer_record (
    id          BIGINT   NOT NULL AUTO_INCREMENT COMMENT '主键',
    user_id     BIGINT   NOT NULL COMMENT '用户ID',
    question_id BIGINT   NOT NULL COMMENT '题目ID',
    paper_id    BIGINT   DEFAULT NULL COMMENT '试卷ID(练习模式为空)',
    user_answer CHAR(1)  DEFAULT NULL COMMENT '用户答案 A/B/C/D',
    is_correct  TINYINT  DEFAULT 0 COMMENT '是否正确 0/1',
    cost_time   INT      DEFAULT 0 COMMENT '耗时(秒)',
    answered_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '作答时间',
    PRIMARY KEY (id),
    KEY idx_user (user_id),
    KEY idx_question (question_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT ='答题记录表';

-- -----------------------------------------------------
-- 错题本表
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS wrong_question_book (
    id          BIGINT   NOT NULL AUTO_INCREMENT COMMENT '主键',
    user_id     BIGINT   NOT NULL COMMENT '用户ID',
    question_id BIGINT   NOT NULL COMMENT '题目ID',
    wrong_count INT      DEFAULT 1 COMMENT '错误次数',
    mastered    TINYINT  DEFAULT 0 COMMENT '是否已掌握 0/1',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '首次加入时间',
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_user_question (user_id, question_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT ='错题本表';
