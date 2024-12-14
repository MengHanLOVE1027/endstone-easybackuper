# python 库
import re, os, json, shutil, zipfile
from pathlib import Path

# endstone 库
from endstone import ColorFormat, Player
from endstone.command import Command, CommandSender, CommandSenderWrapper
from endstone.plugin import Plugin

# TAG: 全局常量
plugin_name = "EasyBackuper"
plugin_name_smallest = "easybackuper"
plugin_description = "基于 LeviLamina - LSE引擎 的 最最最简单的JS热备份插件 / The simplest Python hot backup plugin based on EndStone."
plugin_version = "0.3.0"
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


# NOTE: 自制日志头
def plugin_print(text) -> bool:
    """
    自制 print 日志输出函数
    :param text: 文本内容
    :return: True
    """
    # 自制Logger消息头
    logger_head = "[\x1b[32m" + plugin_name + "\x1b[0m] "
    print(logger_head + str(text))
    return True


# TAG: 默认配置文件
plugin_config_file = """
{
    "exe_7z_path": "./plugins/EasyBackuper/7za.exe",
    "BackupFolderPath": "./backup",
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
        "Backup_Time_ms": 5000,
        "Title": "[OP]要开始备份啦~",
        "SubTitle": "将于 5秒 后进行备份！",
        "Server_Title": "[Server]Neve Gonna Give You UP~",
        "Server_SubTitle": "Never Gonna Let You Down~",
        "Backup_success_Title": "备份完成！",
        "Backup_success_SubTitle": "星级服务，让爱连接",
        "Backup_wrong_Title": "很好的邢级服务，使我备份失败",
        "Backup_wrong_SubTitle": "RT"
    },
    "Debug_MoreLogs": false,
    "Debug_MoreLogs_Player": false,
    "Debug_MoreLogs_Cron": false
}
"""
# 检查插件文件路径，以防后续出问题
if not plugin_path.exists():
    print(f"文件夹 '{plugin_path.resolve()}' 不存在。")
    os.makedirs(plugin_path, exist_ok=True)  # 使用 makedirs 可以创建多级目录
else:
    print(f"文件夹 '{plugin_path.resolve()}' 存在。")

# 现在可以确保插件文件路径正常，接下来检查配置文件路径
if plugin_config_path.exists():
    print(f"文件 '{plugin_config_path.resolve()}' 存在。")
    # 读取json文件内容
    with open(plugin_config_path, "r", encoding="utf-8") as load_f:
        pluginConfig = json.load(load_f)
else:
    print(f"文件 '{plugin_config_path.resolve()}' 不存在。")
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

my_beautiful_text = f"This is {ColorFormat.YELLOW}yellow, {ColorFormat.AQUA}aqua and {ColorFormat.GOLD}gold{ColorFormat.RESET}."


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

    # def on_message(self, message):
    #     msg = []
    #     print(f"命令输出: {message}")
    #     print(dir(message))
    #     msg.append(message.with_)
    #     print(msg)

    # def on_error(self, error):
    #     print(f"发生错误: {error}")

    # NOTE: 注册命令
    commands = {
        # 备份主命令
        "backup": {
            "description": "test is op",
            "usages": ["/backup (init|refresh)[action: OtherAction]"],
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

    # NOTE: #2备份功能
    def backup_2(plugin: Plugin) -> None:
        """
        备份功能第二部分
        :return: None
        """
        server = plugin.server

        # 暂停存档写入
        assert server.dispatch_command(server.command_sender, "save hold")
        plugin_print("拷贝中...")

        def save_query():
            messages = []

            # sender = CommandSenderWrapper(server.command_sender, on_message=lambda msg: print(dir(msg)))
            sender = CommandSenderWrapper(
                server.command_sender,
                on_message=lambda msg: messages.append(msg.params),
            )

            ready = server.dispatch_command(sender, "save query")
            if not ready:
                print("Not ready!")
                assert server.dispatch_command(server.command_sender, "save resume")
                return

            print(messages)

            # 清除tmp文件夹
            if not os.path.exists(backup_tmp_path):
                os.mkdir(backup_tmp_path)
            else:
                shutil.rmtree(backup_tmp_path)
            # 复制存档
            shutil.copytree(world_folder_path, backup_tmp_path / world_level_name)
            server.dispatch_command(server.command_sender, "save resume")

            print(messages[1][0].split(", "))
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
                            print(real_file_name, position)
                            print(f"原始文件大小: {original_size} 字节")
                            print(f"移动到位置: {position}")
                            print(f"文件已被截取到位置: {position}")
                            print(f"截取后的文件大小: {new_size} 字节")
                            server.logger.warning(
                                f"文件大小减少了: {size_difference} 字节"
                            )
                        elif size_difference < 0:
                            print(real_file_name, position)
                            print(f"原始文件大小: {original_size} 字节")
                            print(f"移动到位置: {position}")
                            print(f"文件已被截取到位置: {position}")
                            print(f"截取后的文件大小: {new_size} 字节")
                            server.logger.warning(
                                f"文件大小减少了: {size_difference} 字节"
                            )
                        # else:
                        #     print(f"文件大小减少了: {size_difference} 字节")

                        return True  # 截取成功

                except Exception as e:
                    # 如果在截取过程中出现错误，打印错误信息
                    print(f"截取文件时发生错误: {e}")
                    return False  # 截取失败

            for path in file_paths:
                file_name, position = path.split(":")
                position = int(position)
                # print(file_name, position)
                real_file_name = backup_tmp_path / file_name
                # print(real_file_name, position)
                truncate_file(real_file_name, position)

            # 压缩存档
            month_rank_dir = str(backup_tmp_path)
            zip_file_new = (
                pluginConfig["BackupFolderPath"] + "/" + month_rank_dir + ".zip"
            )
            if os.path.exists(month_rank_dir):
                print("正在为您压缩...")

                if not os.path.exists(pluginConfig["BackupFolderPath"]):
                    os.mkdir(pluginConfig["BackupFolderPath"])

                # 压缩后的名字
                zip = zipfile.ZipFile(zip_file_new, "w", zipfile.ZIP_DEFLATED)
                for dir_path, dir_names, file_names in os.walk(month_rank_dir):
                    # 去掉目标跟路径，只对目标文件夹下面的文件及文件夹进行压缩
                    fpath = dir_path.replace(month_rank_dir, "")
                    for filename in file_names:
                        zip.write(
                            os.path.join(dir_path, filename),
                            os.path.join(fpath, filename),
                        )
                zip.close()
                print("该目录压缩成功！")

                # 清除tmp文件夹
                if not os.path.exists(backup_tmp_path):
                    os.mkdir(backup_tmp_path)
                else:
                    shutil.rmtree(backup_tmp_path)
            else:
                print("您要压缩的目录不存在...")

        server.scheduler.run_task(plugin, save_query, delay=20, period=0)
        return None

    # NOTE: #1备份功能
    def backup(self) -> None:
        """
        备份功能
        :return: None
        """
        # 导入全局变量
        global yes_no_console

        # 获取配置文件中Broadcast配置内容
        broadcast = pluginConfig["Broadcast"]
        # 读取"Status"
        broadcast_status = broadcast["Status"]
        # 读取"Backup_success_Title"(通知标题)
        broadcast_backup_success_title = broadcast["Backup_success_Title"]
        # 读取"Backup_success_SubTitle"(通知内容)
        broadcast_backup_success_sub_title = broadcast["Backup_success_SubTitle"]
        # 读取"Backup_wrong_Title"(通知标题)
        broadcast_backup_wrong_title = broadcast["Backup_wrong_Title"]
        # 读取"Backup_wrong_SubTitle"(通知内容)
        broadcast_backup_wrong_sub_title = broadcast["Backup_wrong_SubTitle"]
        plugin_print("亻尔女子！")

        # 如果开启广播功能则进行广播
        if broadcast_status:
            self.server.broadcast(
                "§2§l[EasyBackuper]§r§3开始备份力！",
                "easybackuper_plugin.command.players",
            )

        # 局部变量
        plugin_print(world_folder_path)

        # FIXME: 继续移植
        # if yes_no_console == 0:
        #     self.server.command_sender

        # 备份的第二部分内容
        # 延时一段时间后再执行，以免不生效
        self.server.scheduler.run_task(self, self.backup_2, delay=20, period=0)

        return None

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
        # 读取"Time"(延迟时间/ms)
        broadcast_backup_time_ms = broadcast["Backup_Time_ms"]
        # 读取"Title"(通知标题)
        broadcast_title = broadcast["Title"]
        # 读取"SubTitle"(通知内容)
        broadcast_subtitle = broadcast["SubTitle"]
        # 读取"Title"(通知标题)
        broadcast_server_title = broadcast["Server_Title"]
        # 读取"SubTitle"(通知内容)
        broadcast_server_subtitle = broadcast["Server_SubTitle"]

        # self.server.broadcast("你好", "easybackuper_plugin.command.players")
        # self.server.broadcast_subtitle("你好 Again")

        # INFO: 延时执行函数
        # 当 delay=number, period=number(单位Tick) 时，延时后，开始循环执行(多次)
        # 当 delay=0, period=number(单位Tick) 时，立即执行(延时后)，开始循环执行(多次)
        # 当 delay=number, period=0(单位Tick) 时，延时执行(单次)
        self.server.scheduler.run_task(
            self, self.backup, delay=int(broadcast_backup_time_ms / 1000 * 20), period=0
        )

        if yes_no_console == 0:
            # 是玩家
            if broadcast_status:
                print()
                # Notice_Upper(broadcast_title, broadcast_subtitle)
                self.server.dispatch_command(
                    self.server.command_sender, f"/title @a title {broadcast_title}"
                )
                self.server.dispatch_command(
                    self.server.command_sender,
                    f"/title @a subtitle {broadcast_subtitle}",
                )
        elif yes_no_console == 1:
            # 是服务端
            print()
            # Notice_Upper(broadcast_server_title, broadcast_server_message)
            self.server.dispatch_command(
                self.server.command_sender, f"/title @a title {broadcast_server_title}"
            )
            self.server.dispatch_command(
                self.server.command_sender,
                f"/title @a subtitle {broadcast_server_subtitle}",
            )
        return True

    # NOTE: 开始运行
    def start(self) -> bool:
        """
        开始运行
        :return: True
        """
        # 导入全局变量
        global yes_no_console

        # 判断指令执行者
        # 如果是 Server
        if self.server.command_sender.name == "Server":
            yes_no_console = 1

            self.notice()
            plugin_print("notice server")

            # sender.send_message(sender.name)
            # sender.send_message("I'm here.")
            # sender.send_message(my_beautiful_text)
            return True
        # 如果是 Player
        elif isinstance(self.server.command_sender.name, Player):
            yes_no_console = 0

            self.notice()
            plugin_print("notice player")
            # sender.send_message(sender.name)
            # sender.send_message("I'm here.")
            # sender.send_message(my_beautiful_text)
            return True
        # 如果不是 Player 也不是 Server
        elif (
            not isinstance(self.server.command_sender.name, Player)
            and self.server.command_sender.name != "Server"
        ):
            self.server.command_sender.send_error_message(
                "This command can only be executed by a player or console!"
            )
            self.server.command_sender.send_message(my_beautiful_text)
            return False

    # TAG: 处理命令
    def on_command(
        self, sender: CommandSender, command: Command, args: list[str]
    ) -> bool:
        # 导入全局变量
        global pluginConfig

        if command.name == "backup":
            # 判断 args参数(数组) 的长度，如果是0，则主命令后面没有参数
            if len(args) == 0:
                # 现在是没有附加参数的情况
                #  backup (我是幽灵附加参数)
                # 此处args长度为0，因为就没有参数在里面
                self.logger.info("Hello EasyBackuper!")
                self.logger.warning(plugin_path.name)
                self.logger.warning(backup_tmp_path.name)
                self.logger.warning(world_level_name)
                self.logger.warning(world_folder_path.name)
                self.logger.warning(sender.name)

                # 默认 /backup 指令后执行的代码
                # 当玩家执行时检测并传参
                self.start()

            # 如果长度是1或以上(这里只考虑整数，因为这里绝不可能会出现负数)，那么则判断其拥有附加参数
            else:
                # 现在是有附加参数的情况
                #  backup [init|refresh]
                #       此处为 args[0]
                # 向控制台输出其附加参数(只带1个)
                # TAG: 开始对其附加参数进行判断
                match args[0]:

                    # TODO: 初始化配置文件
                    case "init":

                        self.logger.info("Hello EasyBackuper!")
                        self.logger.warning(plugin_path.name)
                        self.logger.warning(backup_tmp_path.name)
                        self.logger.warning(world_level_name)
                        self.logger.warning(world_folder_path.name)
                        self.logger.warning(sender.name)

                        # 读取默认的json配置
                        pluginConfig = json.loads(plugin_config_file)

                        # 初始化配置文件
                        # 写入json配置文件
                        with open(plugin_config_path, "w", encoding="utf-8") as write_f:
                            # 格式化json
                            write_f.write(
                                json.dumps(pluginConfig, indent=4, ensure_ascii=False)
                            )

                    # TODO: 重载配置文件
                    case "refresh":
                        self.logger.info("Hello EasyBackuper!")
                        self.logger.warning(plugin_path.name)
                        self.logger.warning(backup_tmp_path.name)
                        self.logger.warning(world_level_name)
                        self.logger.warning(world_folder_path.name)
                        self.logger.warning(sender.name)

                        # 重载配置文件
                        # 读取json文件内容
                        with open(plugin_config_path, "r", encoding="utf-8") as load_f:
                            pluginConfig = json.load(load_f)
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
        plugin_print(
            "\x1b[36m"
            + plugin_description
            + "\x1b[0m  \x1b[33m作者："
            + plugin_author[0]
            + "\x1b[0m"
        )
        plugin_print("自动备份状态：开发中...")
        plugin_print("自动清理状态：开发中...")
        plugin_print("Debug更多日志状态(控制台)：开发中...")
        plugin_print("Debug更多日志状态(玩家)：开发中...")
        plugin_print("Debug更多日志状态(Cron)：开发中...")
        plugin_print(
            "\x1b[36m=============================="
            + plugin_name
            + "==============================\x1b[0m"
        )
        print()

    # def on_enable(self) -> None:
    #     self.logger.info("on_enable is called!")
    #
    def on_disable(self) -> None:
        self.logger.info("on_disable is called!")
        self.server.scheduler.cancel_tasks(self)
