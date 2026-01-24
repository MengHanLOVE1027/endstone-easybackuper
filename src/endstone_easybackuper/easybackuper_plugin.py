# python 库
import re, os, json, shutil, zipfile, time
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import logging

# endstone 库
from endstone import Player
from endstone.command import Command, CommandSender, CommandSenderWrapper
from endstone.plugin import Plugin

# TAG: 全局常量
plugin_name = "EasyBackuper"
plugin_name_smallest = "easybackuper"
plugin_description = "基于 EndStone 的最最最简单的Python热备份插件 / The simplest Python hot backup plugin based on EndStone."
plugin_version = "0.4.0-beta"
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
    "exe_7z_path": "./plugins/EasyBackuper/7za.exe",
    "use_7z": false,
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
        "Server_Title": "[Server]Neve Gonna Give You UP~",
        "Server_Message": "Never Gonna Let You Down~",
        "Backup_success_Title": "备份完成！",
        "Backup_success_Message": "星级服务，让爱连接",
        "Backup_wrong_Title": "很好的邢级服务，使我备份失败",
        "Backup_wrong_Message": "RT"
    },
    "Debug_MoreLogs": false,
    "Debug_MoreLogs_Player": false,
    "Debug_MoreLogs_Cron": false
}
"""
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

    # NOTE: #2备份功能
    def backup_2(plugin: Plugin) -> None:
        """
        备份功能第二部分
        :return: None
        """
        server = plugin.server

        # 记录备份开始时间
        backup_start_time = time.time()

        try:
            # 备份完成后重置备份状态
            def reset_backup_status():
                plugin.is_backing_up = False

            # 7z相关功能
            use_7z = pluginConfig["use_7z"]
            exe_7z_path = Path(pluginConfig["exe_7z_path"])

            # 暂停存档写入
            assert server.dispatch_command(server.command_sender, "save hold")
            plugin_print("正在暂停存档写入...", level="INFO")

            def save_query():
                messages = []

                # sender = CommandSenderWrapper(server.command_sender, on_message=lambda msg: print(dir(msg)))
                sender = CommandSenderWrapper(
                    server.command_sender,
                    on_message=lambda msg: messages.append(msg.params),
                )

                ready = server.dispatch_command(sender, "save query")
                if not ready:
                    plugin_print("存档未准备好，继续等待...", level="WARNING")
                    assert server.dispatch_command(server.command_sender, "save resume")
                    return

                if Debug_MoreLogs:
                    plugin_print(f"存档查询结果: {messages}", level="DEBUG")

                # 清除tmp文件夹
                if not os.path.exists(backup_tmp_path):
                    os.mkdir(backup_tmp_path)
                else:
                    shutil.rmtree(backup_tmp_path)
                    plugin_print("已清除临时文件夹", level="DEBUG")
                # 复制存档
                plugin_print("正在复制存档文件...", level="INFO")
                
                # 多线程复制单个文件
                def copy_file(src_path, dst_path):
                    """
                    多线程复制单个文件
                    """
                    try:
                        if Debug_MoreLogs:
                            plugin_print(f"正在复制文件: {src_path} -> {dst_path}", level="DEBUG")
                        shutil.copy2(src_path, dst_path)
                        return True
                    except Exception as e:
                        plugin_print(f"复制文件失败 {src_path}: {e}", level="ERROR")
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
                                plugin_print(f"复制文件异常 {src_path}: {e}", level="ERROR")
                
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
                                plugin_print(f"正在复制文件: {src_path} -> {dst_path}", level="DEBUG")
                            shutil.copy2(src_path, dst_path)

                # 创建目标目录
                os.makedirs(backup_tmp_path / world_level_name, exist_ok=True)
                # 开始复制（使用多线程）
                copy_directory_multithread(str(world_folder_path), str(backup_tmp_path / world_level_name))
                assert server.dispatch_command(server.command_sender, "save resume")
                plugin_print("存档写入已恢复", level="INFO")

                if Debug_MoreLogs:
                    plugin_print(f"需要截取的文件列表: {messages[1][0].split(", ")}", level="DEBUG")
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
                                    plugin_print(f"正在截取文件: {file_path}", level="DEBUG")
                                    plugin_print(f"  原始大小: {original_size} 字节", level="DEBUG")
                                    plugin_print(f"  截取位置: {position}", level="DEBUG")
                                    plugin_print(f"  截取后大小: {new_size} 字节", level="DEBUG")
                                    plugin_print(f"  文件大小变化: -{size_difference} 字节", level="WARNING")
                            elif size_difference < 0:
                                if Debug_MoreLogs:
                                    plugin_print(f"正在截取文件: {file_path}", level="DEBUG")
                                    plugin_print(f"  原始大小: {original_size} 字节", level="DEBUG")
                                    plugin_print(f"  截取位置: {position}", level="DEBUG")
                                    plugin_print(f"  截取后大小: {new_size} 字节", level="DEBUG")
                                    plugin_print(f"  文件大小变化: +{abs(size_difference)} 字节", level="WARNING")
                            else:
                                if Debug_MoreLogs:
                                    plugin_print(f"正在截取文件: {file_path}", level="DEBUG")
                                    plugin_print(f"  原始大小: {original_size} 字节", level="DEBUG")
                                    plugin_print(f"  截取后大小: {new_size} 字节", level="DEBUG")
                                    plugin_print(f"  文件大小无变化", level="INFO")

                            return True  # 截取成功

                    except Exception as e:
                        # 如果在截取过程中出现错误，打印错误信息
                        plugin_print(f"截取文件时发生错误: {e}", level="ERROR")
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
                                plugin_print(f"截取文件异常 {file_path}: {e}", level="ERROR")
                
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
                        f"[{world_level_name}]"
                )
                zip_file_new = (
                        pluginConfig["BackupFolderPath"] + "/" + archive_name + ".zip"
                )

                # 是否使用7z来备份
                if use_7z:
                    if os.path.exists(month_rank_dir):
                        plugin_print("正在使用7z压缩备份...", level="INFO")

                        if not os.path.exists(pluginConfig["BackupFolderPath"]):
                            os.mkdir(pluginConfig["BackupFolderPath"])

                        # 压缩后的名字
                        path = str(exe_7z_path) + " a -tzip " + '"' + zip_file_new + '" ' + '"./' + month_rank_dir + '/*"'
                        print(path)
                        result = os.system(path)
                        if result == 0:
                            plugin_print("该目录压缩成功！", level="SUCCESS")
                        else:
                            plugin_print("压缩失败！", level="ERROR")
                            plugin.broadcast_backup_wrong()

                        # 清除tmp文件夹
                        if not os.path.exists(backup_tmp_path):
                            os.mkdir(backup_tmp_path)
                        else:
                            shutil.rmtree(backup_tmp_path)
                    else:
                        plugin_print("您要压缩的目录不存在...", level="ERROR")
                        plugin.broadcast_backup_wrong()
                else:
                    if os.path.exists(month_rank_dir):
                        plugin_print("正在压缩备份...", level="INFO")

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
                                    plugin_print(f"添加文件到压缩包失败 {src_path}: {e}", level="ERROR")
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
                                            plugin_print(f"压缩文件异常: {e}", level="ERROR")
                            
                            plugin_print("该目录压缩成功！", level="SUCCESS")
                        except Exception as e:
                            plugin_print("压缩失败！", level="ERROR")
                            plugin.broadcast_backup_wrong()

                        # 清除tmp文件夹
                        if not os.path.exists(backup_tmp_path):
                            os.mkdir(backup_tmp_path)
                        else:
                            shutil.rmtree(backup_tmp_path)
                    else:
                        plugin_print("您要压缩的目录不存在...", level="ERROR")
                        plugin.broadcast_backup_wrong()

                # 备份成功后广播通知
                # 计算备份文件大小和耗时
                archive_path = Path(zip_file_new)
                backup_end_time = time.time()
                backup_elapsed = backup_end_time - backup_start_time

                # 格式化备份耗时
                if backup_elapsed < 60:
                    backup_time_str = f"{backup_elapsed:.2f}秒"
                elif backup_elapsed < 3600:
                    backup_time_str = f"{backup_elapsed / 60:.2f}分钟"
                else:
                    backup_time_str = f"{backup_elapsed / 3600:.2f}小时"

                if archive_path.exists():
                    archive_size = archive_path.stat().st_size
                    archive_size_mb = f"{archive_size / (1024 * 1024):.2f}"

                    # 根据Mode 1执行自动清理
                    if use_number_detection_mode == 1:
                        plugin.auto_clean_backups()

                    # 广播备份成功消息
                    plugin.broadcast_backup_success(archive_name, archive_size_mb, backup_time_str)
                else:
                    # 根据Mode 1执行自动清理
                    if use_number_detection_mode == 1:
                        plugin.auto_clean_backups()

                    # 广播备份成功消息
                    plugin.broadcast_backup_success(backup_time=backup_time_str)

                # 重置备份状态
                reset_backup_status()

        except Exception as e:
            # 备份失败时重置备份状态
            plugin.logger.error(f"备份过程中发生错误: {e}")
            plugin_print(f"备份过程中发生错误: {e}", level="ERROR")
            reset_backup_status()

        server.scheduler.run_task(plugin, save_query, delay=20, period=0)
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
                        raise ValueError(f"不支持的cron表达式格式: {cronExpr}")

            # 检查是否成功解析出间隔
            if interval == 0:
                raise ValueError(f"无法解析cron表达式: {cronExpr}")

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
            self.logger.info(f"自动备份已启动，间隔: {interval}秒")
            plugin_print(f"自动备份已启动，间隔: {interval}秒")
            return True

        except Exception as e:
            self.logger.error(f"启动自动备份失败: {e}")
            plugin_print(f"启动自动备份失败: {e}")
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
            self.logger.info("自动备份已停止")
            plugin_print("自动备份已停止")

    def scheduled_backup_task(self) -> None:
        """
        定时备份任务
        :return: None
        """
        if Debug_MoreLogs_Cron:
            self.logger.info("执行定时备份任务")
            plugin_print("执行定时备份任务")

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
                self.logger.info("自动清理功能未启用")
                plugin_print("自动清理功能未启用")
            return

        try:
            backup_folder = Path(pluginConfig["BackupFolderPath"])
            if not backup_folder.exists():
                if Debug_MoreLogs:
                    self.logger.warning(f"备份文件夹不存在: {backup_folder}")
                return

            # 获取所有备份文件
            backup_files = []
            for file in backup_folder.glob("*.zip"):
                backup_files.append((file.stat().st_mtime, file))

            # 按文件名中的日期时间部分进行排序
            backup_files.sort(key=lambda x: x[0])

            # 计算需要删除的文件数量
            files_to_delete = len(backup_files) - use_number_detection_max_number

            if files_to_delete <= 0:
                plugin_print("本小姐看了一下，很干净捏~")
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
                        self.logger.info(f"已删除旧备份: {file_to_delete.name}")
                        plugin_print(f"已删除旧备份: {file_to_delete.name}")

                if deleted_files:
                    self.logger.info(f"清理成功，清理了: {', '.join(deleted_files)}")
                    plugin_print(f"清理成功，清理了: {', '.join(deleted_files)}")

        except Exception as e:
            self.logger.error(f"自动清理备份失败: {e}")
            plugin_print(f"自动清理备份失败: {e}")

    # NOTE: #1备份功能
    def backup(self) -> None:
        """
        备份功能
        :return: None
        """
        # 检查是否正在备份
        if self.is_backing_up:
            self.logger.warning("已有备份任务正在进行中，跳过此次备份")
            plugin_print("已有备份任务正在进行中，跳过此次备份")
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
                "§2§l[EasyBackuper]§r§3开始备份力！",
                "easybackuper_plugin.command.players",
            )

        # 局部变量
        plugin_print(world_folder_path)

        # 延时执行备份
        delay_ticks = int(broadcast_time_ms / 1000 * 20)
        self.server.scheduler.run_task(self, self.backup_2, delay=delay_ticks, period=0)

        return None

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
                "§2§l[EasyBackuper]§r§c备份失败！",
                "easybackuper_plugin.command.players",
            )

            plugin_print("§2§l[EasyBackuper]§r§c备份失败！", level="ERROR")

            # 发送标题消息
            try:
                self.server.dispatch_command(
                    self.server.command_sender, 
                    f'/title @a title {broadcast_backup_wrong_title}'
                )
                self.server.dispatch_command(
                    self.server.command_sender,
                    f'/title @a subtitle {broadcast_backup_wrong_message}',
                )
            except Exception as e:
                if Debug_MoreLogs:
                    self.logger.error(f"发送备份失败标题消息失败: {e}")
                    plugin_print(f"发送备份失败标题消息失败: {e}")

    # NOTE: 广播备份成功消息
    def broadcast_backup_success(self, archive_name: str = "", archive_size_mb: str = "0.00", backup_time: str = "") -> None:
        """
        广播备份成功消息
        :param archive_name: 备份文件名
        :param archive_size_mb: 备份文件大小(MB)
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
                f"§2§l[EasyBackuper]§r§6备份成功！§e备份存档：{archive_name} ({archive_size_mb} MB)§a 耗时: {backup_time}",
                "easybackuper_plugin.command.players",
            )

            plugin_print(f"\x1b[33m备份成功！\x1b[93m备份存档：{archive_name} ({archive_size_mb} MB) \x1b[32m耗时: {backup_time}", level="SUCCESS")


            # 发送标题消息
            try:
                self.server.dispatch_command(
                    self.server.command_sender, 
                    f'/title @a title {broadcast_backup_success_title}'
                )
                self.server.dispatch_command(
                    self.server.command_sender,
                    f'/title @a subtitle {broadcast_backup_success_message}',
                )
            except Exception as e:
                if Debug_MoreLogs:
                    self.logger.error(f"发送备份成功标题消息失败: {e}")
                    plugin_print(f"发送备份成功标题消息失败: {e}")

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
                print("通知即将开始!!!")
                self.server.dispatch_command(
                    self.server.command_sender, f'/title @a title {broadcast_title}'
                )
                self.server.dispatch_command(
                    self.server.command_sender,
                    f'/title @a subtitle "{broadcast_message}"',
                )
        elif yes_no_console == 1:
            # 是服务端
            print("通知即将开始!!!")
            self.server.dispatch_command(
                self.server.command_sender, f'/title @a title {broadcast_server_title}'
            )
            self.server.dispatch_command(
                self.server.command_sender,
                f'/title @a subtitle "{broadcast_server_message}"',
            )
        return True

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
                        sender.send_message(f"§a[EasyBackuper] §f正在初始化配置文件...")
                        self.logger.info("inited.")

                        # 读取默认的json配置
                        pluginConfig = json.loads(plugin_config_file)

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

                        self.logger.info("reloaded.")
                        sender.send_message(f"§a[EasyBackuper] §f配置文件初始化完成！")

                    # NOTE: 重载配置文件
                    case "reload":
                        # 检查是否正在备份
                        if self.is_backing_up:
                            sender.send_message(f"§c[EasyBackuper] §f正在备份中，请等待备份完成后再重载配置文件！")
                            self.logger.warning("正在备份中，拒绝重载配置文件")
                            return True

                        sender.send_message(f"§a[EasyBackuper] §f正在重载配置文件...")
                        self.logger.info("reloaded.")

                        # 重载配置文件
                        # 读取json文件内容
                        with open(plugin_config_path, "r", encoding="utf-8") as load_f:
                            pluginConfig = json.load(load_f)

                            # 更新多线程配置
                            MAX_WORKERS = pluginConfig.get("Max_Workers", 4)

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

                        sender.send_message(f"§a[EasyBackuper] §f配置文件重载完成！")

                        # 如果自动备份已启用，则等待下一个循环周期再备份
                        if pluginConfig["Scheduled_Tasks"]["Status"]:
                            sender.send_message(f"§a[EasyBackuper] §f自动备份已启用，将在下一个循环周期执行备份")

                    # 启动自动备份
                    case "start":
                        sender.send_message(f"§a[EasyBackuper] §f正在启动自动备份...")
                        success = self.start_scheduled_backup()
                        if success:
                            # 更新配置文件中的自动备份状态为true
                            pluginConfig["Scheduled_Tasks"]["Status"] = True
                            # 保存配置文件
                            with open(plugin_config_path, "w", encoding="utf-8") as write_f:
                                write_f.write(json.dumps(pluginConfig, indent=4, ensure_ascii=False))
                            sender.send_message(f"§a[EasyBackuper] §f自动备份已启动！")
                        else:
                            sender.send_message(f"§c[EasyBackuper] §f自动备份启动失败，请检查配置文件！")

                    # 停止自动备份
                    case "stop":
                        sender.send_message(f"§a[EasyBackuper] §f正在停止自动备份...")
                        self.stop_scheduled_backup()
                        # 更新配置文件中的自动备份状态为false
                        pluginConfig["Scheduled_Tasks"]["Status"] = False
                        # 保存配置文件
                        with open(plugin_config_path, "w", encoding="utf-8") as write_f:
                            write_f.write(json.dumps(pluginConfig, indent=4, ensure_ascii=False))
                        sender.send_message(f"§a[EasyBackuper] §f自动备份已停止！")

                    # 查看备份状态
                    case "status":
                        status_messages = [
                            f"§a[EasyBackuper] §f===== 备份状态 =====",
                            f"§a[EasyBackuper] §f自动备份状态: {'§a已启用' if self.scheduled_backup_enabled else '§c未启用'}",
                            f"§a[EasyBackuper] §f自动清理状态: {'§a已启用' if use_number_detection_status else '§c未启用'}",
                            f"§a[EasyBackuper] §fDebug日志(控制台): {'§a已启用' if Debug_MoreLogs else '§c未启用'}",
                            f"§a[EasyBackuper] §fDebug日志(玩家): {'§a已启用' if Debug_MoreLogs_Player else '§c未启用'}",
                            f"§a[EasyBackuper] §fDebug日志(Cron): {'§a已启用' if Debug_MoreLogs_Cron else '§c未启用'}",
                            f"§a[EasyBackuper] §f===================="
                        ]
                        for msg in status_messages:
                            sender.send_message(msg)

                    # 手动执行清理
                    case "clean":
                        sender.send_message(f"§a[EasyBackuper] §f正在执行清理...")
                        self.auto_clean_backups()
                        sender.send_message(f"§a[EasyBackuper] §f清理完成！")
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
                            \x1b[33m作者："""
            + plugin_author[0]
            + """\x1b[0m                        \x1b[1;30;47m版本："""
            + success_plugin_version
            + """[zh_CN]\x1b[0m
==============================================================================================================="""
        )
        plugin_print(
            "\x1b[36m=============================="
            + plugin_name
            + "==============================\x1b[0m"
        )
        plugin_print("\x1b[37;43m" + plugin_name + " 安装成功！\x1b[0m")
        plugin_print("\x1b[37;43m版本: " + success_plugin_version + "\x1b[0m")
        plugin_print("\x1b[1;35m查看帮助：" + plugin_the_help_link + "\x1b[0m")
        plugin_print("\x1b[31m" + plugin_copyright + "\x1b[0m")
        plugin_print("\x1b[33mGitHub 仓库：" + plugin_github_link + "\x1b[0m")
        plugin_print("\x1b[36m" + plugin_description + "\x1b[0m  \x1b[33m作者：" + plugin_author[0] + "\x1b[0m")
        # 显示功能状态
        if scheduled_tasks_status:
            plugin_print(f"\x1b[32m自动备份状态：已启用 (间隔: {scheduled_tasks_cron})\x1b[0m")
        else:
            plugin_print("\x1b[31m自动备份状态：未启用\x1b[0m")

        if use_number_detection_status:
            plugin_print(f"\x1b[32m自动清理状态：已启用 (最大保留: {use_number_detection_max_number} 个)\x1b[0m")
        else:
            plugin_print("\x1b[31m自动清理状态：未启用\x1b[0m")

        if Debug_MoreLogs:
            plugin_print("\x1b[32mDebug更多日志状态(控制台)：已启用\x1b[0m")
        else:
            plugin_print("\x1b[31mDebug更多日志状态(控制台)：未启用\x1b[0m")

        if Debug_MoreLogs_Player:
            plugin_print("\x1b[32mDebug更多日志状态(玩家)：已启用\x1b[0m")
        else:
            plugin_print("\x1b[31mDebug更多日志状态(玩家)：未启用\x1b[0m")

        if Debug_MoreLogs_Cron:
            plugin_print("\x1b[32mDebug更多日志状态(Cron)：已启用\x1b[0m")
        else:
            plugin_print("\x1b[31mDebug更多日志状态(Cron)：未启用\x1b[0m")
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
        self.logger.info(f"{plugin_name} 插件已启用！")

        # 根据Mode 0或Mode 2执行自动清理
        if use_number_detection_status and use_number_detection_mode in [0, 2]:
            self.logger.info("正在执行开服清理...")
            self.auto_clean_backups()

        # 启动自动备份功能（仅当配置文件中启用时）
        if scheduled_tasks_status:
            self.start_scheduled_backup()

    def on_disable(self) -> None:
        """
        插件禁用时调用
        :return: None
        """
        self.logger.info(f"{plugin_name} 插件即将禁用...")

        # 停止自动备份功能
        self.stop_scheduled_backup()

        self.logger.info(f"{plugin_name} 插件已禁用！")
        self.server.scheduler.cancel_tasks(self)
