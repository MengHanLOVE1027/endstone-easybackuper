# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.3] - 2026-02-03

### 🐛 Bug Fixes
- 修复 Go 程序中 `fmt.Sprintf` 的参数传递问题，解决日志格式化错误
- 修复 `sender` 为 None 导致的错误，优化 `on_load` 方法
- 修复 `subprocess.run` 返回值检查，正确检查 `result.returncode`
- 修复路径包含空格时的日志格式化问题
- 修复控制台和玩家帮助信息中的参数格式，将 `[数量]` 改为 `<数量>`

### ✨ New Features
- 添加 `send_to_sender` 方法，根据发送者类型自动选择输出方式（控制台/玩家）
- 添加 `easybackuper.restore.help.console` 和 `easybackuper.restore.help.player` 翻译
- 支持多种压缩格式的独立参数配置（7z、zip、tar）
- 添加调试日志配置选项（Debug_MoreLogs、Debug_MoreLogs_Player、Debug_MoreLogs_Cron）

### 📝 Documentation
- 更新 README.md 和 README_EN.md，添加完整的配置说明
- 添加压缩格式独立参数配置文档
- 添加调试配置说明

### ⚙️ Configuration Changes
- 更新默认配置值：
  - `Auto_Clean.Use_Number_Detection.Status`: `true` → `false`
  - `Auto_Clean.Use_Number_Detection.Mode`: `1` → `0`
  - `Scheduled_Tasks.Status`: `true` → `false`
  - `Restore.config.restart_server.status`: `true` → `false`
  - `Restore.config.restart_server.wait_time_s`: `10` → `3`
- 新增配置项：
  - `Compression.formats`: 支持多种压缩格式的独立配置
  - `Broadcast`: 扩展广播消息配置（Title、Message、Server_Title、Server_Message、Backup_success_Title、Backup_success_Message、Backup_wrong_Title、Backup_wrong_Message）
  - `Debug_MoreLogs`: 启用详细日志（控制台）
  - `Debug_MoreLogs_Player`: 启用详细日志（玩家）
  - `Debug_MoreLogs_Cron`: 启用详细日志（Cron任务）
  - `Restore.exe_path`: 恢复处理器路径
  - `Restore.config.restart_server.start_script_path`: 启动脚本路径
  - `Restore.config.debug`: 启用恢复调试日志

## [0.4.2] - 2026-02-02

### ✨ New Features
- 添加备份恢复功能
- 添加多格式压缩支持（7z、zip、tar.gz）
- 添加自动重启服务器功能
- 添加回档前自动备份当前世界功能
- 添加多语言支持（中文、英文）

### 🐛 Bug Fixes
- 修复备份文件路径问题
- 优化日志输出格式

## [0.4.1] - 2026-01-25

### ✨ New Features
- 添加自动定时备份功能
- 添加智能清理旧备份功能
- 添加实时通知功能
- 添加多线程加速备份功能

### 🐛 Bug Fixes
- 修复备份过程中的内存泄漏问题
- 优化文件复制性能

## [0.4.0-beta] - 2026-01-24

### ✨ Initial Release
- 基于热备份功能
- 支持手动备份
- 支持配置文件自定义
- 支持多语言界面
- 完整的日志系统
