# 系统架构设计

## 1. 整体架构

### 1.1 架构风格
本项目采用 Service-Based Architecture（SBA）,根据业务领域与功能划分为几个独立的服务，每个服务都有明确的职责边界，可以根据业务需求选择相应的技术栈，并通过http/grpc等协议进行通信。

原因：
- 相较于单体架构，本项目业务量较大，不同服务领域区分清晰且有多种技术栈的需求，SBA提供了更高的技术栈灵活性与更好的模块解耦。
- 相较于微服务架构，本项目不需要引入复杂的服务治理基础设施，服务拆分粒度也不需要过细，架构简单，更适合当前项目规模。

![alt text](../image/system-architecture.png)

### 1.2 拓扑关系

## 2. 服务内部层次

## 3. 业务服务职责

本节描述 Project、Asset 和 AI 三个业务服务的职责边界与数据所有权。各服务的数据结构和接口定义保存在对应的服务设计文档中。

### 3.1 Project Service

Project Service 负责项目的生命周期及项目级配置管理，主要包括：

- 创建项目
- 获取当前用户的项目列表
- 获取项目详情
- 更新项目配置
- 维护项目类型、视角、美术风格、描述和参考图等项目级信息

Project Service 拥有 Project 相关数据。需要生成项目参考图时，由应用层调用 AI Service，Project 领域模型不直接依赖具体的模型供应商。

数据结构：[Project Service](<data structure/project.md>)；接口：[Project Service](interfaces/project.md)

### 3.2 Asset Service

Asset Service 负责项目内资产的生命周期、组织关系和版本管理，主要包括：

- 创建或复制一个或多个资产
- 按项目、类型、标签或名称查询资产
- 获取和更新资产详情
- 删除资产
- 建立资产之间的关联
- 管理资产标签
- 创建、查询和恢复资产历史版本

Asset Service 拥有 Asset、AssetResource、AssetSnapshot 和 AssetRecord 相关数据。其他服务不得绕过 Asset Service 直接修改这些数据。

数据结构：[Asset Service](<data structure/asset.md>)；接口：[Asset Service](interfaces/asset.md)

### 3.3 AI Service

AI Service 为其他业务服务和外部调用方提供内容生成能力，主要包括：

- 生成人物资产
- 生成 UI 元素
- 生成场景和图层
- 生成图块集
- 生成对象
- 生成动画
- 生成项目参考图

AI Service 负责生成任务的组织和模型调用，不拥有 Project 或 Asset 的业务数据。生成结果需要保存为资产时，应由相应的应用服务协调 Asset Service 完成。

数据结构：[AI Service](<data structure/ai.md>)；接口：[AI Service](interfaces/ai.md)

## 4. 接入基础设施

### 4.1 Gateway 职责

Gateway 为前端和外部调用方提供统一的系统入口。系统初期使用 Nginx 作为 Gateway 的实现。
Gateway 负责：

- 将请求转发到对应的后端服务
- 终止 TLS 连接
- 转发用户认证信息
- 处理跨域请求
- 限制请求体大小
- 实施请求限流
- 控制请求超时时间
- 记录访问日志和请求追踪信息

### 4.2 边界约束

Gateway 属于接入基础设施，不是业务服务，也不包含 Project、Asset 或 AI 领域逻辑。
Gateway 不得：

- 直接访问任何业务服务的数据库
- 执行资产、项目或生成任务的业务规则
- 直接调用外部模型供应商
- 根据业务状态决定跨服务流程
- 修改业务服务返回的数据语义
Gateway 可以完成认证信息转发，但具体资源访问权限仍由对应业务服务校验。

### 4.3 请求路由与服务编排
