<div align="center">
  <!-- <a href="https://github.com/MengHanLOVE1027/endstone-easybackuper/releases">
    <img src="https://avatars.githubusercontent.com/u/99132833?v=4" alt="Logo" width="128" height="128">
  </a> -->

![EndStone-EasyBackuper](https://socialify.git.ci/MengHanLOVE1027/endstone-easybackuper/image?custom_language=Python&description=1&font=Inter&forks=1&issues=1&language=1&logo=https://zh.minecraft.wiki/images/Chiseled_Bookshelf_%28stage_6%29_%28S%29_JE1.png?bbb31&name=1&owner=1&pattern=Plus&pulls=1&stargazers=1&theme=Auto)
<h3>EndStone-EasyBackuper</h3>

<p>
  <b>A lightweight, high-performance, and feature-rich hot backup plugin for Minecraft servers based on EndStone. </b>

  Powered by EndStone.<br>
</p>
</div>
<div align="center">

[![README](https://img.shields.io/badge/README-中文|Chinese-blue)](README.md) [![README_EN](https://img.shields.io/badge/README-英文|English-blue)](README_EN.md)

[![Github Version](https://img.shields.io/github/v/release/MengHanLOVE1027/endstone-easybackuper)](https://github.com/MengHanLOVE1027/endstone-easybackuper/releases) [![GitHub License](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](https://opensource.org/licenses/AGPL-3.0) [![Python](https://img.shields.io/badge/Python-3.8+-green.svg)](https://www.python.org/) [![Platform](https://img.shields.io/badge/Platform-EndStone-9cf.svg)](https://endstone.io) [![Downloads](https://img.shields.io/github/downloads/MengHanLOVE1027/endstone-easybackuper/total.svg)](https://github.com/MengHanLOVE1027/endstone-easybackuper/releases)

</div>

---

## 📖 Introduction

EasyBackuper is a backup plugin designed specifically for Endstone servers. It aims to simplify the backup process, improve backup efficiency, and ensure data security. It supports features such as automatic scheduled backups, intelligent cleanup, real-time notifications, multi-threaded acceleration, multiple format support, backup restoration, and multilingual interfaces, providing server administrators with a comprehensive data protection solution.

---

## ✨ Core Features

| Feature                           | Description                                                    |
| --------------------------------- | -------------------------------------------------------------- |
| 🔄 **Automatic Scheduled Backups** | Intelligent scheduled backups based on cron expressions        |
| 🧹 **Intelligent Cleanup**         | Automatically cleans old backups to save disk space            |
| 📢 **Real-time Notifications**     | Sends notifications to players before and after backups        |
| ⚡ **Multi-threaded Acceleration** | Parallel file processing to significantly improve backup speed |
| 🗜️ **Multiple Format Support**     | Supports various compression formats: 7z, zip, tar.gz          |
| 🔄 **Backup Restoration**          | One-click backup restoration with automatic restart support    |
| 🌍 **Multilingual Interface**      | Supports multiple languages including Chinese and English      |
| 📝 **Complete Logging System**     | Colored log output with daily log rotation                     |

---

## 🗂️ Directory Structure

```
Server Root Directory/
├── logs/
│   └── EasyBackuper/                    # Logs directory
│       ├── easybackuper_YYYYMMDD.log    # Main log file
│       └── easybackuper_restore_YYYYMMDD.log  # Restoration log
├── plugins/
│   ├── endstone_easybackuper-x.x.x-py3-none-any.whl  # Main plugin file
│   └── EasyBackuper/                    # Plugin resources directory
│       ├── 7za.exe                      # 7z compression tool
│       ├── restore_handler.exe          # Backup restoration handler
│       ├── config/
│       │   └── EasyBackuper.json        # Configuration file
│       └── langs/                       # Language files
│           ├── zh_CN.json               # Simplified Chinese
│           └── en_US.json               # English
└── backup/                              # Backup storage directory
```

---

## 🚀 Quick Start

### Installation Steps

1. **Download the Plugin**
   - Download the latest version from the [Releases page](https://github.com/MengHanLOVE1027/EasyBackuper/releases)
   - Or get it from [MineBBS](https://www.minebbs.com/resources/easybackuper-eb.7771/)

2. **Install the Plugin**
   ```bash
   # Copy the main plugin file to the server's plugins directory
   cp endstone_easybackuper-x.x.x-py3-none-any.whl plugins/
   
   # Create plugin resource directories
   mkdir -p plugins/EasyBackuper/config
   mkdir -p plugins/EasyBackuper/langs
   ```

3. **Install Dependencies**
   - Place `7za.exe` and `restore_handler.exe` into the `plugins/EasyBackuper/` directory (restore_handler.exe can be downloaded from the [Releases page](https://github.com/MengHanLOVE1027/EasyBackuper/releases) or compiled manually)

4. **Start the Server**
   - Restart the server or use the `/reload` command
   - The plugin will automatically generate default configuration files

---

## ⚙️ Configuration Details

Configuration file location: `plugins/EasyBackuper/config/EasyBackuper.json`

### 📋 Main Configuration Items

```json
{
  // 🌐 Internationalization Settings
  "Language": "zh_CN",  // Options: zh_CN, en_US
  
  // 🗜️ Compression Configuration
  "Compression": {
    "method": "zip",  // Compression algorithm: 7z, zip, tar
    "exe_7z_path": "./plugins/EasyBackuper/7za.exe",  // Path to 7z executable
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
  
  // 📁 Storage Path
  "BackupFolderPath": "./backup",  // Backup file save path
  
  // ⚡ Performance Configuration
  "Max_Workers": 4,  // Concurrent thread count
  
  // 🧹 Automatic Cleanup
  "Auto_Clean": {
    "Use_Number_Detection": {
      "Status": false,    // Enable automatic cleanup
      "Max_Number": 5,   // Maximum number of backups to retain
      "Mode": 0          // 0=Clean after server start, 1=Clean after backup, 2=Clean at server start
    }
  },
  
  // ⏰ Scheduled Tasks
  "Scheduled_Tasks": {
    "Status": false,                // Enable scheduled backups
    "Cron": "*/30 * * * * *"      // Cron expression, every 30 seconds
  },
  
  // 📢 Notification Settings
  "Broadcast": {
    "Status": true,                // Enable broadcast notifications
    "Time_ms": 5000,              // Notification time before backup (milliseconds)
    "Title": "[OP]Starting backup~",
    "Message": "Backup will start in 5 seconds!",
    "Server_Title": "[Server]Never Gonna Give You UP~",
    "Server_Message": "Never Gonna Let You Down~",
    "Backup_success_Title": "Backup completed!",
    "Backup_success_Message": "Star service, connecting with love",
    "Backup_wrong_Title": "Excellent service, backup failed",
    "Backup_wrong_Message": "RT"
  },
  
  // 🔍 Debug Settings
  "Debug_MoreLogs": false,         // Enable verbose logs (console)
  "Debug_MoreLogs_Player": false,  // Enable verbose logs (player)
  "Debug_MoreLogs_Cron": false,   // Enable verbose logs (cron tasks)

  // 🔄 Restoration Configuration
  "Restore": {
    "exe_path": "./plugins/EasyBackuper/restore_handler.exe",  // Restoration handler path
    "config": {
      "backup_old_world_before_restore": true,  // Backup current world before restoration
      "restart_server": {
        "status": false,                        // Auto-restart server after restoration
        "wait_time_s": 3,                       // Restart wait time (seconds)
        "start_script_path": "./start.bat"          // Start script path
      },
      "debug": false  // Enable restoration debug logs
    }
  }
}
```

### ⏰ Cron Expression Examples

| Expression       | Description              |
| ---------------- | ------------------------ |
| `*/30 * * * * *` | Every 30 seconds         |
| `0 0 3 ? * *`    | Daily at 3:00 AM         |
| `0 0 */2 ? * ?`  | Every 2 hours            |
| `0 0 0 ? * MON`  | Every Monday at midnight |

---

## 🎮 Command Manual

### Backup Management Commands

| Command          | Permission | Description                        |
| ---------------- | ---------- | ---------------------------------- |
| `/backup`        | OP         | Perform an immediate manual backup |
| `/backup init`   | OP         | Re-initialize configuration files  |
| `/backup reload` | OP         | Reload configuration files         |
| `/backup start`  | OP         | Start automatic backup service     |
| `/backup stop`   | OP         | Stop automatic backup service      |
| `/backup status` | OP         | View backup status                 |
| `/backup clean`  | OP         | Manually clean old backups         |

### Restoration Management Commands

| Command            | Permission | Description                       |
| ------------------ | ---------- | --------------------------------- |
| `/restore list`    | OP         | List all available backups        |
| `/restore <index>` | OP         | Restore specified backup by index |
| `/restore`         | OP         | Show restoration help             |

---

## 🔧 Advanced Features

### 🗜️ 7z Compression Configuration

1. **Download 7za.exe**
   ```bash
   # Download 7za.exe from the 7-Zip official website
   # Place it in the plugins/EasyBackuper/ directory
   ```

2. **Modify Configuration**
   ```json
   {
     "Compression": {
       "method": "7z",
       "exe_7z_path": "./plugins/EasyBackuper/7za.exe"
     }
   }
   ```

3. **Reload Configuration**
   ```bash
   /backup reload
   ```

### 🔄 Backup Restoration Handler

The restoration handler (`restore_handler.exe`) is used to safely restore backup files:

1. **How it Works**
   - Detects and waits for the running `bedrock_server` process to close
   - Backs up current world files (optional)
   - Extracts backup files to the server directory
   - Automatically restarts the server (optional)

2. **Location**
   ```
   plugins/EasyBackuper/restore_handler.exe
   ```

### 🚀 Multi-threading Optimization Suggestions

| Server Type              | Recommended Thread Count | Notes                             |
| ------------------------ | ------------------------ | --------------------------------- |
| Small Server (1-2 cores) | 2-4                      | Avoid excessive CPU usage         |
| Medium Server (4 cores)  | 4-6                      | Balance performance and resources |
| Large Server (8+ cores)  | 6-8                      | Maximize backup speed             |

> ⚠️ **Note**: Setting thread count too high may cause server lag. Adjust according to actual situation.

---

## 🛠️ Troubleshooting

### Common Issues

<details>
<summary><b>❓ Automatic backup not executing</b></summary>

**Troubleshooting Steps:**
1. Check scheduled task status
   ```bash
   /backup status
   ```
2. Verify cron expression format
3. Check log files
   ```bash
   cat logs/EasyBackuper/easybackuper_*.log
   ```
</details>

<details>
<summary><b>❓ Restoration feature not working</b></summary>

**Troubleshooting Methods:**
1. Confirm `restore_handler.exe` exists
   ```bash
   ls plugins/EasyBackiper/restore_handler.exe
   ```
2. Check restoration handler permissions
   ```bash
   chmod +x plugins/EasyBackuper/restore_handler.exe
   ```
3. View restoration logs
   ```bash
   cat logs/EasyBackuper/easybackuper_restore_*.log
   ```
</details>

### 📊 Log File Information

| Log File        | Location                                              | Purpose                                             |
| --------------- | ----------------------------------------------------- | --------------------------------------------------- |
| Main Log        | `logs/EasyBackuper/easybackuper_YYYYMMDD.log`         | Records regular operations like backups and cleanup |
| Restoration Log | `logs/EasyBackuper/easybackuper_restore_YYYYMMDD.log` | Records detailed restoration operations             |

---

## 📄 License

This project is open source under the **AGPL-3.0** license.

```
Copyright (c) 2023 梦涵LOVE

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
```

See the [LICENSE](LICENSE) file for the full license text.

---

## 👥 Contribution Guide

Issues and Pull Requests are welcome!

1. **Fork the Repository**
2. **Create a Feature Branch**
   ```bash
   git checkout -b feature/AmazingFeature
   ```
3. **Commit Your Changes**
   ```bash
   git commit -m 'Add some AmazingFeature'
   ```
4. **Push to the Branch**
   ```bash
   git push origin feature/AmazingFeature
   ```
5. **Open a Pull Request**

---

## 🌟 Support & Feedback

- **GitHub Issues**: [Submit Issues](https://github.com/MengHanLOVE1027/endstone-easybackuper/issues)
- **MineBBS**: [Discussion Thread](https://www.minebbs.com/resources/easybackuper-eb-minecraft.14896/)
- **Author**: 梦涵LOVE

---

<div align="center">

**⭐ If this project is helpful to you, please give us a Star!**

[![Star History Chart](https://api.star-history.com/svg?repos=MengHanLOVE1027/endstone-easybackuper&type=Date)](https://star-history.com/#MengHanLOVE1027/endstone-easybackuper&Date)

</div>
