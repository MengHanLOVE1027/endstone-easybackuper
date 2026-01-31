# 注册命令
from endstone._internal.endstone_python import CommandSender, Command

commands = {
    # 备份主命令
    "test": {
        "description": "test is op",
        "usages": ["/test (add|list|del)[action: BackupAction] (a|b|c)[action: OtherAction]"],
        "permissions": ["easybackuper_plugin.command.only_op"]
    },
    # 备份主命令
    "said": {
        "description": "test is op",
        "usages": ["/said [msg: message]"],
        "permissions": ["easybackuper_plugin.command.only_op"]
    },
    # 备份主命令
    "backup": {
        "description": "test is op",
        "usages": ["/backup"],
        "aliases": ["easybackuper"],
        "permissions": ["easybackuper_plugin.command.only_op"]
    }
}
# 权限组
permissions = {
    # 只有 OP 玩家才可以执行命令
    "easybackuper_plugin.command.only_op": {
        "description": "Only OP Players can use this command",
        "default": "op",
    }
}


# 处理命令
def on_command(self, sender: CommandSender, command: Command, args: list[str]) -> bool:
    if command.name == "backup":
        sender.send_message("Hello EasyBackuper!")
    if command.name == "test":
        # 判断 args参数(数组) 的长度，如果是0，则主命令后面没有参数
        if len(args) == 0:
            # 现在是没有附加参数的情况
            #  test (我是幽灵附加参数)
            # 此处args长度为0，因为就没有参数在里面
            sender.send_message("Hello World!")
        # 如果长度是1或以上(这里只考虑整数，因为这里绝不可能会出现负数)，那么则判断其拥有附加参数
        else:
            # 现在是有附加参数的情况
            #         未套娃        /       套娃后
            #  test [add|list|del] / test <add> [a|b|c]
            #       此处为 args[0]        args[0] args[1]
            # 向控制台输出其附加参数(只带1个)
            sender.server.logger.info(args[0])
            # 开始对其附加参数进行判断
            match args[0]:
                case "add":
                    # 这里判断附加参数后是否还有附加参数(套娃是吧)
                    if len(args) == 2:
                        sender.send_message("套娃思密达")
                        # 开始对附加参数的附加参数进行判断
                        match args[1]:
                            case "a":
                                sender.send_message(args[1])
                            case "b":
                                sender.send_message(args[1])
                            case "c":
                                sender.send_message(args[1])
                    else:
                        sender.send_message("淦！没套娃，艹！")
                case "list":
                    return True
                case "del":
                    return True
    return True
