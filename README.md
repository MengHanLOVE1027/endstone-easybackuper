# endstone-easybackuper

基于 EndStone 的最最最简单的Python热备份插件 / The simplest Python hot backup plugin based on EndStone.

## 功能特性

- 🔄 自动备份：支持基于cron表达式的定时自动备份服务器存档
- 🧹 自动清理：自动清理旧备份，节省磁盘空间
- 📢 广播通知：备份前和备份完成后向玩家发送通知，包含详细备份统计
- 🎨 自定义配置：丰富的配置选项，满足不同需求
- 🔧 多种命令：提供多种命令控制备份功能
- 📊 状态查看：随时查看备份插件运行状态
- 📝 日志系统：完整的日志记录系统，支持多级别彩色输出，按日期分割存储
- ⚡ 多线程备份：支持多线程文件复制与压缩，通过线程锁确保线程安全
- 🗜️ 7z压缩：支持通过7za.exe进行高效压缩
- 🌍 国际化支持：支持多语言界面，轻松切换不同语言
- 📏 智能单位显示：备份文件大小自动选择合适单位显示（B/KB/MB/GB）

## 安装方法

1. 将插件文件放入服务器的 `plugins` 文件夹
2. 重启服务器或加载插件
3. 插件会自动创建配置文件

## 命令说明

- `/backup` - 立即执行备份
- `/backup init` - 初始化配置文件
- `/backup reload` - 重载配置文件
- `/backup start` - 启动自动备份
- `/backup stop` - 停止自动备份
- `/backup status` - 查看备份状态
- `/backup clean` - 手动执行清理

## 配置文件说明

配置文件位于 `plugins/EasyBackuper/config/EasyBackuper.json`

主要配置项：

```json
{
    "Language": "zh_CN",             // 语言设置 (支持: zh_CN, en_US等)
    "exe_7z_path": "./plugins/EasyBackuper/7za.exe",  // 7z可执行文件路径
    "use_7z": false,                // 是否使用7z压缩(需要先下载7za.exe)
    "BackupFolderPath": "./backup",    // 备份文件保存路径
    "Max_Workers": 4,               // 最大线程数(文件复制和压缩)
    "Auto_Clean": {                 // 自动清理配置
        "Use_Number_Detection": {
            "Status": false,         // 是否启用自动清理
            "Max_Number": 5,         // 最大保留备份数量
            "Mode": 0                // 清理模式: 0=开服后清理, 1=备份后清理, 2=开服时清理
        }
    },
    "Scheduled_Tasks": {              // 定时任务配置
        "Status": false,              // 是否启用定时备份
        "Cron": "*/30 * * * * *"     // Cron表达式，支持多种格式
    },
    "Broadcast": {                    // 广播配置
        "Status": true,               // 是否启用广播
        "Time_ms": 5000,             // 备份前通知时间(毫秒)
        "Title": "\\[OP\\]要开始备份啦~",   // 备份前标题
        "Message": "将于 5秒 后进行备份！", // 备份前消息
        "Server_Title": "\\[Server\\]Never Gonna Give You UP~", // 服务器备份前标题
        "Server_Message": "Never Gonna Let You Down~", // 服务器备份前消息
        "Backup_success_Title": "备份完成！", // 备份成功标题
        "Backup_success_Message": "星级服务，让爱连接", // 备份成功消息
        "Backup_wrong_Title": "很好的邢级服务，使我备份失败", // 备份失败标题
        "Backup_wrong_Message": "RT" // 备份失败消息
    },
    "Debug_MoreLogs": false,          // 控制台详细日志
    "Debug_MoreLogs_Player": false,   // 玩家详细日志
    "Debug_MoreLogs_Cron": false      // Cron详细日志
}
```

### Cron表达式说明

插件支持多种Cron表达式格式：

1. 简单间隔格式：
   - `*/30 * * * * *` - 每30秒执行一次
   - `* */30 * * * *` - 每30分钟执行一次
   - `* * */1 * * *` - 每小时执行一次

2. Quartz风格（使用?表示不指定值）：
   - `0/10 * * * * ?` - 每10秒执行一次
   - `0 0 0 ? * ?` - 每天0点执行一次
   - `0 0 */2 ? * ?` - 每2小时执行一次

## 使用示例

1. 启用自动备份，每30分钟备份一次：
   - 在配置文件中设置 `"Scheduled_Tasks.Status": true`
   - 设置 `"Scheduled_Tasks.Cron": "* */30 * * * *"`
   - 执行 `/backup reload` 重载配置
   - 执行 `/backup start` 启动自动备份

2. 启用自动清理，保留最新5个备份：
   - 在配置文件中设置 `"Auto_Clean.Use_Number_Detection.Status": true`
   - 设置 `"Auto_Clean.Use_Number_Detection.Max_Number": 5`
   - 设置 `"Auto_Clean.Use_Number_Detection.Mode": 1` (备份后清理)
   - 执行 `/backup reload` 重载配置

3. 启用7z压缩以获得更好的压缩效率：
   - 下载7za.exe并放置在 `plugins/EasyBackuper/` 目录下
   - 在配置文件中设置 `"use_7z": true`
   - 确认 `"exe_7z_path"` 指向正确的7za.exe路径
   - 执行 `/backup reload` 重载配置

4. 设置每天凌晨3点自动备份：
   - 在配置文件中设置 `"Scheduled_Tasks.Cron": "0 0 3 ? * *"`
   - 执行 `/backup reload` 重载配置
   - 执行 `/backup start` 启动自动备份

## 常见问题

**Q: 备份文件保存在哪里？**
A: 默认保存在服务器根目录的 `backup` 文件夹中，可在配置文件中修改。

**Q: 如何查看备份是否成功？**
A: 执行 `/backup status` 命令查看备份状态，备份成功后会有广播通知，并显示备份文件大小和耗时。

**Q: 自动备份会影响服务器性能吗？**
A: 备份过程中会暂停存档写入，建议在服务器负载较低时进行自动备份。多线程备份可以提高备份速度，但也会占用更多系统资源。

**Q: 如何设置最大线程数？**
A: 在配置文件中修改 `Max_Workers` 值。建议设置：
   - CPU核心数较少的服务器: 2-4
   - 多核CPU服务器: 4-8
   - 高性能服务器: 8-16

   线程数越高，备份速度越快，但也会占用更多系统资源。（不代表压缩快）

**Q: 如何启用7z压缩？**
A: 首先下载7za.exe并放置在指定目录，然后在配置文件中设置 `"use_7z": true`，并确保 `"exe_7z_path"` 指向正确的路径。

**Q: 备份失败怎么办？**
A: 查看日志文件 `logs/EasyBackuper/easybackuper_YYYYMMDD.log` 获取详细错误信息。常见原因包括磁盘空间不足、权限问题或存档文件被占用。

**Q: 如何在备份过程中保护服务器状态？**
A: 插件会在备份前暂停存档写入(`save hold`)，备份完成后恢复(`save resume`)，确保备份数据的一致性。

**Q: 可以在备份过程中重载配置吗？**
A: 不可以。插件会阻止在备份过程中重载配置，以防止状态不一致。请等待备份完成后再执行 `/backup reload`。

**Q: 日志文件在哪里？**
A: 日志文件保存在 `logs/EasyBackuper/` 目录下，按日期分割存储，文件名格式为 `easybackuper_YYYYMMDD.log`。

**Q: 如何切换插件语言？**
A: 在配置文件中修改 `"Language"` 值，支持的语言包括 `zh_CN`（简体中文）、`en_US`（英语）等。修改后执行 `/backup reload` 重载配置即可生效。

**Q: 备份文件大小是如何显示的？**
A: 备份完成后，插件会自动根据文件大小选择合适的单位进行显示，包括 B（字节）、KB（千字节）、MB（兆字节）和 GB（吉字节），方便快速了解备份文件大小。

## 许可证

AGPL-3.0

## 作者

梦涵LOVE

## 链接

- [GitHub仓库](https://github.com/MengHanLOVE1027/EasyBackuper)
- [MineBBS讨论帖](https://www.minebbs.com/resources/easybackuper-eb.7771/)
