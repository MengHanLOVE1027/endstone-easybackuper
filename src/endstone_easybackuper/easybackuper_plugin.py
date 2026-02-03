# python 库
import re, os, json, shutil, zipfile, time
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import logging
import subprocess

# endstone 库
from endstone import Player
from endstone.command import Command, CommandSender, CommandSenderWrapper
from endstone.plugin import Plugin

# TAG: 全局常量
plugin_name = "EasyBackuper"
plugin_name_smallest = "easybackuper"
plugin_description = "基于 EndStone 的最最最简单的Python热备份插件 / The simplest Python hot backup plugin based on EndStone."
plugin_version = "0.4.3.1"
plugin_author = ["梦涵LOVE"]
plugin_the_help_link = "https://www.minebbs.com/resources/easybackuper-eb.7771/"
plugin_website = "https://minebbs.com"
plugin_github_link = "https://github.com/MengHanLOVE1027/EasyBackuper"
plugin_license = "AGPL-3.0"
plugin_copyright = "务必保留原作者信息！"

success_plugin_version = "v" + plugin_version
plugin_full_name = plugin_name + " " + success_plugin_version

# 读取文件内容
with open("./server.properties", "r") as file:
    server_properties_file = file.read()

plugin_path = Path(f"./plugins/{plugin_name}")
plugin_config_path = plugin_path / "config" / "EasyBackuper.json"
backup_tmp_path = Path("./backup_tmp")  # 临时复制解压缩路径
world_level_name = re.search(r"level-name=(.*)", server_properties_file).group(
    1
)  # 存档名称
world_folder_path = Path(f"./worlds/{world_level_name}")  # 存档路径


# TAG: 日志系统设置
# 创建logs目录
log_dir = Path("./logs/EasyBackuper")
if not log_dir.exists():
    log_dir.mkdir(parents=True, exist_ok=True)

# 设置日志文件名，按日期分割
log_file = log_dir / f"{plugin_name_smallest}_{datetime.now().strftime('%Y%m%d')}.log"

# 配置日志系统
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
    ]
)

# 创建插件专用的logger
logger = logging.getLogger(plugin_name)

# NOTE: 格式化文件大小
def format_file_size(size_bytes: int) -> str:
    """
    格式化文件大小，自动选择合适的单位
    :param size_bytes: 文件大小（字节）
    :return: 格式化后的文件大小字符串
    """
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)

    while size >= 1024 and i < len(size_names) - 1:
        size /= 1024
        i += 1

    return f"{size:.2f} {size_names[i]}"


# NOTE: 自制日志头
def plugin_print(text, level="INFO") -> bool:
    """
    自制 print 日志输出函数
    :param text: 文本内容
    :param level: 日志级别 (DEBUG, INFO, WARNING, ERROR, SUCCESS)
    :return: True
    """
    # 日志级别颜色映射
    level_colors = {
        "DEBUG": "\x1b[36m",    # 青色
        "INFO": "\x1b[37m",     # 白色
        "WARNING": "\x1b[33m",  # 黄色
        "ERROR": "\x1b[31m",    # 红色
        "SUCCESS": "\x1b[32m"   # 绿色
    }
    
    # 获取日志级别颜色
    level_color = level_colors.get(level, "\x1b[37m")
    
    # 自制Logger消息头
    logger_head = f"[\x1b[32m{plugin_name}\x1b[0m] [{level_color}{level}\x1b[0m] "
    
    # 使用锁确保线程安全
    with print_lock:
        print(logger_head + str(text))
    
    # 记录到日志文件
    log_level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "SUCCESS": logging.INFO
    }
    
    # 将SUCCESS级别映射为INFO级别记录到日志
    log_level = log_level_map.get(level, logging.INFO)
    logger.log(log_level, str(text))
    
    return True


# TAG: 默认配置文件
plugin_config_file = """
{
    "Language": "zh_CN",
    "Compression": {
        "method": "zip",
        "exe_7z_path": "./plugins/EasyBackuper/7za.exe",
        "formats": {
            "7z": {
                "extension": ".7z",
                "compress_args": ["a", "-t7z", "-mx=5"],
                "extract_args": ["x", "-y"]
            },
            "zip": {
                "extension": ".zip",
                "compress_args": ["a", "-tzip", "-mx=5"],
                "extract_args": ["x", "-y"]
            },
            "tar": {
                "extension": ".tar.gz",
                "compress_args": ["a", "-ttar", "-mx=5"],
                "extract_args": ["x", "-y"]
            }
        }
    },
    "BackupFolderPath": "./backup",
    "Max_Workers": 4,
    "Auto_Clean": {
        "Use_Number_Detection": {
            "Status": false,
            "Max_Number": 5,
            "Mode": 0
        }
    },
    "Scheduled_Tasks": {
        "Status": false,
        "Cron": "*/30 * * * * *"
    },
    "Broadcast": {
        "Status": true,
        "Time_ms": 5000,
        "Title": "[OP]要开始备份啦~",
        "Message": "将于 5秒 后进行备份！",
        "Server_Title": "[Server]Never Gonna Give You UP~",
        "Server_Message": "Never Gonna Let You Down~",
        "Backup_success_Title": "备份完成！",
        "Backup_success_Message": "星级服务，让爱连接",
        "Backup_wrong_Title": "很好的邢级服务，使我备份失败",
        "Backup_wrong_Message": "RT"
    },
    "Debug_MoreLogs": false,
    "Debug_MoreLogs_Player": false,
    "Debug_MoreLogs_Cron": false,
    "Restore": {
        "exe_path": "./plugins/EasyBackuper/restore_handler.exe",
        "config": {
            "restart_server": {
                "status": false,
                "wait_time_s": 3,
                "start_script_path": "./start.bat"
            },
            "backup_old_world_before_restore": true,
            "debug": false
        }
    }
}
"""

# TAG: 默认翻译文件内容
default_translations = {
    "zh_CN": {
        "easybackuper.auto_clean.disabled": "自动清理功能未启用",
        "easybackuper.auto_clean.deleted": "已删除旧备份: %s",
        "easybackuper.auto_clean.success": "清理成功，清理了: %s",
        "easybackuper.auto_clean.failed": "自动清理备份失败: %s",
        "easybackuper.auto_clean.clean": "本小姐看了一下，很干净捏~",
        "easybackuper.backup.started": "自动备份已启动，间隔: %s秒",
        "easybackuper.backup.start_failed": "启动自动备份失败: %s",
        "easybackuper.backup.stopped": "自动备份已停止",
        "easybackuper.backup.task_running": "已有备份任务正在进行中，跳过此次备份",
        "easybackuper.backup.scheduled_task": "执行定时备份任务",
        "easybackuper.backup.folder_not_exist": "备份文件夹不存在: %s",
        "easybackuper.backup.broadcast_failed": "发送备份失败标题消息失败: %s",
        "easybackuper.backup.broadcast_success_failed": "发送备份成功标题消息失败: %s",
        "easybackuper.backup.error": "备份过程中发生错误: %s",
        "easybackuper.backup.inited": "初始化完成",
        "easybackuper.backup.reloaded": "重载完成",
        "easybackuper.backup.reload_rejected": "正在备份中，拒绝重载配置文件",
        "easybackuper.plugin.enabled": "%s 插件已启用！",
        "easybackuper.plugin.start_clean": "正在执行开服清理...",
        "easybackuper.plugin.disabling": "%s 插件即将禁用...",
        "easybackuper.plugin.disabled": "%s 插件已禁用！",
        "easybackuper.backup.paused": "正在暂停存档写入...",
        "easybackuper.backup.resumed": "存档写入已恢复",
        "easybackuper.backup.copying": "正在复制存档文件...",
        "easybackuper.backup.copying_file": "正在复制文件: %s -> %s",
        "easybackuper.backup.copy_failed": "复制文件失败 %s: %s",
        "easybackuper.backup.tmp_cleared": "已清除临时文件夹",
        "easybackuper.backup.query_result": "存档查询结果: %s",
        "easybackuper.backup.not_ready": "存档未准备好，继续等待...",
        "easybackuper.backup.truncating": "正在截取文件: %s",
        "easybackuper.backup.original_size": "  原始大小: %s 字节",
        "easybackuper.backup.truncate_position": "  截取位置: %s",
        "easybackuper.backup.new_size": "  截取后大小: %s 字节",
        "easybackuper.backup.size_decreased": "  文件大小变化: -%s 字节",
        "easybackuper.backup.size_increased": "  文件大小变化: +%s 字节",
        "easybackuper.backup.size_unchanged": "  文件大小无变化",
        "easybackuper.backup.truncate_error": "截取文件时发生错误: %s",
        "easybackuper.backup.truncate_exception": "截取文件异常 %s: %s",
        "easybackuper.backup.compressing_7z": "正在使用7z压缩备份...",
        "easybackuper.backup.compress_success": "该目录压缩成功！",
        "easybackuper.backup.compress_failed": "压缩失败！",
        "easybackuper.backup.dir_not_exist": "您要压缩的目录不存在...",
        "easybackuper.backup.compressing": "正在压缩备份...",
        "easybackuper.backup.add_file_failed": "添加文件到压缩包失败 %s: %s",
        "easybackuper.backup.compress_exception": "压缩文件异常: %s",
        "easybackuper.backup.success": "备份成功！\x1b[93m备份存档：%s (%s) \x1b[32m耗时: %s\x1b[0m",
        "easybackuper.broadcast.start": "开始备份力！",
        "easybackuper.broadcast.failed": "备份失败！",
        "easybackuper.broadcast.failed.message": "§2§l[EasyBackuper]§r§c备份失败！",
        "easybackuper.broadcast.success": "备份成功！§e备份存档：%s (%s) §a耗时: %s",
        "easybackuper.command.reload.success": "配置文件重载完成！",
        "easybackuper.command.reload.reloading": "正在重载配置文件...",
        "easybackuper.command.reload.auto_enabled": "自动备份已启用，将在下一个循环周期执行备份",
        "easybackuper.command.start.starting": "正在启动自动备份...",
        "easybackuper.command.start.success": "自动备份已启动！",
        "easybackuper.command.start.failed": "自动备份启动失败，请检查配置文件！",
        "easybackuper.command.stop.stopping": "正在停止自动备份...",
        "easybackuper.command.stop.success": "自动备份已停止！",
        "easybackuper.command.status.header": "===== 备份状态 =====",
        "easybackuper.command.status.auto_backup": "自动备份状态: %s",
        "easybackuper.command.status.auto_clean": "自动清理状态: %s",
        "easybackuper.command.status.debug_console": "Debug日志(控制台): %s",
        "easybackuper.command.status.debug_player": "Debug日志(玩家): %s",
        "easybackuper.command.status.debug_cron": "Debug日志(Cron): %s",
        "easybackuper.command.status.separator": "====================",
        "easybackuper.command.status.enabled": "已启用",
        "easybackuper.command.status.disabled": "未启用",
        "easybackuper.command.clean.cleaning": "正在执行清理...",
        "easybackuper.command.clean.success": "清理完成！",
        "easybackuper.command.init.initializing": "正在初始化配置文件...",
        "easybackuper.command.init.success": "配置文件初始化完成！",
        "easybackuper.plugin.installed": "%s 安装成功！",
        "easybackuper.plugin.version": "版本: %s",
        "easybackuper.plugin.help": "查看帮助：%s",
        "easybackuper.plugin.copyright": "务必保留原作者信息！",
        "easybackuper.plugin.github": "GitHub 仓库：%s",
        "easybackuper.plugin.status.auto_backup.enabled": "自动备份状态：已启用 (间隔: %s)",
        "easybackuper.plugin.status.auto_backup.disabled": "自动备份状态：未启用",
        "easybackuper.plugin.status.auto_clean.enabled": "自动清理状态：已启用 (最大保留: %s 个)",
        "easybackuper.plugin.status.auto_clean.disabled": "自动清理状态：未启用",
        "easybackuper.plugin.status.debug_console.enabled": "Debug更多日志状态(控制台)：已启用",
        "easybackuper.plugin.status.debug_console.disabled": "Debug更多日志状态(控制台)：未启用",
        "easybackuper.plugin.status.debug_player.enabled": "Debug更多日志状态(玩家)：已启用",
        "easybackuper.plugin.status.debug_player.disabled": "Debug更多日志状态(玩家)：未启用",
        "easybackuper.plugin.status.debug_cron.enabled": "Debug更多日志状态(Cron)：已启用",
        "easybackuper.plugin.status.debug_cron.disabled": "Debug更多日志状态(Cron)：未启用",
        "easybackuper.logo.author": "作者：",
        "easybackuper.logo.version": "版本：",
        "easybackuper.plugin.description": "基于 EndStone 的最最最简单的Python热备份插件",
        "easybackuper.title.no_players": "没有玩家在线，跳过发送标题消息",
        "easybackuper.lang.init": "初始化语言文件: %s",
        "easybackuper.lang.init_failed": "初始化语言文件失败 %s: %s",
        "easybackuper.copy.file_exception": "复制文件异常 %s: %s",
        "easybackuper.compress.exception": "压缩文件异常: %s",
        "easybackuper.compress.success": "该目录压缩成功！",
        "easybackuper.compress.failed": "压缩失败！",
        "easybackuper.title.send_failed": "发送标题消息给玩家 %s 失败: %s",
        "easybackuper.lang.copied": "已复制语言文件: %s",
        "easybackuper.backup.world_path": "存档路径: %s",
        "easybackuper.lang.load_failed": "加载翻译文件失败 %s: %s",
        "easybackuper.backup.truncate_list": "需要截取的文件列表: %s",
        "easybackuper.backup.7z_command": "7z命令: %s",
        "easybackuper.cron.unsupported_format": "不支持的cron表达式格式: %s",
        "easybackuper.cron.parse_failed": "无法解析cron表达式: %s",
        "easybackuper.restore.no_backups": "没有找到可用的备份文件",
        "easybackuper.restore.list.header": "===== 可用备份列表 =====",
        "easybackuper.restore.list.item": "§e[%d]§r %s (%s)",
        "easybackuper.restore.list.footer": "=====================",
        "easybackuper.restore.invalid_index": "无效的备份索引: %s",
        "easybackuper.restore.invalid_argument": "无效的参数: %s",
        "easybackuper.restore.confirm": "确认要回档到 §e%s§r 吗？此操作不可逆！",
        "easybackuper.restore.confirming": "正在回档到备份: %s",
        "easybackuper.restore.success": "回档成功！备份: %s",
        "easybackuper.restore.failed": "回档失败: %s",
        "easybackuper.restore.extracting": "正在解压备份: %s",
        "easybackuper.restore.backuping_current": "正在备份当前存档...",
        "easybackuper.restore.backup_current_success": "当前存档备份成功！",
        "easybackuper.restore.backup_current_failed": "当前存档备份失败，继续回档...",
        "easybackuper.restore.restoring": "正在恢复存档...",
        "easybackuper.restore.restore_success": "存档恢复成功！",
        "easybackuper.restore.restore_failed": "存档恢复失败: %s",
        "easybackuper.restore.no_permission": "您没有权限执行此操作！",
        "easybackuper.restore.help": "§a[EasyBackuper] §f回档命令帮助:\n§e/restore §f- 显示此帮助信息\n§e/restore list [数量] §f- 列出指定数量的备份\n§e/restore <索引> §f- 回档到指定索引的备份",
        "easybackuper.restore.help.console": "回档命令帮助:\n/restore - 显示此帮助信息\n/restore list <数量> - 列出指定数量的备份\n/restore <索引> - 回档到指定索引的备份",
        "easybackuper.restore.help.player": "回档命令帮助:\n/restore - 显示此帮助信息\n/restore list <数量> - 列出指定数量的备份\n/restore <索引> - 回档到指定索引的备份",
        "easybackuper.restore.file_not_found": "备份文件不存在: %s",
        "easybackuper.restore.extract_failed": "解压备份失败: %s",
        "easybackuper.restore.world_not_found": "存档文件夹不存在: %s",
        "easybackuper.restore.backup_in_progress": "正在备份中，请等待备份完成后再回档！",
        "easybackuper.restore.restore_in_progress": "正在回档中，请等待当前回档完成！",
        "easybackuper.restore.starting": "开始回档操作，索引: %s",
        "easybackuper.restore.rejected_backing_up": "回档操作被拒绝: 正在备份中",
        "easybackuper.restore.rejected_restoring": "回档操作被拒绝: 正在回档中",
        "easybackuper.restore.processing_request": "开始处理回档请求...",
        "easybackuper.restore.scanning_folder": "正在扫描备份文件夹: %s",
        "easybackuper.restore.found_backups": "找到 %s 个备份文件",
        "easybackuper.restore.selected_backup": "选择的备份文件: %s (时间: %s)",
        "easybackuper.restore.backup_full_path": "备份文件完整路径: %s",
        "easybackuper.restore.request_recorded": "已记录回档请求，将在服务器关闭时执行回档到第%s个备份",
        "easybackuper.restore.request_recorded_player": "已记录回档请求，将在服务器关闭时执行回档到 §e%s§r",
        "easybackuper.restore.pending_detected": "检测到待执行的回档操作，索引: %s",
        "easybackuper.restore.total_backups": "备份文件总数: %s",
        "easybackuper.restore.pending_index": "待执行的回档索引: %s",
        "easybackuper.restore.backup_file": "备份文件: %s",
        "easybackuper.restore.external_exe_not_exist": "外部回档程序不存在: %s",
        "easybackuper.restore.preparing_external_exe": "准备启动外部回档程序: %s",
        "easybackuper.restore.external_exe_args": "传递给外部程序的参数: %s",
        "easybackuper.restore.external_exe_pid": "外部程序进程ID: %s",
        "easybackuper.restore.external_exe_started": "外部回档程序已启动，将在服务器关闭后执行回档操作",
        "easybackuper.restore.external_exe_start_failed": "启动外部回档程序失败: %s",
        "easybackuper.restore.error_details": "错误详情: %s",
        "easybackuper.restore.invalid_index_range": "无效的备份索引: %s，可用范围: 1-%s",
        "easybackuper.restore.available_backups_list": "可用的备份文件列表:",
        "easybackuper.restore.backup_list_item": "  [%d] %s (时间: %s)"
    },
    "en_US": {
        "easybackuper.auto_clean.disabled": "Auto clean feature is disabled",
        "easybackuper.auto_clean.deleted": "Deleted old backup: %s",
        "easybackuper.auto_clean.success": "Clean successful, cleaned: %s",
        "easybackuper.auto_clean.failed": "Auto clean backup failed: %s",
        "easybackuper.auto_clean.clean": "Looks clean to me~",
        "easybackuper.backup.started": "Auto backup started, interval: %s seconds",
        "easybackuper.backup.start_failed": "Failed to start auto backup: %s",
        "easybackuper.backup.stopped": "Auto backup stopped",
        "easybackuper.backup.task_running": "Backup task is already in progress, skipping this backup",
        "easybackuper.backup.scheduled_task": "Executing scheduled backup task",
        "easybackuper.backup.folder_not_exist": "Backup folder does not exist: %s",
        "easybackuper.backup.broadcast_failed": "Failed to send backup failed title message: %s",
        "easybackuper.backup.broadcast_success_failed": "Failed to send backup success title message: %s",
        "easybackuper.backup.error": "Error during backup: %s",
        "easybackuper.backup.inited": "inited.",
        "easybackuper.backup.reloaded": "reloaded.",
        "easybackuper.backup.reload_rejected": "Backup in progress, refusing to reload config",
        "easybackuper.plugin.enabled": "%s plugin enabled!",
        "easybackuper.plugin.start_clean": "Starting server clean...",
        "easybackuper.plugin.disabling": "%s plugin about to disable...",
        "easybackuper.plugin.disabled": "%s plugin disabled!",
        "easybackuper.backup.paused": "Pausing save writes...",
        "easybackuper.backup.resumed": "Save writes resumed",
        "easybackuper.backup.copying": "Copying world files...",
        "easybackuper.backup.copying_file": "Copying file: %s -> %s",
        "easybackuper.backup.copy_failed": "Failed to copy file %s: %s",
        "easybackuper.backup.tmp_cleared": "Temporary folder cleared",
        "easybackuper.backup.query_result": "Save query result: %s",
        "easybackuper.backup.not_ready": "Save not ready, continuing to wait...",
        "easybackuper.backup.truncating": "Truncating file: %s",
        "easybackuper.backup.original_size": "  Original size: %s bytes",
        "easybackuper.backup.truncate_position": "  Truncate position: %s",
        "easybackuper.backup.new_size": "  Truncated size: %s bytes",
        "easybackuper.backup.size_decreased": "  File size change: -%s bytes",
        "easybackuper.backup.size_increased": "  File size change: +%s bytes",
        "easybackuper.backup.size_unchanged": "  File size unchanged",
        "easybackuper.backup.truncate_error": "Error truncating file: %s",
        "easybackuper.backup.truncate_exception": "Truncate file exception %s: %s",
        "easybackuper.backup.compressing_7z": "Compressing backup with 7z...",
        "easybackuper.backup.compress_success": "Directory compressed successfully!",
        "easybackuper.backup.compress_failed": "Compression failed!",
        "easybackuper.backup.dir_not_exist": "The directory you want to compress does not exist...",
        "easybackuper.backup.compressing": "Compressing backup...",
        "easybackuper.backup.add_file_failed": "Failed to add file to archive %s: %s",
        "easybackuper.backup.compress_exception": "Compress file exception: %s",
        "easybackuper.backup.success": "Backup successful! \x1b[93mArchive: %s (%s) \x1b[32mTime: %s\x1b[0m",
        "easybackuper.broadcast.start": "Starting backup!",
        "easybackuper.broadcast.failed": "Backup failed!",
        "easybackuper.broadcast.failed.message": "§2§l[EasyBackuper]§r§cBackup failed!",
        "easybackuper.broadcast.success": "Backup successful! §eArchive: %s (%s) §aTime: %s",
        "easybackuper.command.reload.success": "Configuration file reloaded successfully!",
        "easybackuper.command.reload.reloading": "Reloading configuration file...",
        "easybackuper.command.reload.auto_enabled": "Auto backup is enabled and will run in the next cycle",
        "easybackuper.command.start.starting": "Starting auto backup...",
        "easybackuper.command.start.success": "Auto backup started!",
        "easybackuper.command.start.failed": "Failed to start auto backup, please check the configuration file!",
        "easybackuper.command.stop.stopping": "Stopping auto backup...",
        "easybackuper.command.stop.success": "Auto backup stopped!",
        "easybackuper.command.status.header": "===== Backup Status =====",
        "easybackuper.command.status.auto_backup": "Auto backup status: %s",
        "easybackuper.command.status.auto_clean": "Auto clean status: %s",
        "easybackuper.command.status.debug_console": "Debug logs (Console): %s",
        "easybackuper.command.status.debug_player": "Debug logs (Player): %s",
        "easybackuper.command.status.debug_cron": "Debug logs (Cron): %s",
        "easybackuper.command.status.separator": "====================",
        "easybackuper.command.status.enabled": "Enabled",
        "easybackuper.command.status.disabled": "Disabled",
        "easybackuper.command.clean.cleaning": "Cleaning...",
        "easybackuper.command.clean.success": "Cleaning completed!",
        "easybackuper.command.init.initializing": "Initializing configuration files...",
        "easybackuper.command.init.success": "Configuration files initialized successfully!",
        "easybackuper.plugin.installed": "%s installed successfully!",
        "easybackuper.plugin.version": "Version: %s",
        "easybackuper.plugin.help": "View help: %s",
        "easybackuper.plugin.copyright": "Please keep the original author information!",
        "easybackuper.plugin.github": "GitHub repository: %s",
        "easybackuper.plugin.status.auto_backup.enabled": "Auto backup status: Enabled (interval: %s)",
        "easybackuper.plugin.status.auto_backup.disabled": "Auto backup status: Disabled",
        "easybackuper.plugin.status.auto_clean.enabled": "Auto clean status: Enabled (max keep: %s)",
        "easybackuper.plugin.status.auto_clean.disabled": "Auto clean status: Disabled",
        "easybackuper.plugin.status.debug_console.enabled": "Debug more logs (Console): Enabled",
        "easybackuper.plugin.status.debug_console.disabled": "Debug more logs (Console): Disabled",
        "easybackuper.plugin.status.debug_player.enabled": "Debug more logs (Player): Enabled",
        "easybackuper.plugin.status.debug_player.disabled": "Debug more logs (Player): Disabled",
        "easybackuper.plugin.status.debug_cron.enabled": "Debug more logs (Cron): Enabled",
        "easybackuper.plugin.status.debug_cron.disabled": "Debug more logs (Cron): Disabled",
        "easybackuper.logo.author": "Author: ",
        "easybackuper.logo.version": "Version: ",
        "easybackuper.plugin.description": "The simplest Python hot backup plugin based on EndStone",
        "easybackuper.title.no_players": "No players online, skipping title message",
        "easybackuper.lang.init": "Initializing language file: %s",
        "easybackuper.lang.init_failed": "Failed to initialize language file %s: %s",
        "easybackuper.copy.file_exception": "Copy file exception %s: %s",
        "easybackuper.compress.exception": "Compress file exception: %s",
        "easybackuper.compress.success": "Directory compressed successfully!",
        "easybackuper.compress.failed": "Compression failed!",
        "easybackuper.title.send_failed": "Failed to send title message to player %s: %s",
        "easybackuper.lang.copied": "Copied language file: %s",
        "easybackuper.backup.world_path": "World path: %s",
        "easybackuper.lang.load_failed": "Failed to load translation file %s: %s",
        "easybackuper.backup.truncate_list": "Files to truncate: %s",
        "easybackuper.backup.7z_command": "7z command: %s",
        "easybackuper.cron.unsupported_format": "Unsupported cron expression format: %s",
        "easybackuper.cron.parse_failed": "Failed to parse cron expression: %s",
        "easybackuper.restore.no_backups": "No available backup files found",
        "easybackuper.restore.list.header": "===== Available Backups =====",
        "easybackuper.restore.list.item": "§e[%d]§r %s (%s)",
        "easybackuper.restore.list.footer": "=====================",
        "easybackuper.restore.invalid_index": "Invalid backup index: %s",
        "easybackuper.restore.invalid_argument": "Invalid argument: %s",
        "easybackuper.restore.confirm": "Confirm restore to §e%s§r? This action cannot be undone!",
        "easybackuper.restore.confirming": "Restoring to backup: %s",
        "easybackuper.restore.success": "Restore successful! Backup: %s",
        "easybackuper.restore.failed": "Restore failed: %s",
        "easybackuper.restore.extracting": "Extracting backup: %s",
        "easybackuper.restore.backuping_current": "Backing up current world...",
        "easybackuper.restore.backup_current_success": "Current world backup successful!",
        "easybackuper.restore.backup_current_failed": "Current world backup failed, continuing restore...",
        "easybackuper.restore.restoring": "Restoring world...",
        "easybackuper.restore.restore_success": "World restore successful!",
        "easybackuper.restore.restore_failed": "World restore failed: %s",
        "easybackuper.restore.no_permission": "You don't have permission to perform this action!",
        "easybackuper.restore.help": "§a[EasyBackuper] §fRestore command help:\n§e/restore §f- Show this help message\n§e/restore list [count] §f- List specified number of backups\n§e/restore <index> §f- Restore to backup with specified index",
        "easybackuper.restore.help.console": "Restore command help:\n/restore - Show this help message\n/restore list <count> - List specified number of backups\n/restore <index> - Restore to backup with specified index",
        "easybackuper.restore.help.player": "Restore command help:\n/restore - Show this help message\n/restore list <count> - List specified number of backups\n/restore <index> - Restore to backup with specified index",
        "easybackuper.restore.file_not_found": "Backup file not found: %s",
        "easybackuper.restore.extract_failed": "Failed to extract backup: %s",
        "easybackuper.restore.world_not_found": "World folder not found: %s",
        "easybackuper.restore.backup_in_progress": "Backup in progress, please wait for backup to complete before restoring!",
        "easybackuper.restore.restore_in_progress": "Restore in progress, please wait for current restore to complete!",
        "easybackuper.restore.starting": "Starting restore operation, index: %s",
        "easybackuper.restore.rejected_backing_up": "Restore operation rejected: Backup in progress",
        "easybackuper.restore.rejected_restoring": "Restore operation rejected: Restore in progress",
        "easybackuper.restore.processing_request": "Starting to process restore request...",
        "easybackuper.restore.scanning_folder": "Scanning backup folder: %s",
        "easybackuper.restore.found_backups": "Found %s backup files",
        "easybackuper.restore.selected_backup": "Selected backup file: %s (Time: %s)",
        "easybackuper.restore.backup_full_path": "Backup file full path: %s",
        "easybackuper.restore.request_recorded": "Restore request recorded, will execute restore to backup #%s when server shuts down",
        "easybackuper.restore.request_recorded_player": "Restore request recorded, will execute restore to §e%s§r when server shuts down",
        "easybackuper.restore.pending_detected": "Detected pending restore operation, index: %s",
        "easybackuper.restore.total_backups": "Total backup files: %s",
        "easybackuper.restore.pending_index": "Pending restore index: %s",
        "easybackuper.restore.backup_file": "Backup file: %s",
        "easybackuper.restore.external_exe_not_exist": "External restore program not found: %s",
        "easybackuper.restore.preparing_external_exe": "Preparing to start external restore program: %s",
        "easybackuper.restore.external_exe_args": "Arguments passed to external program: %s",
        "easybackuper.restore.external_exe_pid": "External program process ID: %s",
        "easybackuper.restore.external_exe_started": "External restore program started, restore will execute after server shutdown",
        "easybackuper.restore.external_exe_start_failed": "Failed to start external restore program: %s",
        "easybackuper.restore.error_details": "Error details: %s",
        "easybackuper.restore.invalid_index_range": "Invalid backup index: %s, available range: 1-%s",
        "easybackuper.restore.available_backups_list": "Available backup files list:",
        "easybackuper.restore.backup_list_item": "  [%d] %s (Time: %s)"
}}
# 检查插件文件路径，以防后续出问题
if not plugin_path.exists():
    # print(f"文件夹 '{plugin_path.resolve()}' 不存在。")
    os.makedirs(plugin_path, exist_ok=True)  # 使用 makedirs 可以创建多级目录
# else:
    # print(f"文件夹 '{plugin_path.resolve()}' 存在。")

# 现在可以确保插件文件路径正常，接下来检查配置文件路径
if plugin_config_path.exists():
    # print(f"文件 '{plugin_config_path.resolve()}' 存在。")
    # 读取json文件内容
    with open(plugin_config_path, "r", encoding="utf-8") as load_f:
        pluginConfig = json.load(load_f)
else:
    # print(f"文件 '{plugin_config_path.resolve()}' 不存在。")
    # 读取默认的json配置
    # 后续的json配置文件操作都以这个开始
    pluginConfig = json.loads(plugin_config_file)

    # 初始化配置文件
    # 确保配置文件的父目录(config)存在
    plugin_config_path.parent.mkdir(parents=True, exist_ok=True)

    # 写入json配置文件
    with open(plugin_config_path, "w", encoding="utf-8") as write_f:
        # 格式化json
        write_f.write(json.dumps(pluginConfig, indent=4, ensure_ascii=False))

# TAG: 全局变量
(yes_no_console,) = (None,)

# 多线程配置
# 从配置文件读取最大线程数,如果不存在则使用默认值4
MAX_WORKERS = pluginConfig.get("Max_Workers", 4)
print_lock = Lock()  # 用于线程安全的日志输出

# Cron 相关变量
scheduled_tasks = pluginConfig["Scheduled_Tasks"]
scheduled_tasks_status = scheduled_tasks["Status"]
scheduled_tasks_cron = scheduled_tasks["Cron"]
cronExpr = scheduled_tasks_cron

# 获取配置文件中Auto_Clean配置内容
auto_cleaup = pluginConfig["Auto_Clean"]
# 读取"Use_Number_Detection"
use_number_detection = auto_cleaup["Use_Number_Detection"]
# 读取"Use_Number_Detection"中的Status, Max_Clean_Number, Mode
use_number_detection_status = use_number_detection["Status"]
use_number_detection_max_number = use_number_detection["Max_Number"]
use_number_detection_mode = use_number_detection["Mode"]

# Debug相关
Debug_MoreLogs = pluginConfig["Debug_MoreLogs"]
Debug_MoreLogs_Player = pluginConfig["Debug_MoreLogs_Player"]
Debug_MoreLogs_Cron = pluginConfig["Debug_MoreLogs_Cron"]
Cron_Use_Backup = True

class MyZipInfo(zipfile.ZipInfo):
    # 重新定义_encodeFilename方法，将编码方式改为UTF-8
    def _encodeFilename(self, zefilename):
        return zefilename.encode("utf-8")

zipfile.ZipInfo = MyZipInfo

# TAG: 插件入口点
class EasyBackuperPlugin(Plugin):
    """
    插件入口点
    """

    api_version = "0.5"
    name = plugin_name_smallest
    full_name = plugin_full_name
    description = plugin_description
    version = plugin_version
    authors = plugin_author
    website = plugin_website

    # NOTE: 注册命令
    commands = {
        # 备份主命令
        "backup": {
            "description": "EasyBackuper Backup Plugin",
            "usages": [
                "/backup",
                "/backup init",
                "/backup reload",
                "/backup start",
                "/backup stop",
                "/backup status",
                "/backup clean"
            ],
            "permissions": ["easybackuper_plugin.command.only_op"],
        },
        # 回档命令
        "restore": {
            "description": "Restore backup",
            "usages": [
                "/restore",
                "/restore list <count: int>",
                "/restore <index: int>"
            ],
            "permissions": ["easybackuper_plugin.command.only_op"]
        }
    }
    # NOTE: 权限组
    permissions = {
        # 只有 OP 玩家才可以执行命令
        "easybackuper_plugin.command.only_op": {
            "description": "Only OP Players can use this command",
            "default": "op",
        },
        # 用于普通玩家
        "easybackuper_plugin.command.players": {
            "description": "All Players can use this command",
            "default": "true",
        },
    }

    def __init__(self):
        super().__init__()
        self.last_death_locations = {}
        self.backup_task_id = None  # 存储备份任务ID
        self.scheduled_backup_enabled = False  # 自动备份状态
        self.is_backing_up = False  # 是否正在备份
        self.translations = {}  # 存储翻译字典
        self.load_translations()  # 加载翻译文件并初始化语言文件
        
        # 回档相关
        self.is_restoring = False
        self.pending_restore_index = None  # 待执行的回档索引

    def translate(self, key: str, *args) -> str:
        """
        翻译文本
        :param key: 翻译键
        :param args: 格式化参数
        :return: 翻译后的文本
        """
        # 获取配置文件中的语言设置
        language = pluginConfig.get("Language", "zh_CN")
        
        # 从翻译字典中获取对应语言的翻译
        if language in self.translations:
            text = self.translations[language].get(key, key)
        else:
            # 如果语言不存在，尝试使用中文
            text = self.translations.get("zh_CN", {}).get(key, key)
        
        # 如果有参数，进行格式化
        if args:
            try:
                return text % args
            except (TypeError, ValueError):
                return text
        
        return text

    def load_translations(self) -> None:
            """
            加载翻译文件
            :return: None
            """
            global default_translations
            
            # 翻译文件放在插件配置文件夹下的langs文件夹
            lang_dir = plugin_path / "langs"

            # 确保语言目录存在
            lang_dir.mkdir(parents=True, exist_ok=True)

            # 首先加载默认翻译到内存
            for lang, translations in default_translations.items():
                if lang not in self.translations:
                    self.translations[lang] = {}
                self.translations[lang].update(translations)

            # 检查并创建语言文件（如果不存在）
            for lang, translations in default_translations.items():
                lang_file = lang_dir / f"{lang}.json"
                if not lang_file.exists():
                    try:
                        with open(lang_file, "w", encoding="utf-8") as f:
                            json.dump({lang: translations}, f, indent=4, ensure_ascii=False)
                        plugin_print(f"初始化语言文件: {lang_file}", level="INFO")
                    except Exception as e:
                        plugin_print(f"初始化语言文件失败 {lang_file}: {str(e)}", level="ERROR")

            # 加载所有语言文件
            for lang_file in lang_dir.glob("*.json"):
                try:
                    with open(lang_file, "r", encoding="utf-8") as f:
                        lang_data = json.load(f)
                        # 合并翻译数据，确保按语言分类
                        for lang, translations in lang_data.items():
                            if lang not in self.translations:
                                self.translations[lang] = {}
                            self.translations[lang].update(translations)
                except Exception as e:
                    plugin_print(f"加载翻译文件失败 {lang_file}: {str(e)}", level="ERROR")

    # NOTE: #2备份功能
    def backup_2(self) -> None:
        """
        备份功能第二部分
        :return: None
        """
        server = self.server

        # 记录备份开始时间
        backup_start_time = time.time()

        try:
            # 备份完成后重置备份状态
            def reset_backup_status():
                self.is_backing_up = False

            # 压缩相关功能
            compression_config = pluginConfig.get("Compression", {})
            compression_method = compression_config.get("method", "zip")
            exe_7z_path = Path(compression_config.get("exe_7z_path", "./plugins/EasyBackuper/7za.exe"))
            formats = compression_config.get("formats", {})

            # 获取当前压缩格式的配置
            format_config = formats.get(compression_method, {})
            file_extension = format_config.get("extension", ".zip")
            compress_args = format_config.get("compress_args", ["a", "-tzip", "-mx=5"])

            # 暂停存档写入
            assert server.dispatch_command(server.command_sender, "save hold")
            plugin_print(self.translate("easybackuper.backup.paused"), level="INFO")

            def save_query():
                messages = []

                # sender = CommandSenderWrapper(server.command_sender, on_message=lambda msg: print(dir(msg)))
                sender = CommandSenderWrapper(
                    server.command_sender,
                    on_message=lambda msg: messages.append(msg.params),
                )

                ready = server.dispatch_command(sender, "save query")
                if not ready:
                    plugin_print(self.translate("easybackuper.backup.not_ready"), level="WARNING")
                    assert server.dispatch_command(server.command_sender, "save resume")
                    return

                if Debug_MoreLogs:
                    plugin_print(self.translate("easybackuper.backup.query_result", str(messages)), level="DEBUG")

                # 清除tmp文件夹
                if not os.path.exists(backup_tmp_path):
                    os.mkdir(backup_tmp_path)
                else:
                    shutil.rmtree(backup_tmp_path)
                    plugin_print(self.translate("easybackuper.backup.tmp_cleared"), level="DEBUG")
                # 复制存档
                plugin_print(self.translate("easybackuper.backup.copying"), level="INFO")
                
                # 多线程复制单个文件
                def copy_file(src_path, dst_path):
                    """
                    多线程复制单个文件
                    """
                    try:
                        if Debug_MoreLogs:
                            plugin_print(self.translate("easybackuper.backup.copying_file", src_path, dst_path), level="DEBUG")
                        shutil.copy2(src_path, dst_path)
                        return True
                    except Exception as e:
                        plugin_print(self.translate("easybackuper.backup.copy_failed", src_path, str(e)), level="ERROR")
                        return False
                
                # 收集所有需要复制的文件
                def collect_files(src, dst):
                    """
                    收集所有需要复制的文件
                    """
                    files_to_copy = []
                    for item in os.listdir(src):
                        src_path = os.path.join(src, item)
                        dst_path = os.path.join(dst, item)
                        
                        if os.path.isdir(src_path):
                            # 创建目标目录
                            os.makedirs(dst_path, exist_ok=True)
                            # 递归收集子目录中的文件
                            files_to_copy.extend(collect_files(src_path, dst_path))
                        else:
                            # 添加文件到复制列表
                            files_to_copy.append((src_path, dst_path))
                    return files_to_copy
                
                # 使用多线程复制文件
                def copy_directory_multithread(src, dst):
                    """
                    使用多线程复制目录
                    """
                    # 收集所有需要复制的文件
                    files_to_copy = collect_files(src, dst)
                    
                    # 使用线程池并行复制文件
                    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                        # 提交所有复制任务
                        futures = {executor.submit(copy_file, src, dst): (src, dst) for src, dst in files_to_copy}
                        
                        # 等待所有任务完成
                        for future in as_completed(futures):
                            src_path, dst_path = futures[future]
                            try:
                                future.result()
                            except Exception as e:
                                plugin_print(self.translate('easybackuper.copy.file_exception', str(src_path), str(e)), level="ERROR")
                
                # 递归复制目录，显示每个文件的操作（保留原函数作为备用）
                def copy_directory_with_progress(src, dst):
                    """
                    递归复制目录，显示每个文件的操作
                    """
                    # 遍历源目录
                    for item in os.listdir(src):
                        src_path = os.path.join(src, item)
                        dst_path = os.path.join(dst, item)

                        # 如果是目录，递归复制
                        if os.path.isdir(src_path):
                            # 创建目标目录
                            os.makedirs(dst_path, exist_ok=True)
                            copy_directory_with_progress(src_path, dst_path)
                        else:
                            # 如果是文件，复制文件
                            if Debug_MoreLogs:
                                plugin_print(self.translate("easybackuper.backup.copying_file", src_path, dst_path), level="DEBUG")
                            shutil.copy2(src_path, dst_path)

                # 创建目标目录
                os.makedirs(backup_tmp_path / world_level_name, exist_ok=True)
                # 开始复制（使用多线程）
                copy_directory_multithread(str(world_folder_path), str(backup_tmp_path / world_level_name))
                assert server.dispatch_command(server.command_sender, "save resume")
                plugin_print(self.translate("easybackuper.backup.resumed"), level="INFO")

                if Debug_MoreLogs:
                    plugin_print(self.translate("easybackuper.backup.truncate_list", messages[1][0].split(", ")), level="DEBUG")
                file_paths = messages[1][0].split(", ")

                # 截取文件
                def truncate_file(file_path, position):
                    try:
                        # 打开文件以进行读写操作
                        with open(file_path, "r+") as file:
                            # 获取文件截取前的实际大小
                            original_size = file.seek(0, os.SEEK_END)

                            # 移动到截取位置
                            file.seek(position)

                            # 执行截取操作
                            file.truncate()

                            # 获取截取后的文件大小
                            new_size = file.seek(0, os.SEEK_END)

                            # 输出截取前后的文件大小差异
                            size_difference = original_size - new_size
                            if size_difference > 0:
                                if Debug_MoreLogs:
                                    plugin_print(self.translate("easybackuper.backup.truncating", file_path), level="INFO")
                                    plugin_print(self.translate("easybackuper.backup.original_size", original_size), level="INFO")
                                    plugin_print(self.translate("easybackuper.backup.truncate_position", position), level="INFO")
                                    plugin_print(self.translate("easybackuper.backup.new_size", new_size), level="INFO")
                                    plugin_print(self.translate("easybackuper.backup.size_decreased", size_difference), level="WARNING")
                            elif size_difference < 0:
                                if Debug_MoreLogs:
                                    plugin_print(self.translate("easybackuper.backup.truncating", file_path), level="INFO")
                                    plugin_print(self.translate("easybackuper.backup.original_size", original_size), level="INFO")
                                    plugin_print(self.translate("easybackuper.backup.truncate_position", position), level="INFO")
                                    plugin_print(self.translate("easybackuper.backup.new_size", new_size), level="INFO")
                                    plugin_print(self.translate("easybackuper.backup.size_increased", abs(size_difference)), level="WARNING")
                            else:
                                if Debug_MoreLogs:
                                    plugin_print(self.translate("easybackuper.backup.truncating", file_path), level="INFO")
                                    plugin_print(self.translate("easybackuper.backup.original_size", original_size), level="INFO")
                                    plugin_print(self.translate("easybackuper.backup.new_size", new_size), level="INFO")
                                    plugin_print(self.translate("easybackuper.backup.size_unchanged"), level="INFO")

                            return True  # 截取成功

                    except Exception as e:
                        # 如果在截取过程中出现错误，打印错误信息
                        plugin_print(self.translate("easybackuper.backup.truncate_error", str(e)), level="ERROR")
                        return False  # 截取失败
                
                # 使用多线程截取文件
                def truncate_files_multithread(file_paths):
                    """
                    使用多线程截取多个文件
                    """
                    # 准备截取任务
                    truncate_tasks = []
                    for path in file_paths:
                        file_name, position = path.split(":")
                        position = int(position)
                        real_file_name = backup_tmp_path / file_name
                        truncate_tasks.append((real_file_name, position))
                    
                    # 使用线程池并行截取文件
                    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                        # 提交所有截取任务
                        futures = {executor.submit(truncate_file, file_path, position): (file_path, position) 
                                  for file_path, position in truncate_tasks}
                        
                        # 等待所有任务完成
                        for future in as_completed(futures):
                            file_path, position = futures[future]
                            try:
                                future.result()
                            except Exception as e:
                                plugin_print(self.translate("easybackuper.backup.truncate_exception", file_path, str(e)), level="ERROR")
                
                # 执行多线程截取
                truncate_files_multithread(file_paths)


                # 压缩存档
                month_rank_dir = str(backup_tmp_path)
                # 获取当前时间
                current_time = time.time()
                time_obj = datetime.fromtimestamp(current_time)
                archive_name = (
                        f"{time_obj.year}" +
                        "_" +
                        f"{time_obj.month:02d}" +
                        "_" +
                        f"{time_obj.day:02d}=" +
                        f"{time_obj.hour:02d}-" +
                        f"{time_obj.minute:02d}-" +
                        f"{time_obj.second:02d}" +
                        f"[{world_level_name}]" +
                        file_extension
                )
                zip_file_new = (
                        pluginConfig["BackupFolderPath"] + "/" + archive_name
                )

                # 根据压缩方法选择压缩方式
                if compression_method in ["7z", "zip"]:
                    if os.path.exists(month_rank_dir):
                        plugin_print(self.translate("easybackuper.backup.compressing_7z"), level="INFO")

                        if not os.path.exists(pluginConfig["BackupFolderPath"]):
                            os.mkdir(pluginConfig["BackupFolderPath"])

                        # 压缩后的名字
                        path = str(exe_7z_path) + " a -tzip " + '"' + zip_file_new + '" ' + '"./' + month_rank_dir + '/*"'
                        plugin_print(self.translate("easybackuper.backup.7z_command", path), level="DEBUG")
                        result = os.system(path)
                        if result == 0:
                            plugin_print(self.translate("easybackuper.backup.compress_success"), level="SUCCESS")
                        else:
                            plugin_print(self.translate("easybackuper.backup.compress_failed"), level="ERROR")
                            self.broadcast_backup_wrong()

                        # 清除tmp文件夹
                        if not os.path.exists(backup_tmp_path):
                            os.mkdir(backup_tmp_path)
                        else:
                            shutil.rmtree(backup_tmp_path)
                    else:
                        plugin_print(self.translate("easybackuper.backup.dir_not_exist"), level="ERROR")
                        self.broadcast_backup_wrong()
                elif compression_method == "tar":
                    # 使用tar压缩
                    import tarfile
                    if os.path.exists(month_rank_dir):
                        plugin_print(self.translate("easybackuper.backup.compressing"), level="INFO")

                        if not os.path.exists(pluginConfig["BackupFolderPath"]):
                            os.mkdir(pluginConfig["BackupFolderPath"])

                        try:
                            # 使用tar.gz格式压缩
                            with tarfile.open(zip_file_new, "w:gz") as tar:
                                # 遍历目录并添加文件到tar
                                for dir_path, dir_names, file_names in os.walk(month_rank_dir):
                                    for filename in file_names:
                                        file_path = os.path.join(dir_path, filename)
                                        # 计算归档中的相对路径
                                        arc_path = os.path.relpath(file_path, month_rank_dir)
                                        tar.add(file_path, arcname=arc_path)

                            plugin_print(self.translate('easybackuper.compress.success'), level="SUCCESS")
                        except Exception as e:
                            plugin_print(self.translate('easybackuper.compress.exception', str(e)), level="ERROR")
                            plugin_print(self.translate('easybackuper.compress.failed'), level="ERROR")
                            self.broadcast_backup_wrong()

                        # 清除tmp文件夹
                        if not os.path.exists(backup_tmp_path):
                            os.mkdir(backup_tmp_path)
                        else:
                            shutil.rmtree(backup_tmp_path)
                    else:
                        plugin_print(self.translate("easybackuper.backup.dir_not_exist"), level="ERROR")
                        self.broadcast_backup_wrong()
                else:
                    if os.path.exists(month_rank_dir):
                        plugin_print(self.translate("easybackuper.backup.compressing"), level="INFO")

                        if not os.path.exists(pluginConfig["BackupFolderPath"]):
                            os.mkdir(pluginConfig["BackupFolderPath"])

                        # 压缩后的名字
                        try:
                            # 收集所有需要压缩的文件
                            files_to_zip = []
                            for dir_path, dir_names, file_names in os.walk(month_rank_dir):
                                # 去掉目标跟路径，只对目标文件夹下面的文件及文件夹进行压缩
                                fpath = dir_path.replace(month_rank_dir, "")
                                for filename in file_names:
                                    files_to_zip.append((
                                        os.path.join(dir_path, filename),
                                        os.path.join(fpath, filename)
                                    ))
                            
                            # 多线程压缩文件
                            def add_file_to_zip(zip_file, src_path, arc_path, lock):
                                """
                                将单个文件添加到zip文件中
                                使用锁确保线程安全
                                """
                                try:
                                    # 读取文件内容
                                    with open(src_path, 'rb') as f:
                                        file_data = f.read()

                                    # 使用锁保护ZIP写入操作
                                    with lock:
                                        zip_file.writestr(arc_path, file_data)
                                    return True
                                except Exception as e:
                                    plugin_print(self.translate("easybackuper.backup.add_file_failed", src_path, str(e)), level="ERROR")
                                    return False
                            
                            # 使用线程锁保护zip文件写入
                            zip_lock = Lock()
                            
                            # 使用多线程压缩
                            with zipfile.ZipFile(zip_file_new, "w", zipfile.ZIP_DEFLATED) as zip:
                                with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                                    futures = []
                                    for src_path, arc_path in files_to_zip:
                                        futures.append(
                                            executor.submit(
                                                lambda s=src_path, a=arc_path: add_file_to_zip(zip, s, a, zip_lock)
                                            )
                                        )
                                    
                                    # 等待所有任务完成
                                    for future in as_completed(futures):
                                        try:
                                            future.result()
                                        except Exception as e:
                                            plugin_print(self.translate('easybackuper.compress.exception', str(e)), level="ERROR")
                            
                            plugin_print(self.translate('easybackuper.compress.success'), level="SUCCESS")
                        except Exception as e:
                            plugin_print(self.translate('easybackuper.compress.failed'), level="ERROR")
                            self.broadcast_backup_wrong()

                        # 清除tmp文件夹
                        if not os.path.exists(backup_tmp_path):
                            os.mkdir(backup_tmp_path)
                        else:
                            shutil.rmtree(backup_tmp_path)
                    else:
                        plugin_print(self.translate("easybackuper.backup.dir_not_exist"), level="ERROR")
                        self.broadcast_backup_wrong()

                # 备份成功后广播通知
                # 计算备份文件大小和耗时
                archive_path = Path(zip_file_new)
                backup_end_time = time.time()
                backup_elapsed = backup_end_time - backup_start_time

                # 格式化备份耗时
                if backup_elapsed < 60:
                    backup_time_str = f"{backup_elapsed:.2f}s"
                elif backup_elapsed < 3600:
                    backup_time_str = f"{backup_elapsed / 60:.2f}min"
                else:
                    backup_time_str = f"{backup_elapsed / 3600:.2f}h"

                if archive_path.exists():
                    archive_size = archive_path.stat().st_size
                    archive_size_formatted = format_file_size(archive_size)

                    # 根据Mode 1执行自动清理
                    if use_number_detection_mode == 1:
                        self.auto_clean_backups()

                    # 广播备份成功消息
                    self.broadcast_backup_success(archive_name, archive_size_formatted, backup_time_str)
                else:
                    # 根据Mode 1执行自动清理
                    if use_number_detection_mode == 1:
                        self.auto_clean_backups()

                    # 广播备份成功消息
                    self.broadcast_backup_success(backup_time=backup_time_str)

                # 重置备份状态
                reset_backup_status()

        except Exception as e:
            # 备份失败时重置备份状态
            self.logger.error(self.translate("easybackuper.backup.error", str(e)))
            plugin_print(self.translate("easybackuper.backup.error", str(e)), level="ERROR")
            reset_backup_status()

        server.scheduler.run_task(self, save_query, delay=20, period=0)
        return None

    # NOTE: 自动备份功能
    def start_scheduled_backup(self) -> bool:
        """
        启动定时备份任务
        :return: 是否成功启动
        """
        global scheduled_tasks_status, scheduled_tasks_cron, cronExpr

        # 如果已经启动了自动备份，先停止
        if self.backup_task_id is not None:
            self.stop_scheduled_backup()

        # 读取配置文件中的自动备份状态
        scheduled_tasks = pluginConfig["Scheduled_Tasks"]
        scheduled_tasks_status = scheduled_tasks["Status"]
        scheduled_tasks_cron = scheduled_tasks["Cron"]
        cronExpr = scheduled_tasks_cron

        # 解析cron表达式，计算备份间隔（秒）
        # 支持两种格式：
        # 1. 简单间隔格式：*/秒 * * * * * 或 * */分钟 * * * * 或 * * */小时 * * * 等
        # 2. Quartz风格：秒 分 时 日 月 周，使用?表示不指定值
        #    例如：0/10 * * * * ? 表示每10秒执行一次
        #    例如：0 0 0 ? * ? 表示每天0点执行一次
        try:
            parts = cronExpr.split()
            interval = 0  # 初始化为0，强制要求从配置文件中读取

            if len(parts) >= 6:
                # 检查是否是Quartz风格（包含?）
                if '?' in cronExpr:
                    # Quartz风格：解析各个字段
                    # 检查秒字段（第1个字段）
                    if '/' in parts[0]:
                        # 例如：0/10 表示从0秒开始，每10秒执行一次
                        interval = int(parts[0].split('/')[1])
                    # 检查分钟字段（第2个字段）
                    elif '/' in parts[1]:
                        # 例如：0/30 表示从0分钟开始，每30分钟执行一次
                        minutes = int(parts[1].split('/')[1])
                        interval = minutes * 60  # 分钟转秒
                    # 检查小时字段（第3个字段）
                    elif '/' in parts[2]:
                        # 例如：0/1 表示从0小时开始，每小时执行一次
                        hours = int(parts[2].split('/')[1])
                        interval = hours * 3600  # 小时转秒
                    else:
                        # 默认为每天执行一次
                        interval = 86400
                else:
                    # 简单间隔格式
                    # 检查秒字段（第1个字段）
                    if parts[0].startswith('*/'):
                        interval = int(parts[0][2:])
                    # 检查分钟字段（第2个字段）
                    elif parts[1].startswith('*/'):
                        minutes = int(parts[1][2:])
                        interval = minutes * 60  # 分钟转秒
                    # 检查小时字段（第3个字段）
                    elif parts[2].startswith('*/'):
                        hours = int(parts[2][2:])
                        interval = hours * 3600  # 小时转秒
                    # 检查日字段（第4个字段）
                    elif parts[3].startswith('*/'):
                        days = int(parts[3][2:])
                        interval = days * 86400  # 日转秒
                    # 检查月字段（第5个字段）
                    elif parts[4].startswith('*/'):
                        months = int(parts[4][2:])
                        interval = months * 2592000  # 月转秒（按30天计算）
                    else:
                        # 如果没有匹配到任何格式，抛出异常
                        raise ValueError(self.translate("easybackuper.cron.unsupported_format", cronExpr))

            # 检查是否成功解析出间隔
            if interval == 0:
                raise ValueError(self.translate("easybackuper.cron.parse_failed", cronExpr))

            # 将秒转换为tick（20 ticks = 1秒）
            interval_ticks = interval * 20

            # 启动定时任务
            self.backup_task_id = self.server.scheduler.run_task(
                self, 
                self.scheduled_backup_task, 
                delay=interval_ticks, 
                period=interval_ticks
            )

            self.scheduled_backup_enabled = True
            plugin_print(self.translate("easybackuper.backup.started", interval), level="INFO")
            return True

        except Exception as e:
            plugin_print(self.translate("easybackuper.backup.start_failed", str(e)), level="ERROR")
            return False

    def stop_scheduled_backup(self) -> None:
        """
        停止定时备份任务
        :return: None
        """
        if self.backup_task_id is not None:
            # 使用Task对象的cancel方法来取消任务
            self.backup_task_id.cancel()
            self.backup_task_id = None
            self.scheduled_backup_enabled = False
            plugin_print(self.translate("easybackuper.backup.stopped"), level="INFO")

    def scheduled_backup_task(self) -> None:
        """
        定时备份任务
        :return: None
        """
        if Debug_MoreLogs_Cron:
            plugin_print(self.translate("easybackuper.backup.scheduled_task"), level="INFO")

        # 执行备份
        self.backup()

    # NOTE: 自动清理备份文件
    def auto_clean_backups(self) -> None:
        """
        自动清理备份文件
        :return: None
        """
        global use_number_detection_status, use_number_detection_max_number, use_number_detection_mode

        if not use_number_detection_status:
            if Debug_MoreLogs:
                plugin_print(self.translate("easybackuper.auto_clean.disabled"), level="INFO")
            return

        try:
            backup_folder = Path(pluginConfig["BackupFolderPath"])
            if not backup_folder.exists():
                if Debug_MoreLogs:
                    plugin_print(self.translate("easybackuper.backup.folder_not_exist", backup_folder), level="WARNING")
                return

            # 获取所有备份文件（支持多种压缩格式）
            backup_files = []
            # 支持的压缩格式扩展名
            supported_extensions = [".zip", ".7z", ".tar.gz", ".tgz"]
            for ext in supported_extensions:
                for file in backup_folder.glob(f"*{ext}"):
                    backup_files.append((file.stat().st_mtime, file))

            # 按文件名中的日期时间部分进行排序
            backup_files.sort(key=lambda x: x[0])

            # 计算需要删除的文件数量
            files_to_delete = len(backup_files) - use_number_detection_max_number

            if files_to_delete <= 0:
                plugin_print(self.translate("easybackuper.auto_clean.clean"))
                return

            # 根据模式删除文件
            # Mode 0: 开服后清理，删除最旧的文件
            # Mode 1: 备份后清理，删除最旧的文件
            # Mode 2: 两者皆可，删除最旧的文件
            if use_number_detection_mode in [0, 1, 2]:
                # 删除最旧的文件
                deleted_files = []
                for i in range(files_to_delete):
                    file_to_delete = backup_files[i][1]
                    file_to_delete.unlink()
                    deleted_files.append(file_to_delete.name)
                    if Debug_MoreLogs:
                        plugin_print(self.translate("easybackuper.auto_clean.deleted", file_to_delete.name), level="INFO")

                if deleted_files:
                    plugin_print(self.translate("easybackuper.auto_clean.success", ', '.join(deleted_files)), level="INFO")

        except Exception as e:
            plugin_print(self.translate("easybackuper.auto_clean.failed", str(e)), level="ERROR")

    # NOTE: #1备份功能
    def backup(self) -> None:
        """
        备份功能
        :return: None
        """
        # 检查是否正在备份
        if self.is_backing_up:
            plugin_print(self.translate("easybackuper.backup.task_running"), level="WARNING")
            return None

        # 设置备份状态为正在进行
        self.is_backing_up = True

        # 导入全局变量
        global yes_no_console

        # 获取配置文件中Broadcast配置内容
        broadcast = pluginConfig["Broadcast"]
        # 读取"Status"
        broadcast_status = broadcast["Status"]
        # 读取"Time_ms"(延迟时间)
        broadcast_time_ms = broadcast["Time_ms"]
        # 读取"Title"(通知标题)
        broadcast_title = broadcast["Title"]
        # 读取"Message"(通知内容)
        broadcast_message = broadcast["Message"]
        # 读取"Server_Title"(通知标题)
        broadcast_server_title = broadcast["Server_Title"]
        # 读取"Server_Message"(通知内容)
        broadcast_server_message = broadcast["Server_Message"]

        # plugin_print("亻尔女子！")

        # 如果开启广播功能则进行广播
        if broadcast_status:
            self.server.broadcast(
                "§2§l[EasyBackuper]§r§3" + self.translate('easybackuper.broadcast.start'),
                "easybackuper_plugin.command.players",
            )

        # 局部变量
        plugin_print(self.translate("easybackuper.backup.world_path", str(world_folder_path)), level="DEBUG")

        # 延时执行备份
        delay_ticks = int(broadcast_time_ms / 1000 * 20)
        self.server.scheduler.run_task(self, self.backup_2, delay=delay_ticks, period=0)

        return None

    # NOTE: 发送标题消息给在线玩家
    def send_title_to_players(self, title: str, subtitle: str = "") -> None:
        """
        发送标题消息给在线玩家
        :param title: 标题
        :param subtitle: 副标题
        :return: None
        """
        # 获取在线玩家列表
        online_players = self.server.online_players

        # 如果没有玩家在线，则不发送
        if not online_players:
            plugin_print(self.translate('easybackuper.title.no_players'), level="WARNING")
            return

        # 遍历所有在线玩家，发送标题消息
        for player in online_players:
            try:
                player.send_title(title, subtitle)
            except Exception as e:
                if Debug_MoreLogs:
                    plugin_print(self.translate('easybackuper.title.send_failed', player.name, str(e)), level="ERROR")

    # NOTE: 广播备份失败消息
    def broadcast_backup_wrong(self) -> None:
        """
        广播备份失败消息
        :return: None
        """
        # 获取配置文件中Broadcast配置内容
        broadcast = pluginConfig["Broadcast"]
        # 读取"Status"
        broadcast_status = broadcast["Status"]
        # 读取"Backup_wrong_Title"(通知标题)
        broadcast_backup_wrong_title = broadcast["Backup_wrong_Title"]
        # 读取"Backup_wrong_Message"(通知内容)
        broadcast_backup_wrong_message = broadcast["Backup_wrong_Message"]

        if broadcast_status:
            # 发送广播消息
            self.server.broadcast(
                self.translate("easybackuper.broadcast.failed.message"),
                "easybackuper_plugin.command.players",
            )

            plugin_print(self.translate("easybackuper.broadcast.failed"), level="ERROR")

            # 发送标题消息
            self.send_title_to_players(broadcast_backup_wrong_title, broadcast_backup_wrong_message)

    # NOTE: 广播备份成功消息
    def broadcast_backup_success(self, archive_name: str = "", archive_size_mb: str = "0.00", backup_time: str = "") -> None:
        """
        广播备份成功消息
        :param archive_name: 备份文件名
        :param archive_size_mb: 备份文件大小（自动单位）
        :param backup_time: 备份耗时
        :return: None
        """
        # 获取配置文件中Broadcast配置内容
        broadcast = pluginConfig["Broadcast"]
        # 读取"Status"
        broadcast_status = broadcast["Status"]
        # 读取"Backup_success_Title"(通知标题)
        broadcast_backup_success_title = broadcast["Backup_success_Title"]
        # 读取"Backup_success_Message"(通知内容)
        broadcast_backup_success_message = broadcast["Backup_success_Message"]

        if broadcast_status:
            # 发送广播消息
            self.server.broadcast(
                "§2§l[EasyBackuper]§r§6" + self.translate('easybackuper.broadcast.success', archive_name, archive_size_mb, backup_time),
                "easybackuper_plugin.command.players",
            )

            plugin_print(f"\x1b[33m" + self.translate('easybackuper.backup.success', archive_name, archive_size_mb, backup_time), level="SUCCESS")


            # 发送标题消息
            self.send_title_to_players(broadcast_backup_success_title, broadcast_backup_success_message)

    # NOTE: 通知功能
    def notice(self) -> bool:
        """
        通知功能
        :return: True
        """
        # 导入全局变量
        global yes_no_console

        # 获取配置文件中Broadcast配置内容
        broadcast = pluginConfig["Broadcast"]
        # 读取"Status"
        broadcast_status = broadcast["Status"]
        # 读取"Time_ms"(延迟时间/ms)
        broadcast_time_ms = broadcast["Time_ms"]
        # 读取"Title"(通知标题)
        broadcast_title = broadcast["Title"]
        # 读取"Message"(通知内容)
        broadcast_message = broadcast["Message"]
        # 读取"Server_Title"(通知标题)
        broadcast_server_title = broadcast["Server_Title"]
        # 读取"Server_Message"(通知内容)
        broadcast_server_message = broadcast["Server_Message"]

        # self.server.broadcast("你好", "easybackuper_plugin.command.players")
        # self.server.broadcast_subtitle("你好 Again")

        # INFO: 延时执行函数
        # 当 delay=number, period=number(单位Tick) 时，延时后，开始循环执行(多次)
        # 当 delay=0, period=number(单位Tick) 时，立即执行(延时后)，开始循环执行(多次)
        # 当 delay=number, period=0(单位Tick) 时，延时执行(单次)
        self.server.scheduler.run_task(
            self, self.backup, delay=int(broadcast_time_ms / 1000 * 20), period=0
        )

        if yes_no_console == 0:
            # 是玩家
            if broadcast_status:
                # print("通知即将开始!!!")
                self.send_title_to_players(broadcast_title, broadcast_message)
        elif yes_no_console == 1:
            # 是服务端
            # print("通知即将开始!!!")
            self.send_title_to_players(broadcast_server_title, broadcast_server_message)
        return True

    # NOTE: 列出可用备份
    def list_backups(self, sender: CommandSender, limit: int = 10) -> None:
        """
        列出可用的备份文件
        :param sender: 命令发送者
        :param limit: 显示的备份数量限制
        :return: None
        """
        try:
            backup_folder = Path(pluginConfig["BackupFolderPath"])
            if not backup_folder.exists():
                sender.send_message(f"§c[EasyBackuper] §f{self.translate('easybackuper.backup.folder_not_exist', backup_folder)}")
                return

            # 获取所有备份文件（支持多种压缩格式）
            backup_files = []
            # 支持的压缩格式扩展名
            supported_extensions = [".zip", ".7z", ".tar.gz", ".tgz"]
            for ext in supported_extensions:
                for file in backup_folder.glob(f"*{ext}"):
                    backup_files.append((file.stat().st_mtime, file))

            # 按修改时间倒序排序（最新的在前）
            backup_files.sort(key=lambda x: x[0], reverse=True)

            # 限制显示数量
            backup_files = backup_files[:limit]

            if not backup_files:
                sender.send_message(f"§c[EasyBackuper] §f{self.translate('easybackuper.restore.no_backups')}")
                return

            # 发送备份列表
            sender.send_message(f"§a[EasyBackuper] §f{self.translate('easybackuper.restore.list.header')}")
            for i, (mtime, file) in enumerate(backup_files):
                # 格式化文件大小
                file_size = format_file_size(file.stat().st_size)
                # 格式化时间
                time_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                sender.send_message(f"§a[EasyBackuper] §f{self.translate('easybackuper.restore.list.item', i+1, file.name, f'{time_str} ({file_size})')}")
            sender.send_message(f"§a[EasyBackuper] §f{self.translate('easybackuper.restore.list.footer')}")

        except Exception as e:
            sender.send_message(f"§c[EasyBackuper] §f{self.translate('easybackuper.restore.failed', str(e))}")

    # NOTE: 开始回档
    def start_restore(self, sender: CommandSender, restore_index: int) -> None:
        """
        开始回档操作
        :param sender: 命令发送者
        :param restore_index: 备份索引（从1开始）
        :return: None
        """
        plugin_print(self.translate("easybackuper.restore.starting", restore_index), level="INFO")

        # 检查是否正在备份
        if self.is_backing_up:
            plugin_print(self.translate("easybackuper.restore.rejected_backing_up"), level="WARNING")
            sender.send_message(f"§c[EasyBackuper] §f{self.translate('easybackuper.restore.backup_in_progress')}")
            return

        # 检查是否正在回档
        if self.is_restoring:
            plugin_print(self.translate("easybackuper.restore.rejected_restoring"), level="WARNING")
            sender.send_message(f"§c[EasyBackuper] §f{self.translate('easybackuper.restore.restore_in_progress')}")
            return

        try:
            plugin_print(self.translate("easybackuper.restore.processing_request"), level="INFO")

            backup_folder = Path(pluginConfig["BackupFolderPath"])
            if not backup_folder.exists():
                plugin_print(self.translate("easybackuper.backup.folder_not_exist", backup_folder), level="ERROR")
                sender.send_message(f"§c[EasyBackuper] §f{self.translate('easybackuper.backup.folder_not_exist', backup_folder)}")
                return

            # 获取所有备份文件（支持多种压缩格式）
            plugin_print(self.translate("easybackuper.restore.scanning_folder", backup_folder), level="INFO")
            backup_files = []
            # 支持的压缩格式扩展名
            supported_extensions = [".zip", ".7z", ".tar.gz", ".tgz"]
            for ext in supported_extensions:
                for file in backup_folder.glob(f"*{ext}"):
                    backup_files.append((file.stat().st_mtime, file))

            plugin_print(self.translate("easybackuper.restore.found_backups", len(backup_files)), level="INFO")

            # 按修改时间倒序排序（最新的在前）
            backup_files.sort(key=lambda x: x[0], reverse=True)

            # 检查索引是否有效
            if restore_index < 1 or restore_index > len(backup_files):
                plugin_print(self.translate("easybackuper.restore.invalid_index_range", restore_index, len(backup_files)), level="ERROR")
                sender.send_message(f"§c[EasyBackuper] §f{self.translate('easybackuper.restore.invalid_index', restore_index)}")
                return

            # 获取选中的备份文件
            selected_backup = backup_files[restore_index - 1][1]

            # 将备份文件路径转换为绝对路径
            if not selected_backup.is_absolute():
                selected_backup = selected_backup.resolve()

            # 格式化时间
            time_str = datetime.fromtimestamp(selected_backup.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')

            plugin_print(self.translate("easybackuper.restore.selected_backup", selected_backup.name, time_str), level="INFO")
            plugin_print(self.translate("easybackuper.restore.backup_full_path", selected_backup), level="INFO")

            # 记录回档请求
            self.pending_restore_index = restore_index
            plugin_print(self.translate("easybackuper.restore.request_recorded", restore_index), level="INFO")
            sender.send_message(f"§a[EasyBackuper] §f{self.translate('easybackuper.restore.request_recorded_player', selected_backup.name)}")
        except Exception as e:
            sender.send_message(f"§c[EasyBackuper] §f{self.translate('easybackuper.restore.failed', str(e))}")



    # NOTE: 开始运行
    def start(self, sender) -> bool:
        """
        开始运行
        :return: True
        """
        # 导入全局变量
        global yes_no_console

        # self.server.logger.error(sender.name)

        # 判断指令执行者
        # 如果是 Server
        if sender.name == "Server":
            yes_no_console = 1

            self.notice()
            # self.logger.warning(sender.name)
            # plugin_print("notice server")
            return True
        # 如果是 Player
        elif isinstance(sender, Player):
            yes_no_console = 0

            self.notice()
            # self.logger.warning(sender.name)
            # plugin_print("notice player")
            return True
        # 如果不是 Player 也不是 Server
        elif (
            not isinstance(sender.name, Player)
            and sender.name != "Server"
        ):
            self.server.command_sender.send_error_message(
                "This command can only be executed by a player or console!"
            )
            return False

    # TAG: 处理命令
    def on_command(self, sender: CommandSender, command: Command, args: list[str]) -> bool:
        # 导入全局变量
        global pluginConfig, MAX_WORKERS, scheduled_tasks, scheduled_tasks_status, scheduled_tasks_cron, cronExpr
        global auto_cleaup, use_number_detection, use_number_detection_status, use_number_detection_max_number, use_number_detection_mode
        global Debug_MoreLogs, Debug_MoreLogs_Player, Debug_MoreLogs_Cron

        if command.name == "backup":
            # 判断 args参数(数组) 的长度，如果是0，则主命令后面没有参数
            if len(args) == 0:
                # 现在是没有附加参数的情况
                #  backup (我是幽灵附加参数)
                # 此处args长度为0，因为就没有参数在里面

                # self.logger.info("Hello EasyBackuper!")
                # self.logger.warning(plugin_path.name)
                # self.logger.warning(backup_tmp_path.name)
                # self.logger.warning(world_level_name)
                # self.logger.warning(world_folder_path.name)
                # self.logger.warning(sender.name)

                # 默认 /backup 指令后执行的代码
                # 当玩家执行时检测并传参
                self.start(sender)

            # 如果长度是1或以上(这里只考虑整数，因为这里绝不可能会出现负数)，那么则判断其拥有附加参数
            else:
                # 现在是有附加参数的情况
                #  backup [init|reload]
                #       此处为 args[0]
                # 向控制台输出其附加参数(只带1个)
                # TAG: 开始对其附加参数进行判断
                match args[0]:

                    # NOTE: 初始化配置文件
                    case "init":
                        sender.send_message(f"§a[EasyBackuper] §f{self.translate('easybackuper.command.init.initializing')}")
                        plugin_print(self.translate("easybackuper.backup.inited"), level="INFO")

                        # 读取默认的json配置
                        pluginConfig = json.loads(plugin_config_file)
                        
                        # 初始化语言文件
                        self.load_translations()

                        # 初始化配置文件
                        # 写入json配置文件
                        with open(plugin_config_path, "w", encoding="utf-8") as write_f:
                            # 格式化json
                            write_f.write(
                                json.dumps(pluginConfig, indent=4, ensure_ascii=False)
                            )

                        # 重载配置文件
                        # 读取json文件内容
                        with open(plugin_config_path, "r", encoding="utf-8") as load_f:
                            pluginConfig = json.load(load_f)

                        plugin_print(self.translate("easybackuper.backup.reloaded"), level="INFO")
                        sender.send_message(f"§a[EasyBackuper] §f{self.translate('easybackuper.command.init.success')}")

                    # NOTE: 重载配置文件
                    case "reload":
                        # 检查是否正在备份
                        if self.is_backing_up:
                            sender.send_message(f"§c[EasyBackuper] §f{self.translate('easybackuper.backup.reload_rejected')}")
                            plugin_print(self.translate("easybackuper.backup.reload_rejected"), level="WARNING")
                            return True

                        sender.send_message(f"§a[EasyBackuper] §f{self.translate('easybackuper.command.reload.reloading')}")
                        plugin_print(self.translate("easybackuper.backup.reloaded"), level="INFO")

                        # 重载配置文件
                        # 读取json文件内容
                        with open(plugin_config_path, "r", encoding="utf-8") as load_f:
                            pluginConfig = json.load(load_f)
                        
                        # 重载语言文件
                        self.load_translations()

                        # 更新多线程配置
                        MAX_WORKERS = pluginConfig.get("Max_Workers")

                        # 更新Cron相关变量
                        scheduled_tasks = pluginConfig["Scheduled_Tasks"]
                        scheduled_tasks_status = scheduled_tasks["Status"]
                        scheduled_tasks_cron = scheduled_tasks["Cron"]
                        cronExpr = scheduled_tasks_cron

                        # 更新Auto_Clean配置
                        auto_cleaup = pluginConfig["Auto_Clean"]
                        use_number_detection = auto_cleaup["Use_Number_Detection"]
                        use_number_detection_status = use_number_detection["Status"]
                        use_number_detection_max_number = use_number_detection["Max_Number"]
                        use_number_detection_mode = use_number_detection["Mode"]

                        # 更新Debug配置
                        Debug_MoreLogs = pluginConfig["Debug_MoreLogs"]
                        Debug_MoreLogs_Player = pluginConfig["Debug_MoreLogs_Player"]
                        Debug_MoreLogs_Cron = pluginConfig["Debug_MoreLogs_Cron"]

                        sender.send_message(f"§a[EasyBackuper] §f{self.translate('easybackuper.command.reload.success')}")

                        # 如果自动备份已启用，则等待下一个循环周期再备份
                        if pluginConfig["Scheduled_Tasks"]["Status"]:
                            sender.send_message(f"§a[EasyBackuper] §f{self.translate('easybackuper.command.reload.auto_enabled')}")

                    # 启动自动备份
                    case "start":
                        sender.send_message(f"§a[EasyBackuper] §f{self.translate('easybackuper.command.start.starting')}")
                        success = self.start_scheduled_backup()
                        if success:
                            # 更新配置文件中的自动备份状态为true
                            pluginConfig["Scheduled_Tasks"]["Status"] = True
                            # 保存配置文件
                            with open(plugin_config_path, "w", encoding="utf-8") as write_f:
                                write_f.write(json.dumps(pluginConfig, indent=4, ensure_ascii=False))
                            sender.send_message(f"§a[EasyBackuper] §f{self.translate('easybackuper.command.start.success')}")
                        else:
                            sender.send_message(f"§c[EasyBackuper] §f{self.translate('easybackuper.command.start.failed')}")

                    # 停止自动备份
                    case "stop":
                        sender.send_message(f"§a[EasyBackuper] §f{self.translate('easybackuper.command.stop.stopping')}")
                        self.stop_scheduled_backup()
                        # 更新配置文件中的自动备份状态为false
                        pluginConfig["Scheduled_Tasks"]["Status"] = False
                        # 保存配置文件
                        with open(plugin_config_path, "w", encoding="utf-8") as write_f:
                            write_f.write(json.dumps(pluginConfig, indent=4, ensure_ascii=False))
                        sender.send_message(f"§a[EasyBackuper] §f{self.translate('easybackuper.command.stop.success')}")

                    # 查看备份状态
                    case "status":
                        enabled_text = self.translate('easybackuper.command.status.enabled')
                        disabled_text = self.translate('easybackuper.command.status.disabled')
                        status_messages = [
                            f"§a[EasyBackuper] §f{self.translate('easybackuper.command.status.header')}",
                            f"§a[EasyBackuper] §f{self.translate('easybackuper.command.status.auto_backup', f"§a{enabled_text}" if self.scheduled_backup_enabled else f"§c{disabled_text}")}",
                            f"§a[EasyBackuper] §f{self.translate('easybackuper.command.status.auto_clean', f"§a{enabled_text}" if use_number_detection_status else f"§c{disabled_text}")}",
                            f"§a[EasyBackuper] §f{self.translate('easybackuper.command.status.debug_console', f"§a{enabled_text}" if Debug_MoreLogs else f"§c{disabled_text}")}",
                            f"§a[EasyBackuper] §f{self.translate('easybackuper.command.status.debug_player', f"§a{enabled_text}" if Debug_MoreLogs_Player else f"§c{disabled_text}")}",
                            f"§a[EasyBackuper] §f{self.translate('easybackuper.command.status.debug_cron', f"§a{enabled_text}" if Debug_MoreLogs_Cron else f"§c{disabled_text}")}",
                            f"§a[EasyBackuper] §f{self.translate('easybackuper.command.status.separator')}"
                        ]
                        for msg in status_messages:
                            sender.send_message(msg)

                    # 手动执行清理
                    case "clean":
                        sender.send_message(f"§a[EasyBackuper] §f{self.translate('easybackuper.command.clean.cleaning')}")
                        self.auto_clean_backups()
                        sender.send_message(f"§a[EasyBackuper] §f{self.translate('easybackuper.command.clean.success')}")
        elif command.name == "restore":
            # 检查权限
            if not sender.has_permission("easybackuper_plugin.command.only_op"):
                sender.send_message(f"§c[EasyBackuper] §f{self.translate('easybackuper.restore.no_permission')}")
                return True
            
            # 处理 restore 命令
            if len(args) == 0:
                # 显示帮助信息
                # sender.send_message(self.translate("easybackuper.restore.help"))
                if sender.name == "Server":
                    # 控制台帮助信息
                    plugin_print(self.translate("easybackuper.restore.help.console"), level="INFO")
                else:
                    # 玩家帮助信息
                    sender.send_message(f"§a[EasyBackuper] §f{self.translate('easybackuper.restore.help.player')}")
            elif args[0] == "list":
                # 列出备份
                limit = 10
                if len(args) > 1:
                    try:
                        limit = int(args[1])
                    except ValueError:
                        sender.send_message(f"§c[EasyBackuper] §f{self.translate('easybackuper.restore.invalid_argument', args[1])}")
                        return True
                self.list_backups(sender, limit)
            else:
                # 尝试解析索引
                try:
                    restore_index = int(args[0])
                    # 执行回档
                    self.start_restore(sender, restore_index)
                except ValueError:
                    sender.send_message(f"§c[EasyBackuper] §f{self.translate('easybackuper.restore.invalid_index', args[0])}")
            return True
        
        return True
    # TAG: 插件加载后输出 LOGO
    def on_load(self) -> None:
        plugin_print(
            """
===============================================================================================================
     ********                             ******                     **
    /**/////                     **   ** /*////**                   /**             ******
    /**        ******    ****** //** **  /*   /**   ******    ***** /**  ** **   ** /**///**  *****  ******
    /*******  //////**  **////   //***   /******   //////**  **////*/** ** /**  /** /**  /** **///**//**//*
    /**////    ******* //*****    /**    /*//// **  ******* /**  // /****  /**  /** /****** /******* /** /
    /**       **////**  /////**   **     /*    /** **////** /**   **/**/** /**  /** /**///  /**////  /**
    /********//******** ******   **      /******* //********//***** /**//**//****** /**     //******/***
    ////////  //////// //////   //       ///////   ////////  /////  //  //  /////// /*     ////// ///
                            \x1b[33m""" + self.translate('easybackuper.logo.author') + plugin_author[0]
            + """\x1b[0m                        \x1b[1;30;47m""" + self.translate('easybackuper.logo.version')
            + success_plugin_version
            + """[""" + pluginConfig.get("Language") + """]\x1b[0m
==============================================================================================================="""
        )
        plugin_print(
            "\x1b[36m=============================="
            + plugin_name
            + "==============================\x1b[0m"
        )
        plugin_print("\x1b[37;43m" + self.translate('easybackuper.plugin.installed', plugin_name) + "\x1b[0m")
        plugin_print("\x1b[37;43m" + self.translate('easybackuper.plugin.version', success_plugin_version) + "\x1b[0m")
        plugin_print("\x1b[1;35m" + self.translate('easybackuper.plugin.help', plugin_the_help_link) + "\x1b[0m")
        plugin_print("\x1b[31m" + self.translate('easybackuper.plugin.copyright') + "\x1b[0m")
        plugin_print("\x1b[33m" + self.translate('easybackuper.plugin.github', plugin_github_link) + "\x1b[0m")
        plugin_print("\x1b[36m" + self.translate('easybackuper.plugin.description') + "\x1b[0m")
        # 显示功能状态
        if scheduled_tasks_status:
            plugin_print(f"\x1b[32m" + self.translate('easybackuper.plugin.status.auto_backup.enabled', scheduled_tasks_cron) + "\x1b[0m")
        else:
            plugin_print("\x1b[31m" + self.translate('easybackuper.plugin.status.auto_backup.disabled') + "\x1b[0m")

        if use_number_detection_status:
            plugin_print(f"\x1b[32m" + self.translate('easybackuper.plugin.status.auto_clean.enabled', str(use_number_detection_max_number)) + "\x1b[0m")
        else:
            plugin_print("\x1b[31m" + self.translate('easybackuper.plugin.status.auto_clean.disabled') + "\x1b[0m")

        if Debug_MoreLogs:
            plugin_print("\x1b[32m" + self.translate('easybackuper.plugin.status.debug_console.enabled') + "\x1b[0m")
        else:
            plugin_print("\x1b[31m" + self.translate('easybackuper.plugin.status.debug_console.disabled') + "\x1b[0m")

        if Debug_MoreLogs_Player:
            plugin_print("\x1b[32m" + self.translate('easybackuper.plugin.status.debug_player.enabled') + "\x1b[0m")
        else:
            plugin_print("\x1b[31m" + self.translate('easybackuper.plugin.status.debug_player.disabled') + "\x1b[0m")

        if Debug_MoreLogs_Cron:
            plugin_print("\x1b[32m" + self.translate('easybackuper.plugin.status.debug_cron.enabled') + "\x1b[0m")
        else:
            plugin_print("\x1b[31m" + self.translate('easybackuper.plugin.status.debug_cron.disabled') + "\x1b[0m")
        plugin_print(
            "\x1b[36m=============================="
            + plugin_name
            + "==============================\x1b[0m"
        )
        print()

    def on_enable(self) -> None:
        """
        插件启用时调用
        :return: None
        """
        # 初始化语言文件
        # 首先检查插件配置文件夹下的langs文件夹是否存在
        config_lang_dir = plugin_path / "langs"
        
        # 如果不存在，则从源代码目录复制语言文件
        if not config_lang_dir.exists():
            # 创建插件配置文件夹下的langs文件夹
            config_lang_dir.mkdir(parents=True, exist_ok=True)
            
            # 从源代码目录复制语言文件
            source_lang_dir = Path(__file__).parent / "langs"
            if source_lang_dir.exists():
                for lang_file in source_lang_dir.glob("*.json"):
                    shutil.copy2(lang_file, config_lang_dir / lang_file.name)
                    plugin_print(self.translate("easybackuper.lang.copied", lang_file.name), level="INFO")
        
        # 加载语言文件
        self.load_translations()
        
        plugin_print(self.translate("easybackuper.plugin.enabled", plugin_name), level="INFO")

        # 根据Mode 0或Mode 2执行自动清理
        if use_number_detection_status and use_number_detection_mode in [0, 2]:
            plugin_print(self.translate("easybackuper.plugin.start_clean"), level="INFO")
            self.auto_clean_backups()

        # 启动自动备份功能（仅当配置文件中启用时）
        if scheduled_tasks_status:
            self.start_scheduled_backup()

    def on_disable(self) -> None:
        """
        插件禁用时调用
        :return: None
        """
        plugin_print(self.translate("easybackuper.plugin.disabling", plugin_name), level="INFO")

        # 停止自动备份功能
        self.stop_scheduled_backup()

        # 检查是否有待执行的回档操作
        if self.pending_restore_index is not None and not self.is_restoring:
            plugin_print(self.translate("easybackuper.restore.pending_detected", self.pending_restore_index), level="INFO")
            
            # 获取备份文件路径
            backup_folder = Path(pluginConfig["BackupFolderPath"])
            backup_files = []
            # 支持多种压缩格式：.zip, .7z, .tar.gz, .tgz
            for pattern in ["*.zip", "*.7z", "*.tar.gz", "*.tgz"]:
                for file in backup_folder.glob(pattern):
                    backup_files.append((file.stat().st_mtime, file))
            backup_files.sort(key=lambda x: x[0], reverse=True)
            
            # 打印调试信息
            plugin_print(self.translate("easybackuper.restore.total_backups", len(backup_files)), level="DEBUG")
            plugin_print(self.translate("easybackuper.restore.pending_index", self.pending_restore_index), level="DEBUG")

            if self.pending_restore_index > 0 and self.pending_restore_index <= len(backup_files):
                selected_backup = backup_files[self.pending_restore_index - 1][1]
                if not selected_backup.is_absolute():
                    selected_backup = selected_backup.resolve()

                plugin_print(self.translate("easybackuper.restore.backup_file", selected_backup), level="INFO")

                # 启动外部回档程序
                try:
                    # 获取回档配置
                    restore_config = pluginConfig.get("Restore", {})
                    exe_path = restore_config.get("exe_path", "./plugins/EasyBackuper/restore_handler.exe")
                    
                    # 检查外部程序是否存在
                    exe_full_path = Path(exe_path)
                    if not exe_full_path.is_absolute():
                        exe_full_path = Path.cwd() / exe_path
                    
                    if not exe_full_path.exists():
                        plugin_print(self.translate("easybackuper.restore.external_exe_not_exist", exe_full_path), level="ERROR")
                    else:
                        plugin_print(self.translate("easybackuper.restore.preparing_external_exe", exe_full_path), level="INFO")
                        
                        # 构建命令和参数列表
                        cmd_args = [
                            str(exe_full_path),
                            "-backup", str(selected_backup),
                            "-server", str(Path.cwd()),
                            "-world", str(world_level_name)
                        ]

                        plugin_print(self.translate("easybackuper.restore.external_exe_args", ' '.join(cmd_args)), level="DEBUG")
                        # 使用subprocess.Popen启动外部程序，不等待其完成
                        if os.name == 'nt':  # Windows
                            process = subprocess.Popen(
                                cmd_args,
                                universal_newlines=True,
                                close_fds=True  # 改为 True，确保文件描述符正确处理
                            )
                            plugin_print(self.translate("easybackuper.restore.external_exe_pid", process.pid), level="INFO")
                        else:  # Linux/Mac
                            # 使用subprocess.Popen启动进程，并将输出显示在同一个终端中
                            process = subprocess.Popen(
                                cmd_args,
                                stdout=None,
                                stderr=None,
                                universal_newlines=True
                            )
                            plugin_print(self.translate("easybackuper.restore.external_exe_pid", process.pid), level="INFO")
                        plugin_print(self.translate("easybackuper.restore.external_exe_started"), level="INFO")
                except Exception as e:
                    plugin_print(self.translate("easybackuper.restore.external_exe_start_failed", str(e)), level="ERROR")
                    plugin_print(self.translate("easybackuper.restore.error_details", type(e).__name__), level="ERROR")
            else:
                plugin_print(self.translate("easybackuper.restore.invalid_index_range", self.pending_restore_index, len(backup_files)), level="ERROR")
                # 打印所有备份文件列表，方便调试
                if len(backup_files) > 0:
                    plugin_print(self.translate("easybackuper.restore.available_backups_list"), level="DEBUG")
                    for idx, (mtime, file) in enumerate(backup_files, 1):
                        plugin_print(self.translate("easybackuper.restore.backup_list_item", idx, file.name, datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')), level="DEBUG")

        plugin_print(self.translate("easybackuper.plugin.disabled", plugin_name), level="INFO")
        self.server.scheduler.cancel_tasks(self)
