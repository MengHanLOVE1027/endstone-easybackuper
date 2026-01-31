#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EasyBackuper 回档处理程序
"""

# 导入必要的模块
import os, sys, subprocess, traceback, logging, argparse, stat, json, datetime, time
import threading
import shutil
from pathlib import Path

plugin_name = "EasyBackuper"
plugin_name_smallest = plugin_name.lower()

# 设置日志
def setup_logging(log_file=None):
    """配置日志记录"""
    if log_file is None:
        log_dir = Path(restore_info["server_dir"]) / "logs" / plugin_name
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{plugin_name_smallest}_restore_{datetime.datetime.now().strftime('%Y%m%d')}.log"

    # 修正拼写错误: 'asasctime' -> 'asctime'
    log_format = '%(asctime)s - %(levelname)s - %(message)s'

    # 根据global_config["debug"]的值设置日志级别
    log_level = logging.DEBUG if global_config["debug"] else logging.INFO
    
    # 配置根日志记录器
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
        ]
    )

    return logging.getLogger(__name__)

# 全局变量，用于存储配置
global_config = {
    "debug": False
}

# 全局restore_config变量
restore_config = {}

# 全局config变量
config = {}

# 全局logger变量
logger = None

# 自制日志头
def plugin_print(text, level="INFO") -> bool:
    """
    自制 print 日志输出函数
    :param text: 文本内容
    :param level: 日志级别 (DEBUG, INFO, WARNING, ERROR, SUCCESS)
    :return: True
    """
    # 如果是DEBUG级别且未开启DEBUG模式，则不输出
    if level == "DEBUG" and not global_config["debug"]:
        return True
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
    logger_head = f"[\x1b[32mEasyBackuper\x1b[0m] [{level_color}{level}\x1b[0m] "

    # 输出到控制台
    print(logger_head + str(text))

    # 记录到日志文件（如果logger已初始化）
    global logger
    if logger is not None:
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

def copy_file_with_progress(src, dst):
    """
    复制文件并显示进度
    :param src: 源文件路径
    :param dst: 目标文件路径
    """
    try:
        shutil.copy2(src, dst)
        plugin_print(f"复制文件: {src} --> {dst}", level="DEBUG")
        return True
    except Exception as e:
        plugin_print(f"复制文件失败: {src} --> {dst}, 错误: {e}", level="ERROR")

def copy_dir_with_progress(src, dst, max_threads=4):
    """
    多线程复制目录
    :param src: 源目录路径
    :param dst: 目标目录路径
    :param max_threads: 最大线程数
    """
    if not os.path.exists(dst):
        os.makedirs(dst)
        plugin_print(f"创建目录: {dst}", level="DEBUG")
    
    # 收集所有文件和目录
    files_to_copy = []
    dirs_to_create = []
    
    for root, dirs, files in os.walk(src):
        for dir_name in dirs:
            src_dir = Path(root) / dir_name
            rel_dir = src_dir.relative_to(src)
            dst_dir = dst / rel_dir
            dirs_to_create.append((src_dir, dst_dir))
        
        for file_name in files:
            src_file = Path(root) / file_name
            rel_file = src_file.relative_to(src)
            dst_file = dst / rel_file
            files_to_copy.append((src_file, dst_file))
    
    # 先创建目录
    for src_dir, dst_dir in dirs_to_create:
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir)
            plugin_print(f"创建目录: {src_dir} ==> {dst_dir}", level="DEBUG")
    
    # 多线程复制文件
    def copy_files(files):
        for src_file, dst_file in files:
            copy_file_with_progress(src_file, dst_file)
    
    # 将文件分成多个批次
    batch_size = max(1, len(files_to_copy) // max_threads)
    batches = [files_to_copy[i:i + batch_size] for i in range(0, len(files_to_copy), batch_size)]
    
    # 创建并启动线程
    threads = []
    for batch in batches:
        thread = threading.Thread(target=copy_files, args=(batch,))
        thread.start()
        threads.append(thread)
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()

def load_config():
    """加载配置文件"""
    global global_config, restore_config, config
    # 使用服务器目录作为基础路径
    server_dir = Path(restore_info.get("server_dir", "."))
    # 尝试多个可能的配置文件路径
    possible_paths = [
        server_dir / "plugins" / "EasyBackuper" / "config" / "EasyBackuper.json",
        Path.cwd() / "plugins" / "EasyBackuper" / "config" / "EasyBackuper.json",
        Path("./plugins/EasyBackuper/config/EasyBackuper.json")
    ]
    
    config_path = None
    for path in possible_paths:
        plugin_print(f"尝试路径: {path}, 存在: {path.exists()}", level="INFO")
        if path.exists():
            config_path = path
            break
    
    if config_path is None:
        plugin_print("所有可能的配置文件路径都不存在，使用默认配置", level="WARNING")
        return {
            "use_7z": False,
            "exe_7z_path": "./plugins/EasyBackuper/7za.exe"
        }
    
    plugin_print(f"使用配置文件路径: {config_path}", level="INFO")
    default_config = {
        "use_7z": False,
        "exe_7z_path": "./plugins/EasyBackuper/7za.exe"
    }

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            plugin_print(f"配置文件内容: {json.dumps(config, indent=2, ensure_ascii=False)}", level="INFO")
            # 合并默认配置和实际配置
            default_config.update(config)
            # 更新全局配置中的DEBUG设置
            # 尝试从Restore.config.debug读取，如果不存在则从Restore.debug读取
            restore_config = config.get("Restore", {})
            plugin_print(f"Restore配置: {restore_config}", level="INFO")
            # 将config保存到全局变量
            globals()['config'] = config
            # 将restore_config保存到全局变量
            globals()['restore_config'] = restore_config
            restore_config_nested = restore_config.get("config", {})
            plugin_print(f"Restore.config配置: {restore_config_nested}", level="INFO")
            backup_old_world = restore_config_nested.get("backup_old_world_before_restore", False)
            plugin_print(f"读取到的backup_old_world_before_restore值: {backup_old_world}, 类型: {type(backup_old_world)}", level="INFO")
            debug_value = restore_config_nested.get("debug", False)
            plugin_print(f"读取到的debug值: {debug_value}, 类型: {type(debug_value)}", level="INFO")
            global_config["debug"] = debug_value
            
            # 读取Max_Workers参数
            max_workers = config.get("Max_Workers", 4)
            plugin_print(f"读取到的Max_Workers值: {max_workers}, 类型: {type(max_workers)}", level="INFO")
            global_config["max_workers"] = max_workers
            plugin_print(f"成功加载配置文件: {config_path}", level="SUCCESS")
            plugin_print(f"DEBUG模式: {global_config['debug']}", level="INFO")
            return default_config
    except Exception as e:
        plugin_print(f"加载配置文件失败，使用默认配置: {e}", level="WARNING")
        plugin_print(traceback.format_exc(), level="ERROR")
        return default_config

def main():
    """主函数"""
    global logger

    # 先加载配置，以便正确设置日志级别
    config = load_config()
    
    # 设置日志
    logger = setup_logging()
    plugin_print("=" * 60, level="INFO")
    plugin_print("EasyBackuper 回档处理程序启动", level="SUCCESS")
    plugin_print(f"Python版本: {sys.version}", level="INFO")
    plugin_print(f"工作目录: {Path.cwd()}", level="INFO")
    plugin_print(f"参数: {vars(args)}", level="INFO")
    plugin_print("=" * 60, level="INFO")
    plugin_print(f"配置信息: use_7z={config['use_7z']}, exe_7z_path={config['exe_7z_path']}", level="INFO")

    # 从命令行参数构建
    if args.backup_file and args.server_dir and args.world_name:
        plugin_print("从命令行参数构建回档信息", level="INFO")
        plugin_print(f"备份文件: {restore_info['backup_file']}", level="INFO")
        plugin_print(f"服务器目录: {restore_info['server_dir']}", level="INFO")
        plugin_print(f"世界名称: {restore_info['world_name']}", level="INFO")

    os.chdir(restore_info['server_dir'])
    plugin_print(f"切换工作目录到: {restore_info['server_dir']}", level="INFO")
    plugin_print("=" * 60, level="INFO")

    # 检测bedrock_server进程是否在运行（跨平台兼容）
    if os.name == 'nt':  # Windows系统
        process_name = "bedrock_server.exe"
        process_cmd = "tasklist"
        encoding = 'gbk'
    else:  # Linux系统
        process_name = "bedrock_server"
        process_cmd = ["ps", "aux"]
        encoding = 'utf-8'

    # 检测进程
    if isinstance(process_cmd, str):
        process = subprocess.Popen(process_cmd, stdout=subprocess.PIPE)
    else:
        process = subprocess.Popen(process_cmd, stdout=subprocess.PIPE)

    if process_name in process.stdout.read().decode(encoding):
        plugin_print(f"检测到{process_name}进程正在运行，等待服务器关闭", level="WARNING")
        while True:
            if isinstance(process_cmd, str):
                process = subprocess.Popen(process_cmd, stdout=subprocess.PIPE)
            else:
                process = subprocess.Popen(process_cmd, stdout=subprocess.PIPE)

            if process_name not in process.stdout.read().decode(encoding):
                break
            time.sleep(1)
        plugin_print("服务器已关闭", level="SUCCESS")
    else:
        plugin_print(f"未检测到{process_name}进程，继续回档操作", level="INFO")
    plugin_print("=" * 60, level="INFO")

    # 检查是否需要在回档前备份当前世界
    restore_config_nested = restore_config.get("config", {})
    backup_old_world = restore_config_nested.get("backup_old_world_before_restore", False)
    plugin_print(f"回档前备份当前世界配置: {backup_old_world}", level="INFO")
    
    if backup_old_world:
        plugin_print("配置为回档前自动备份当前世界", level="INFO")
        try:
            # 获取当前时间作为备份名称的一部分
            current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"before_restore_{current_time}"
            
            # 获取备份目录
            backup_dir = Path(config.get("BackupFolderPath", "./backup"))
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # 创建临时目录用于压缩
            server_dir = Path(restore_info['server_dir'])
            temp_backup_dir = server_dir / "temp_easybackuper_backup"
            if temp_backup_dir.exists():
                shutil.rmtree(temp_backup_dir, ignore_errors=True)
            temp_backup_dir.mkdir(parents=True, exist_ok=True)
            
            # 复制世界目录到临时目录
            worlds_dir = Path(restore_info['server_dir']) / "worlds"
            plugin_print(f"正在备份当前世界: {worlds_dir}", level="INFO")
            temp_world_backup_dir = temp_backup_dir / restore_info['world_name']
            max_workers = global_config.get("max_workers", 4)
            copy_dir_with_progress(worlds_dir, temp_world_backup_dir, max_threads=max_workers)
            
            # 根据配置选择压缩方式
            old_backup_file_path = backup_dir / f"{backup_name}.7z" if config.get("use_7z", True) else backup_dir / f"{backup_name}.tar.gz"
            
            if config.get("use_7z", True):
                # 使用7za压缩
                exe_7z_path = Path(config.get("exe_7z_path", "./plugins/EasyBackuper/7za.exe"))
                exe_7z_path_full = f".\\{exe_7z_path} a \"{old_backup_file_path}\" \"{temp_world_backup_dir}\\*\" -y"
                
                if not exe_7z_path.exists():
                    plugin_print(f"7za可执行文件不存在: {exe_7z_path}", level="ERROR")
                    shutil.rmtree(temp_backup_dir, ignore_errors=True)
                else:
                    plugin_print(f"使用7za压缩: {temp_world_backup_dir}", level="INFO")
                    plugin_print(f"压缩目标: {temp_world_backup_dir} --> {old_backup_file_path}", level="INFO")
                    plugin_print(f"执行命令: {exe_7z_path_full}", level="INFO")
                    process = subprocess.Popen(exe_7z_path_full, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    stdout, stderr = process.communicate()
                    if process.returncode != 0:
                        plugin_print(f"7za压缩失败: {stderr.decode('gbk')}", level="ERROR")
                        # 清理临时目录
                        shutil.rmtree(temp_backup_dir, ignore_errors=True)
                        return 1
                    else:
                        for line in stdout.decode('gbk').splitlines():
                            plugin_print(line, level="INFO")
                        plugin_print("7za压缩完成", level="SUCCESS")
                        plugin_print(f"备份文件已保存: {old_backup_file_path}", level="SUCCESS")
            else:
                # 使用tar压缩
                plugin_print(f"使用tar压缩: {temp_world_backup_dir}", level="INFO")
                plugin_print(f"压缩目标: {temp_world_backup_dir} --> {old_backup_file_path}", level="INFO")
                result = subprocess.run(['tar', '-czf', str(old_backup_file_path), '-C', str(temp_backup_dir), restore_info['world_name']], capture_output=True, text=True)
                if result.returncode != 0:
                    plugin_print(f"tar压缩失败: {result.stderr}", level="ERROR")
                else:
                    plugin_print("tar压缩完成", level="SUCCESS")
                    plugin_print(f"备份文件已保存: {old_backup_file_path}", level="SUCCESS")
            
            # 清理临时目录
            plugin_print(f"清理临时备份目录: {temp_backup_dir}", level="INFO")
            shutil.rmtree(temp_backup_dir, ignore_errors=True)
            plugin_print("临时备份目录清理完成", level="SUCCESS")
            plugin_print("回档前备份完成", level="SUCCESS")
        except Exception as e:
            plugin_print(f"回档前备份失败: {e}", level="ERROR")
            traceback.print_exc()
    else:
        plugin_print("配置为不备份当前世界", level="INFO")

    plugin_print("=" * 60, level="INFO")
    # 恢复备份
    plugin_print("开始恢复备份", level="INFO")
    worlds_dir = Path(restore_info['server_dir']) / "worlds"
    
    # 创建临时目录用于解压
    server_dir = Path(restore_info['server_dir'])
    temp_dir = server_dir / "temp_easybackuper"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    plugin_print(f"创建临时目录: {temp_dir}", level="INFO")

    # 根据配置选择解压方式
    backup_file_path = Path(restore_info['backup_file'])

    if config['use_7z']:
        # 使用7za解压到临时目录
        exe_7z_path = Path(config['exe_7z_path'])
        temp_world_dir = temp_dir / restore_info['world_name']
        exe_7z_path_full = f".\\{exe_7z_path} x \"{backup_file_path}\" -o\"{temp_world_dir}\" -y"
        if not exe_7z_path.exists():
            plugin_print(f"7za可执行文件不存在: {exe_7z_path}", level="ERROR")
            # 清理临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)
            return 1

        plugin_print(f"使用7za解压: {backup_file_path}", level="INFO")
        plugin_print(f"解压目标: {backup_file_path} --> {temp_world_dir}", level="INFO")
        plugin_print(f"执行命令: {exe_7z_path_full}", level="INFO")
        process = subprocess.Popen(exe_7z_path_full, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            plugin_print(f"7za解压失败: {stderr.decode('gbk')}", level="ERROR")
            # 清理临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)
            return 1
        else:
            for line in stdout.decode('gbk').splitlines():
                plugin_print(line, level="INFO")
            plugin_print("7za解压完成", level="SUCCESS")
            
    else:
        # 使用tar解压到临时目录
        temp_world_dir = temp_dir / restore_info['world_name']
        plugin_print(f"使用tar解压: {backup_file_path}", level="INFO")
        plugin_print(f"解压目标: {backup_file_path} --> {temp_world_dir}", level="INFO")
        # 确保目标目录存在
        temp_world_dir.mkdir(parents=True, exist_ok=True)
        # 使用subprocess.run并正确处理路径
        result = subprocess.run(['tar', '-xzf', str(backup_file_path), '-C', str(temp_world_dir)], capture_output=True, text=True)
        if result.returncode != 0:
            plugin_print(f"tar解压失败: {result.stderr}", level="ERROR")
            # 清理临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)
            return 1
        else:
            plugin_print("tar解压完成", level="SUCCESS")

    plugin_print("=" * 60, level="INFO")
    # 删除现有的世界目录
    current_world_dir = worlds_dir / restore_info['world_name']
    if current_world_dir.exists():
        plugin_print(f"(旧)世界目录已存在: {current_world_dir}", level="WARNING")
        plugin_print("正在删除(旧)世界目录...", level="INFO")
        for root, dirs, files in os.walk(current_world_dir, topdown=False):
            for name in files:
                file_path = Path(root) / name
                os.chmod(file_path, stat.S_IWUSR)
                plugin_print(f"删除文件: {file_path} --> [已删除]", level="DEBUG")
                file_path.unlink()
            for name in dirs:
                dir_path = Path(root) / name
                plugin_print(f"删除目录: {dir_path} --> [已删除]", level="DEBUG")
                dir_path.rmdir()
        plugin_print(f"删除目录: {worlds_dir} --> [已删除]", level="DEBUG")
        plugin_print("(旧)世界目录删除完成", level="SUCCESS")
    
    plugin_print("=" * 60, level="INFO")
    # 使用多线程复制文件从临时目录到目标目录
    plugin_print("开始复制文件...", level="INFO")
    plugin_print(f"复制目标: {temp_world_dir} ==> {worlds_dir}", level="INFO")
    # 使用从配置文件中读取的Max_Workers值
    max_workers = global_config.get("max_workers", 4)
    plugin_print(f"使用 {max_workers} 个线程进行文件复制", level="INFO")

    copy_dir_with_progress(temp_world_dir, worlds_dir, max_threads=max_workers)
    plugin_print("文件复制完成", level="SUCCESS")
    
    plugin_print("=" * 60, level="INFO")
    # 清理临时目录
    plugin_print(f"清理临时目录: {temp_dir}", level="INFO")
    shutil.rmtree(temp_dir, ignore_errors=True)
    plugin_print("临时目录清理完成", level="SUCCESS")

    plugin_print("备份恢复完成", level="SUCCESS")

    plugin_print("=" * 60, level="INFO")
    # 检查是否需要重启服务器
    restart_config = restore_config.get("config", {}).get("restart_server", {})
    restart_status = restart_config.get("status", False)
    plugin_print(f"重启服务器配置: {restart_config}", level="INFO")
    
    if restart_status:
        plugin_print("配置为回档后自动重启服务器", level="INFO")
        # 获取等待时间
        wait_time = restart_config.get("wait_time_s", 10)
        plugin_print(f"等待 {wait_time} 秒后启动服务器...", level="INFO")
        time.sleep(wait_time)
        
        # 获取启动脚本路径
        start_script_path = restart_config.get("start_script_path", "./start.bat")
        plugin_print(f"启动脚本路径: {start_script_path}", level="INFO")
        
        try:
            # 获取服务器目录的绝对路径
            server_dir = Path(restore_info['server_dir']).resolve()
            # 解析启动脚本的绝对路径
            if not Path(start_script_path).is_absolute():
                start_script_full_path = server_dir / start_script_path
            else:
                start_script_full_path = Path(start_script_path)
            
            plugin_print(f"服务器目录: {server_dir}", level="INFO")
            plugin_print(f"启动脚本完整路径: {start_script_full_path}", level="INFO")
            
            # 执行启动脚本
            plugin_print(f"正在启动服务器...", level="INFO")
            if os.name == 'nt':  # Windows系统
                # 使用start命令在新窗口中启动脚本
                subprocess.Popen(['start', str(start_script_full_path)], shell=True, cwd=str(server_dir))
            else:  # Linux/Mac系统
                subprocess.Popen(['bash', str(start_script_full_path)], cwd=str(server_dir))
            plugin_print(f"服务器启动命令已执行", level="SUCCESS")
        except Exception as e:
            plugin_print(f"启动服务器失败: {e}", level="ERROR")
    else:
        plugin_print("配置为不自动重启服务器", level="INFO")

    return 0

if __name__ == "__main__":

    # 解析命令行参数
    parser = argparse.ArgumentParser(description='EasyBackuper 回档处理程序')
    
    # 添加命令行参数
    parser.add_argument('backup_file', nargs='?', help='备份文件路径')
    parser.add_argument('server_dir', nargs='?', help='服务器目录')
    parser.add_argument('world_name', nargs='?', help='世界名称')

    # 解析参数
    args = parser.parse_args()

    # 如果没有提供备份文件路径、服务器目录或世界名称，则退出
    if not args.backup_file or not args.server_dir or not args.world_name:
        parser.print_help()
        print("缺少必要的参数")
        os.system("pause")  # 保持控制台打开（Windows）
        sys.exit(1)

    restore_info = {
        'backup_file': args.backup_file,
        'server_dir': args.server_dir,
        'world_name': args.world_name
    }

    try:
        exit_code = main()
    except SystemExit as e:
        exit_code = e.code
        sys.exit(exit_code)
    except KeyboardInterrupt:
        plugin_print("程序被用户中断", level="WARNING")
        sys.exit(130)
    except Exception as e:
        plugin_print(f"程序发生致命错误: {e}", level="ERROR")
        plugin_print(traceback.format_exc(), level="ERROR")