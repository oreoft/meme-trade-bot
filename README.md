# 币价监控交易系统

一个基于 FastAPI 和 Web 界面的代币价格监控与自动交易系统，支持多币种监控、阈值触发和自动交易功能。

## ✨ 核心特性

- **🌐 现代化 Web 界面**：基于 FastAPI 的 RESTful API 和现代化前端界面
- **📊 多币种监控**：支持同时监控多个代币的价格和市值变化
- **⚡ 实时监控**：自动恢复监控任务，系统重启后无缝继续
- **🎯 智能阈值**：支持市值阈值触发和市值变化百分比通知
- **🔄 自动交易**：集成 Jupiter DEX，支持达到阈值时自动出售
- **📱 即时通知**：飞书机器人通知，实时推送价格变化和交易结果
- **💾 数据持久化**：SQLite 数据库存储配置、监控记录和日志
- **🔧 动态配置**：支持运行时修改配置，无需重启服务

## 🛠️ 技术栈

- **后端**：FastAPI + SQLAlchemy + SQLite
- **前端**：HTML + JavaScript + Bootstrap
- **区块链**：Solana + Jupiter DEX
- **数据源**：Birdeye API
- **通知**：飞书机器人 Webhook

## 📦 安装依赖

```bash
pip install -r requirements.txt
```

## 🚀 启动系统

```bash
python main.py 
```

启动后访问：
- **管理界面**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs

## 📱 界面功能

### 首页仪表盘 (`/`)
- 系统概览和快速操作
- 运行状态监控

### 监控管理 (`/monitor`)
- 创建和管理监控任务
- 启动/停止监控
- 查看实时监控状态
- 配置代币地址、阈值、出售比例等参数

### 系统配置 (`/config`)
- API 密钥配置（Birdeye API）
- RPC 节点设置
- Jupiter API 配置
- 交易滑点设置

### 监控日志 (`/logs`)
- 查看详细的监控日志
- 价格变化历史
- 交易执行记录

## 🎯 快速使用指南

### 1. 基础配置
1. 启动系统：`python main.py`
2. 打开浏览器访问：http://localhost:8000
3. 进入"系统配置"页面，设置 Birdeye API 密钥

### 2. 创建监控任务
1. 进入"监控管理"页面
2. 点击"新建监控"
3. 填写以下信息：
   - **监控名称**：给监控任务起个名字
   - **代币地址**：要监控的 Solana 代币合约地址
   - **私钥**：用于交易的钱包私钥（请妥善保管）
   - **市值阈值**：达到此市值时触发自动交易
   - **出售比例**：触发时出售的代币比例（0.1 = 10%）
   - **通知地址**：飞书机器人 Webhook URL
   - **检查间隔**：价格检查间隔（秒）

### 3. 启动监控
1. 在监控列表中找到创建的任务
2. 点击"启动"按钮开始监控
3. 系统会自动发送启动通知到飞书

## ⚙️ 配置说明

### 系统配置项

| 配置项 | 描述 | 默认值 |
|--------|------|---------|
| `API_KEY` | Birdeye API 密钥 | xxx |
| `CHAIN_HEADER` | 区块链类型 | solana |
| `RPC_URL` | Solana RPC 节点地址 | https://api.mainnet-beta.solana.com |
| `JUPITER_API_URL` | Jupiter DEX API 地址 | https://quote-api.jup.ag/v6 |
| `SLIPPAGE_BPS` | 交易滑点（基点，100=1%） | 100 |

### 监控配置项

| 字段 | 描述 | 示例 |
|------|------|------|
| 监控名称 | 监控任务的标识名称 | BONK 监控 |
| 代币地址 | Solana 代币合约地址 | DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263 |
| 私钥 | 交易钱包私钥 | (Base58 格式) |
| 市值阈值 | 触发交易的市值（美元） | 1000000 |
| 出售比例 | 触发时出售比例 | 0.1 (10%) |
| 通知地址 | 飞书 Webhook URL | https://open.feishu.cn/... |
| 检查间隔 | 价格检查间隔（秒） | 5 |

## 🔐 安全注意事项

1. **私钥安全**：私钥以明文存储在数据库中，请确保：
   - 在安全的网络环境中运行
   - 定期备份 `config.db` 文件
   - 不要在公共环境中运行

2. **API 密钥**：妥善保管 Birdeye API 密钥，避免泄露

3. **网络安全**：建议在内网环境中运行，或配置防火墙规则

## 📂 项目结构

```
meme-bot/
├── main.py                 # 主启动文件和 FastAPI 应用
├── api/                    # API 路由模块
│   ├── __init__.py
│   ├── configs.py          # 配置管理 API
│   ├── logs.py            # 日志查询 API
│   ├── monitor.py         # 监控管理 API
│   ├── pages.py           # 页面路由
│   └── records.py         # 监控记录 API
├── models.py              # 数据模型定义
├── config_manager.py      # 配置管理器
├── price_monitor.py       # 价格监控核心逻辑
├── market_data.py         # 市场数据获取（Birdeye API）
├── trader.py              # 交易执行（Jupiter DEX）
├── notifier.py            # 通知发送（飞书机器人）
├── templates/             # HTML 模板文件
│   ├── base.html
│   ├── index.html
│   ├── config.html
│   ├── monitor.html
│   └── logs.html
├── static/                # 静态资源文件
│   ├── css/
│   └── js/
├── config.db              # SQLite 数据库（自动生成）
└── requirements.txt       # Python 依赖列表
```

## 🔄 核心工作流程

1. **系统启动**：
   - 初始化数据库和默认配置
   - 自动恢复之前运行的监控任务
   - 启动 FastAPI Web 服务

2. **监控循环**：
   - 定期调用 Birdeye API 获取代币价格
   - 检查是否达到设定的市值阈值
   - 根据市值变化百分比发送价格更新通知

3. **自动交易**：
   - 达到阈值时调用 Jupiter API 获取交易报价
   - 使用私钥签名并执行交易
   - 发送交易结果通知

4. **数据记录**：
   - 所有监控数据保存到数据库
   - 记录价格变化、交易执行等详细日志

## 📚 API 文档

启动系统后访问 http://localhost:8000/docs 查看完整的 API 文档。

主要 API 端点：

- `GET /api/monitors` - 获取所有监控任务
- `POST /api/monitors` - 创建监控任务
- `POST /api/monitors/{id}/start` - 启动监控
- `POST /api/monitors/{id}/stop` - 停止监控
- `GET /api/configs` - 获取系统配置
- `PUT /api/configs/{key}` - 更新配置
- `GET /api/logs` - 获取监控日志

## ❓ 常见问题

**Q: 如何获取 Birdeye API 密钥？**
A: 访问 [Birdeye 官网](https://birdeye.so) 注册账户并申请 API 密钥。

**Q: 支持哪些区块链？**
A: 目前仅支持 Solana 区块链，后续可扩展支持其他链。

**Q: 如何确保交易安全？**
A: 系统使用 Jupiter DEX 进行交易，建议先小额测试，确认无误后再进行大额操作。

**Q: 监控任务意外停止怎么办？**
A: 系统重启时会自动恢复所有状态为"监控中"的任务，也可以手动重新启动。

**Q: 如何备份配置数据？**
A: 定期备份 `config.db` 文件即可，包含所有配置和监控记录。

## 🎊 开发说明

### 系统架构特点

- **单例模式**：PriceMonitor 使用单例模式，确保全局唯一
- **线程安全**：多线程监控任务，支持并发执行
- **配置热更新**：支持运行时修改配置，服务自动刷新
- **自动恢复**：系统重启后自动恢复监控状态
- **模块化设计**：各功能模块解耦，易于维护和扩展

### 扩展开发

1. **添加新的交易所**：在 `trader.py` 中扩展交易接口
2. **支持新的区块链**：扩展 `market_data.py` 和相关模块
3. **添加新的通知方式**：在 `notifier.py` 中添加新的通知渠道
4. **自定义监控策略**：在 `price_monitor.py` 中扩展监控逻辑

开始使用币价监控交易系统，让代币投资更加智能化！🚀 
