package main

import (
	"archive/tar"
	"compress/gzip"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"time"

	"github.com/fatih/color"
	"github.com/mitchellh/go-ps"
)

const (
	pluginName        = "EasyBackuper"
	pluginNameSmall   = "easybackuper"
	defaultMaxWorkers = 4
)

// Config 结构体定义
type GlobalConfig struct {
	Debug      bool `json:"debug"`
	MaxWorkers int  `json:"max_workers"`
}

type RestoreConfig struct {
	Config struct {
		BackupOldWorldBeforeRestore bool `json:"backup_old_world_before_restore"`
		Debug                       bool `json:"debug"`
		RestartServer               struct {
			Status          bool   `json:"status"`
			WaitTimeS       int    `json:"wait_time_s"`
			StartScriptPath string `json:"start_script_path"`
		} `json:"restart_server"`
	} `json:"config"`
}

type CompressionFormat struct {
	Extension    string   `json:"extension"`
	CompressArgs []string `json:"compress_args"`
	ExtractArgs  []string `json:"extract_args"`
}

type CompressionConfig struct {
	Method    string                       `json:"method"`
	Exe7zPath string                       `json:"exe_7z_path"`
	Formats   map[string]CompressionFormat `json:"formats"`
}

type PluginConfig struct {
	Compression CompressionConfig `json:"Compression"`
	MaxWorkers  int               `json:"max_workers"`
	Restore     RestoreConfig
}

// RestoreInfo 结构体
type RestoreInfo struct {
	BackupFile string
	ServerDir  string
	WorldName  string
}

// 全局变量
var (
	globalConfig GlobalConfig
	pluginConfig PluginConfig
	restoreInfo  RestoreInfo
	logger       *log.Logger
	logFile      *os.File
	cyan         = color.New(color.FgCyan).SprintFunc()
	white        = color.New(color.FgWhite).SprintFunc()
	yellow       = color.New(color.FgYellow).SprintFunc()
	red          = color.New(color.FgRed).SprintFunc()
	green        = color.New(color.FgGreen).SprintFunc()

	// 语言与翻译
	currentLanguage = "zh_CN" // 当前语言，从配置文件 Language 读取 (zh_CN / en_US)

	// enMessages 英文翻译表，key 为中文原文；未收录时回退中文
	enMessages = map[string]string{
		"所有可能的配置文件路径都不存在，使用默认配置": "All possible configuration file paths do not exist, using default configuration",
		"当前平台不支持默认的 7za.exe，回退到 PATH 中的 7z": "Default 7za.exe is not supported on this platform, falling back to 7z in PATH",
		"7z解压完成": "7z extraction completed",
		"tar解压完成": "tar extraction completed",
		"7z压缩完成": "7z compression completed",
		"tar压缩完成": "tar compression completed",
		"服务器已关闭": "Server has been shut down",
		"目录删除完成": "Directory removal completed",
		"配置为回档前自动备份当前世界": "Configured to automatically backup current world before restore",
		"回档前备份完成": "Pre-restore backup completed",
		"配置为不自动重启服务器": "Configured not to automatically restart server",
		"配置为回档后自动重启服务器": "Configured to automatically restart server after restore",
		"正在启动服务器...": "Starting server...",
		"暂不支持Linux/Mac": "Linux/Mac not yet supported",
		"请手动启动服务器": "Please start server manually",
		"服务器启动命令已执行": "Server start command has been executed",
		"EasyBackuper 回档处理程序启动": "EasyBackuper Restore Handler Started",
		"配置为不备份当前世界": "Configured not to backup current world",
		"开始恢复备份": "Starting backup restore",
		"检测到.7z格式备份文件，使用7z解压": "Detected .7z format backup file, using 7z to extract",
		"检测到.zip格式备份文件，使用7z解压": "Detected .zip format backup file, using 7z to extract",
		"检测到.tar.gz格式备份文件，使用tar解压": "Detected .tar.gz format backup file, using tar to extract",
		"tar解压失败，尝试使用7z解压": "tar extraction failed, trying to use 7z to extract",
		"使用配置中的7z解压": "Using 7z from configuration to extract",
		"使用配置中的tar解压": "Using tar from configuration to extract",
		"使用默认的7z解压": "Using default 7z to extract",
		"开始复制文件...": "Starting file copy...",
		"文件复制完成": "File copy completed",
		"备份恢复完成": "Backup restore completed",

		"使用配置文件路径: %s": "Using configuration file path: %s",
		"成功加载配置文件: %s": "Successfully loaded configuration file: %s",
		"DEBUG模式: %v": "DEBUG mode: %v",
		"MaxWorkers: %d": "MaxWorkers: %d",
		"复制文件: %s --> %s": "Copying file:%s --> %s",
		"创建目录: %s": "Created directory: %s",
		"创建目录: %s ==> %s": "Created directory: %s ==> %s",
		"配置的7z路径不存在: %s，回退到 PATH 中的 7z": "Configured 7z path does not exist: %s, falling back to 7z in PATH",
		"使用7z解压: %s": "Extracting with 7z: %s",
		"解压目标: %s --> %s": "Extracting to: %s --> %s",
		"使用tar解压: %s": "Extracting with tar: %s",
		"使用7z压缩: %s": "Compressing with 7z: %s",
		"压缩目标: %s --> %s": "Compressing to: %s --> %s",
		"备份文件已保存: %s": "Backup file saved: %s",
		"使用tar压缩: %s": "Compressing with tar: %s",
		"获取进程列表失败: %v": "Failed to get process list: %v",
		"检测到%s进程正在运行，等待服务器关闭": "Detected %s process is running, waiting for server to shutdown",
		"正在删除目录: %s": "Removing directory: %s",
		"删除文件: %s --> [已删除]": "Deleting file: %s --> [Deleted]",
		"正在备份当前世界: %s": "Backing up current world: %s",
		"等待 %d 秒后启动服务器...": "Waiting %d seconds before starting server...",
		"启动脚本路径: %s": "Start script path: %s",
		"服务器目录: %s": "Server directory: %s",
		"启动脚本完整路径: %s": "Full path of start script: %s",
		"启动脚本不存在: %s": "Start script does not exist: %s",
		"执行命令: %s": "Executing command: %s",
		"工作目录: %s": "Working directory: %s",
		"启动服务器失败: %v": "Failed to start server: %v",
		"Go版本: %s": "Go version: %s",
		"操作系统: %s/%s": "Operating system: %s/%s",
		"切换工作目录失败: %v": "Failed to change working directory: %v",
		"切换工作目录到: %s": "Changed working directory to: %s",
		"未检测到%s进程，继续回档操作": "No %s process detected, continuing with restore operation",
		"回档前备份失败: %v": "Pre-restore backup failed: %v",
		"创建临时目录失败: %v": "Failed to create temporary directory: %v",
		"创建临时目录: %s": "Created temporary directory: %s",
		"解压失败: %v": "Extraction failed: %v",
		"删除旧世界目录失败: %v": "Failed to remove old world directory: %v",
		"复制目标: %s ==> %s": "Copy target: %s ==> %s",
		"使用 %d 个goroutine进行文件复制": "Using %d goroutines for file copying",
		"文件复制失败: %v": "File copy failed: %v",

		"创建日志目录失败: %v": "Failed to create log directory: %v",
		"打开日志文件失败: %v": "Failed to open log file: %v",
		"读取配置文件失败: %v": "Failed to read configuration file: %v",
		"解析配置文件失败: %v": "Failed to parse configuration file: %v",
		"打开源文件失败: %v": "Failed to open source file: %v",
		"创建目标目录失败: %v": "Failed to create destination directory: %v",
		"创建目标文件失败: %v": "Failed to create destination file: %v",
		"复制文件内容失败: %v": "Failed to copy file content: %v",
		"遍历源目录失败: %v": "Failed to traverse source directory: %v",
		"计算相对路径失败: %v": "Failed to calculate relative path: %v",
		"创建目录失败: %v": "Failed to create directory: %v",
		"7z解压失败: %v\n输出: %s": "7z extraction failed: %v\nOutput: %s",
		"打开压缩文件失败: %v": "Failed to open archive file: %v",
		"创建gzip读取器失败: %v": "Failed to create gzip reader: %v",
		"读取tar头部失败: %v": "Failed to read tar header: %v",
		"创建文件目录失败: %v": "Failed to create file directory: %v",
		"创建文件失败: %v": "Failed to create file: %v",
		"写入文件失败: %v": "Failed to write file: %v",
		"设置文件权限失败: %v": "Failed to set file permissions: %v",
		"7z压缩失败: %v\n输出: %s": "7z compression failed: %v\nOutput: %s",
		"创建压缩文件失败: %v": "Failed to create archive file: %v",
		"压缩过程中发生错误: %v": "Error occurred during compression: %v",
		"遍历目录失败: %v": "Failed to traverse directory: %v",
		"删除目录失败: %v": "Failed to remove directory: %v",
		"创建备份目录失败: %v": "Failed to create backup directory: %v",
		"创建临时备份目录失败: %v": "Failed to create temporary backup directory: %v",
		"备份世界目录失败: %v": "Failed to backup world directory: %v",
	}
)

// T 根据当前语言翻译消息，支持 fmt.Sprintf 风格参数；未收录或语言不匹配时回退中文原文。
func T(text string, args ...interface{}) string {
	translated := text
	if currentLanguage == "en_US" {
		if v, ok := enMessages[text]; ok {
			translated = v
		}
	}
	if len(args) > 0 {
		return fmt.Sprintf(translated, args...)
	}
	return translated
}

// pluginPrint 自定义日志输出
func pluginPrint(text string, level string) {
	// 如果是DEBUG级别且未开启DEBUG模式，则不输出
	if level == "DEBUG" && !globalConfig.Debug {
		return
	}

	// 获取当前时间
	currentTime := time.Now().Format("2006-01-02 15:04:05")

	// 日志级别颜色映射
	var levelColor string
	var levelText string

	switch level {
	case "DEBUG":
		levelColor = cyan(level)
		levelText = fmt.Sprintf("[%s] [%s] ", pluginName, levelColor)
	case "INFO":
		levelColor = white(level)
		levelText = fmt.Sprintf("[%s] [%s] ", pluginName, levelColor)
	case "WARNING":
		levelColor = yellow(level)
		levelText = fmt.Sprintf("[%s] [%s] ", pluginName, levelColor)
	case "ERROR":
		levelColor = red(level)
		levelText = fmt.Sprintf("[%s] [%s] ", pluginName, levelColor)
	case "SUCCESS":
		levelColor = green(level)
		levelText = fmt.Sprintf("[%s] [%s] ", pluginName, levelColor)
	default:
		levelText = fmt.Sprintf("[%s] [%s] ", pluginName, level)
	}

	// 输出到控制台
	fmt.Println(levelText + text)

	// 输出到日志文件
	if logger != nil {
		logPrefix := fmt.Sprintf("[%s] [%s] ", currentTime, level)
		logger.Println(logPrefix + text)
	}
}

// setupLogging 配置日志记录
func setupLogging(serverDir string) error {
	logDir := filepath.Join(serverDir, "logs", pluginName)
	err := os.MkdirAll(logDir, 0755)
	if err != nil {
		return fmt.Errorf(T("创建日志目录失败: %v"), err)
	}

	logFileName := fmt.Sprintf("%s_restore_%s.log", pluginNameSmall,
		time.Now().Format("20060102"))
	logFilePath := filepath.Join(logDir, logFileName)

	logFile, err = os.OpenFile(logFilePath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err != nil {
		return fmt.Errorf(T("打开日志文件失败: %v"), err)
	}

	// 设置日志级别
	logLevel := log.LstdFlags
	if globalConfig.Debug {
		// 在调试模式下，添加更详细的日志信息
		logger = log.New(logFile, "", logLevel|log.Lshortfile)
	} else {
		logger = log.New(logFile, "", logLevel)
	}

	return nil
}

// loadConfig 加载配置文件
func loadConfig(serverDir string) error {
	// 尝试多个可能的配置文件路径
	possiblePaths := []string{
		filepath.Join(serverDir, "plugins", "EasyBackuper", "config", "EasyBackuper.json"),
		filepath.Join(".", "plugins", "EasyBackuper", "config", "EasyBackuper.json"),
		filepath.Join(".", "plugins", "EasyBackuper", "config", "EasyBackuper.json"),
	}

	var configPath string
	for _, path := range possiblePaths {
		if _, err := os.Stat(path); err == nil {
			configPath = path
			break
		}
	}

	if configPath == "" {
		pluginPrint(T("所有可能的配置文件路径都不存在，使用默认配置"), "WARNING")
		currentLanguage = "zh_CN"
		pluginConfig = PluginConfig{
			Compression: CompressionConfig{
				Method:    "zip",
				Exe7zPath: "./plugins/EasyBackuper/7za.exe",
				Formats:   make(map[string]CompressionFormat),
			},
			MaxWorkers: defaultMaxWorkers,
		}
		// 初始化默认格式
		pluginConfig.Compression.Formats["7z"] = CompressionFormat{
			Extension:    ".7z",
			CompressArgs: []string{"a", "-t7z", "-mx=5"},
			ExtractArgs:  []string{"x", "-y"},
		}
		pluginConfig.Compression.Formats["zip"] = CompressionFormat{
			Extension:    ".zip",
			CompressArgs: []string{"a", "-tzip", "-mx=5"},
			ExtractArgs:  []string{"x", "-y"},
		}
		pluginConfig.Compression.Formats["tar"] = CompressionFormat{
			Extension:    ".tar.gz",
			CompressArgs: []string{"a", "-ttar", "-mx=5"},
			ExtractArgs:  []string{"x", "-y"},
		}
		return nil
	}

	// 读取配置文件
	data, err := os.ReadFile(configPath)
	if err != nil {
		return fmt.Errorf(T("读取配置文件失败: %v"), err)
	}

	// 解析JSON
	var config map[string]interface{}
	if err := json.Unmarshal(data, &config); err != nil {
		return fmt.Errorf(T("解析配置文件失败: %v"), err)
	}

	// 读取语言配置
	if lang, ok := config["Language"].(string); ok && lang != "" {
		currentLanguage = lang
	}

	pluginPrint(T("使用配置文件路径: %s", configPath), "INFO")

	// 初始化默认配置
	pluginConfig = PluginConfig{
		Compression: CompressionConfig{
			Method:    "zip",
			Exe7zPath: "./plugins/EasyBackuper/7za.exe",
			Formats:   make(map[string]CompressionFormat),
		},
		MaxWorkers: defaultMaxWorkers,
	}
	// 初始化默认格式
	pluginConfig.Compression.Formats["7z"] = CompressionFormat{
		Extension:    ".7z",
		CompressArgs: []string{"a", "-t7z", "-mx=5"},
		ExtractArgs:  []string{"x", "-y"},
	}
	pluginConfig.Compression.Formats["zip"] = CompressionFormat{
		Extension:    ".zip",
		CompressArgs: []string{"a", "-tzip", "-mx=5"},
		ExtractArgs:  []string{"x", "-y"},
	}
	pluginConfig.Compression.Formats["tar"] = CompressionFormat{
		Extension:    ".tar.gz",
		CompressArgs: []string{"a", "-ttar", "-mx=5"},
		ExtractArgs:  []string{"x", "-y"},
	}

	// 设置插件配置
	if compressionData, ok := config["Compression"].(map[string]interface{}); ok {
		if method, ok := compressionData["method"].(string); ok {
			pluginConfig.Compression.Method = method
		}
		if exe7zPath, ok := compressionData["exe_7z_path"].(string); ok {
			pluginConfig.Compression.Exe7zPath = exe7zPath
		}
		// 确保Formats map已初始化
		if pluginConfig.Compression.Formats == nil {
			pluginConfig.Compression.Formats = make(map[string]CompressionFormat)
		}
		if formatsData, ok := compressionData["formats"].(map[string]interface{}); ok {
			for formatName, formatData := range formatsData {
				if formatMap, ok := formatData.(map[string]interface{}); ok {
					format := CompressionFormat{}
					if extension, ok := formatMap["extension"].(string); ok {
						format.Extension = extension
					}
					if compressArgs, ok := formatMap["compress_args"].([]interface{}); ok {
						for _, arg := range compressArgs {
							if argStr, ok := arg.(string); ok {
								format.CompressArgs = append(format.CompressArgs, argStr)
							}
						}
					}
					if extractArgs, ok := formatMap["extract_args"].([]interface{}); ok {
						for _, arg := range extractArgs {
							if argStr, ok := arg.(string); ok {
								format.ExtractArgs = append(format.ExtractArgs, argStr)
							}
						}
					}
					pluginConfig.Compression.Formats[formatName] = format
				}
			}
		}
	}
	if maxWorkers, ok := config["max_workers"].(float64); ok {
		pluginConfig.MaxWorkers = int(maxWorkers)
	} else {
		pluginConfig.MaxWorkers = defaultMaxWorkers
	}

	// 解析Restore配置
	if restoreData, ok := config["Restore"].(map[string]interface{}); ok {
		if configData, ok := restoreData["config"].(map[string]interface{}); ok {
			if debugVal, ok := configData["debug"].(bool); ok {
				globalConfig.Debug = debugVal
			}
			if backupOldWorld, ok := configData["backup_old_world_before_restore"].(bool); ok {
				pluginConfig.Restore.Config.BackupOldWorldBeforeRestore = backupOldWorld
			}
			if restartServer, ok := configData["restart_server"].(map[string]interface{}); ok {
				if status, ok := restartServer["status"].(bool); ok {
					pluginConfig.Restore.Config.RestartServer.Status = status
				}
				if waitTime, ok := restartServer["wait_time_s"].(float64); ok {
					pluginConfig.Restore.Config.RestartServer.WaitTimeS = int(waitTime)
				}
				if scriptPath, ok := restartServer["start_script_path"].(string); ok {
					pluginConfig.Restore.Config.RestartServer.StartScriptPath = scriptPath
				}
			}
		}
	}

	globalConfig.MaxWorkers = pluginConfig.MaxWorkers

	pluginPrint(T("成功加载配置文件: %s", configPath), "SUCCESS")
	pluginPrint(T("DEBUG模式: %v", globalConfig.Debug), "INFO")
	pluginPrint(T("MaxWorkers: %d", globalConfig.MaxWorkers), "INFO")

	return nil
}

// copyFileWithProgress 复制文件
func copyFileWithProgress(src, dst string) error {
	pluginPrint(T("复制文件: %s --> %s", src, dst), "DEBUG")

	sourceFile, err := os.Open(src)
	if err != nil {
		return fmt.Errorf(T("打开源文件失败: %v"), err)
	}
	defer sourceFile.Close()

	// 创建目标目录
	dstDir := filepath.Dir(dst)
	if err := os.MkdirAll(dstDir, 0755); err != nil {
		return fmt.Errorf(T("创建目标目录失败: %v"), err)
	}

	destinationFile, err := os.Create(dst)
	if err != nil {
		return fmt.Errorf(T("创建目标文件失败: %v"), err)
	}
	defer destinationFile.Close()

	_, err = io.Copy(destinationFile, sourceFile)
	if err != nil {
		return fmt.Errorf(T("复制文件内容失败: %v"), err)
	}

	// 复制文件权限
	sourceInfo, err := sourceFile.Stat()
	if err == nil {
		os.Chmod(dst, sourceInfo.Mode())
	}

	return nil
}

// copyDirWithProgress 多goroutine复制目录
func copyDirWithProgress(src, dst string, maxThreads int) error {
	if _, err := os.Stat(dst); os.IsNotExist(err) {
		if err := os.MkdirAll(dst, 0755); err != nil {
			return fmt.Errorf(T("创建目标目录失败: %v"), err)
		}
		pluginPrint(T("创建目录: %s", dst), "DEBUG")
	}

	// 收集所有文件
	var files []string
	var dirs []string

	err := filepath.Walk(src, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}

		if info.IsDir() {
			dirs = append(dirs, path)
		} else {
			files = append(files, path)
		}
		return nil
	})

	if err != nil {
		return fmt.Errorf(T("遍历源目录失败: %v"), err)
	}

	// 先创建所有目录
	for _, dir := range dirs {
		relPath, err := filepath.Rel(src, dir)
		if err != nil {
			return fmt.Errorf(T("计算相对路径失败: %v"), err)
		}
		dstDir := filepath.Join(dst, relPath)
		if _, err := os.Stat(dstDir); os.IsNotExist(err) {
			if err := os.MkdirAll(dstDir, 0755); err != nil {
				return fmt.Errorf(T("创建目录失败: %v"), err)
			}
			pluginPrint(T("创建目录: %s ==> %s", dir, dstDir), "DEBUG")
		}
	}

	// 使用工作池复制文件
	type copyTask struct {
		src string
		dst string
	}

	tasks := make(chan copyTask, len(files))
	errors := make(chan error, len(files))
	var wg sync.WaitGroup

	// 启动worker
	for i := 0; i < maxThreads; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for task := range tasks {
				if err := copyFileWithProgress(task.src, task.dst); err != nil {
					errors <- err
				}
			}
		}()
	}

	// 发送任务
	for _, file := range files {
		relPath, err := filepath.Rel(src, file)
		if err != nil {
			errors <- fmt.Errorf(T("计算相对路径失败: %v"), err)
			continue
		}
		dstPath := filepath.Join(dst, relPath)
		tasks <- copyTask{src: file, dst: dstPath}
	}
	close(tasks)

	wg.Wait()

	// 检查错误
	select {
	case err := <-errors:
		return err
	default:
		return nil
	}
}

// resolve7zPath 获取实际使用的7z可执行文件路径
// 优先使用配置中的 exe_7z_path；
// 非Windows平台上，若配置的是默认的 .exe 文件或路径不存在，则回退到 PATH 中的 7z。
func resolve7zPath() string {
	configured := strings.TrimSpace(pluginConfig.Compression.Exe7zPath)

	if configured == "" {
		return "7z"
	}

	// 非Windows平台上，默认配置指向 Windows 的 7za.exe，回退到 PATH 中的 7z
	if runtime.GOOS != "windows" && strings.HasSuffix(strings.ToLower(configured), ".exe") {
		pluginPrint(T("当前平台不支持默认的 7za.exe，回退到 PATH 中的 7z"), "WARNING")
		return "7z"
	}

	// 配置的是含路径的文件，但文件不存在，回退到 PATH 中的 7z
	if strings.ContainsAny(configured, "/\\") {
		if _, err := os.Stat(configured); err != nil {
			pluginPrint(T("配置的7z路径不存在: %s，回退到 PATH 中的 7z", configured), "WARNING")
			return "7z"
		}
	}

	return configured
}

// extractWith7z 使用7z解压
func extractWith7z(archivePath, destDir string) error {
	pluginPrint(T("使用7z解压: %s", archivePath), "INFO")
	pluginPrint(T("解压目标: %s --> %s", archivePath, destDir), "INFO")

	cmd := exec.Command(resolve7zPath(), "x", archivePath, "-o"+destDir, "-y")

	output, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf(T("7z解压失败: %v\n输出: %s"), err, string(output))
	}

	pluginPrint(T("7z解压完成"), "SUCCESS")
	return nil
}

// extractWithTarGz 使用tar解压
func extractWithTarGz(archivePath, destDir string) error {
	pluginPrint(T("使用tar解压: %s", archivePath), "INFO")
	pluginPrint(T("解压目标: %s --> %s", archivePath, destDir), "INFO")

	file, err := os.Open(archivePath)
	if err != nil {
		return fmt.Errorf(T("打开压缩文件失败: %v"), err)
	}
	defer file.Close()

	gzReader, err := gzip.NewReader(file)
	if err != nil {
		return fmt.Errorf(T("创建gzip读取器失败: %v"), err)
	}
	defer gzReader.Close()

	tarReader := tar.NewReader(gzReader)

	for {
		header, err := tarReader.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			return fmt.Errorf(T("读取tar头部失败: %v"), err)
		}

		targetPath := filepath.Join(destDir, header.Name)

		switch header.Typeflag {
		case tar.TypeDir:
			if err := os.MkdirAll(targetPath, 0755); err != nil {
				return fmt.Errorf(T("创建目录失败: %v"), err)
			}
		case tar.TypeReg:
			// 创建目录
			if err := os.MkdirAll(filepath.Dir(targetPath), 0755); err != nil {
				return fmt.Errorf(T("创建文件目录失败: %v"), err)
			}

			// 创建文件
			outFile, err := os.Create(targetPath)
			if err != nil {
				return fmt.Errorf(T("创建文件失败: %v"), err)
			}

			if _, err := io.Copy(outFile, tarReader); err != nil {
				outFile.Close()
				return fmt.Errorf(T("写入文件失败: %v"), err)
			}
			outFile.Close()

			// 设置文件权限
			if err := os.Chmod(targetPath, os.FileMode(header.Mode)); err != nil {
				return fmt.Errorf(T("设置文件权限失败: %v"), err)
			}
		}
	}

	pluginPrint(T("tar解压完成"), "SUCCESS")
	return nil
}

// compressWith7z 使用7z压缩
func compressWith7z(srcDir, destFile string) error {
	pluginPrint(T("使用7z压缩: %s", srcDir), "INFO")
	pluginPrint(T("压缩目标: %s --> %s", srcDir, destFile), "INFO")

	cmd := exec.Command(resolve7zPath(), "a", destFile, srcDir+string(filepath.Separator)+"*", "-y")

	output, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf(T("7z压缩失败: %v\n输出: %s"), err, string(output))
	}

	pluginPrint(T("7z压缩完成"), "SUCCESS")
	pluginPrint(T("备份文件已保存: %s", destFile), "SUCCESS")
	return nil
}

// compressWithTarGz 使用tar压缩
func compressWithTarGz(srcDir, destFile string) error {
	pluginPrint(T("使用tar压缩: %s", srcDir), "INFO")
	pluginPrint(T("压缩目标: %s --> %s", srcDir, destFile), "INFO")

	file, err := os.Create(destFile)
	if err != nil {
		return fmt.Errorf(T("创建压缩文件失败: %v"), err)
	}
	defer file.Close()

	gzWriter := gzip.NewWriter(file)
	defer gzWriter.Close()

	tarWriter := tar.NewWriter(gzWriter)
	defer tarWriter.Close()

	baseDir := filepath.Dir(srcDir)
	dirName := filepath.Base(srcDir)

	err = filepath.Walk(srcDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}

		// 创建tar头部
		header, err := tar.FileInfoHeader(info, "")
		if err != nil {
			return err
		}

		// 调整路径
		relPath, err := filepath.Rel(baseDir, path)
		if err != nil {
			return err
		}
		header.Name = filepath.Join(dirName, relPath)

		// 写入头部
		if err := tarWriter.WriteHeader(header); err != nil {
			return err
		}

		// 如果是文件，写入内容
		if !info.IsDir() {
			file, err := os.Open(path)
			if err != nil {
				return err
			}
			defer file.Close()

			if _, err := io.Copy(tarWriter, file); err != nil {
				return err
			}
		}

		return nil
	})

	if err != nil {
		return fmt.Errorf(T("压缩过程中发生错误: %v"), err)
	}

	pluginPrint(T("tar压缩完成"), "SUCCESS")
	pluginPrint(T("备份文件已保存: %s", destFile), "SUCCESS")
	return nil
}

// isProcessRunning 检测进程是否在运行
func isProcessRunning(processName string) bool {
	processes, err := ps.Processes()
	if err != nil {
		pluginPrint(T("获取进程列表失败: %v", err), "ERROR")
		return false
	}

	for _, process := range processes {
		if strings.Contains(strings.ToLower(process.Executable()), strings.ToLower(processName)) {
			return true
		}
	}
	return false
}

// waitForProcessExit 等待进程退出
func waitForProcessExit(processName string) {
	pluginPrint(T("检测到%s进程正在运行，等待服务器关闭", processName), "WARNING")

	for isProcessRunning(processName) {
		time.Sleep(1 * time.Second)
	}

	pluginPrint(T("服务器已关闭"), "SUCCESS")
}

// removeDir 删除目录
func removeDir(dir string) error {
	pluginPrint(T("正在删除目录: %s", dir), "INFO")

	err := filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}

		// 设置写权限
		os.Chmod(path, 0666)

		if !info.IsDir() {
			pluginPrint(T("删除文件: %s --> [已删除]", path), "DEBUG")
		}
		return nil
	})

	if err != nil {
		return fmt.Errorf(T("遍历目录失败: %v"), err)
	}

	// 删除整个目录
	err = os.RemoveAll(dir)
	if err != nil {
		return fmt.Errorf(T("删除目录失败: %v"), err)
	}

	pluginPrint(T("目录删除完成"), "SUCCESS")
	return nil
}

// backupCurrentWorld 备份当前世界
func backupCurrentWorld() error {
	pluginPrint(T("配置为回档前自动备份当前世界"), "INFO")

	// 获取当前时间作为备份名称的一部分
	currentTime := time.Now().Format("20060102_150405")
	backupName := fmt.Sprintf("before_restore_%s", currentTime)

	// 获取备份目录
	backupDir := "./backup"
	if err := os.MkdirAll(backupDir, 0755); err != nil {
		return fmt.Errorf(T("创建备份目录失败: %v"), err)
	}

	// 创建临时目录
	tempBackupDir := filepath.Join(restoreInfo.ServerDir, "temp_easybackuper_backup")
	if _, err := os.Stat(tempBackupDir); err == nil {
		os.RemoveAll(tempBackupDir)
	}

	if err := os.MkdirAll(tempBackupDir, 0755); err != nil {
		return fmt.Errorf(T("创建临时备份目录失败: %v"), err)
	}
	defer os.RemoveAll(tempBackupDir)

	// 复制世界目录到临时目录
	worldsDir := filepath.Join(restoreInfo.ServerDir, "worlds")
	tempWorldBackupDir := filepath.Join(tempBackupDir, restoreInfo.WorldName)

	pluginPrint(T("正在备份当前世界: %s", worldsDir), "INFO")

	if err := copyDirWithProgress(worldsDir, tempWorldBackupDir, globalConfig.MaxWorkers); err != nil {
		return fmt.Errorf(T("备份世界目录失败: %v"), err)
	}

	// 根据配置选择压缩方式
	var oldBackupFilePath string
	compressionMethod := pluginConfig.Compression.Method
	if compressionMethod == "" {
		compressionMethod = "zip" // 默认使用zip
	}

	// 获取文件扩展名
	var fileExtension string
	if format, ok := pluginConfig.Compression.Formats[compressionMethod]; ok {
		fileExtension = format.Extension
	} else {
		fileExtension = ".zip" // 默认扩展名
	}

	oldBackupFilePath = filepath.Join(backupDir, backupName+fileExtension)

	// 根据压缩方法选择压缩函数
	switch compressionMethod {
	case "7z", "zip":
		if err := compressWith7z(tempWorldBackupDir, oldBackupFilePath); err != nil {
			return err
		}
	case "tar":
		if err := compressWithTarGz(tempWorldBackupDir, oldBackupFilePath); err != nil {
			return err
		}
	default:
		// 默认使用7z压缩
		if err := compressWith7z(tempWorldBackupDir, oldBackupFilePath); err != nil {
			return err
		}
	}

	pluginPrint(T("回档前备份完成"), "SUCCESS")
	return nil
}

// restartServer 重启服务器
func restartServer() {
	restartConfig := pluginConfig.Restore.Config.RestartServer
	if !restartConfig.Status {
		pluginPrint(T("配置为不自动重启服务器"), "INFO")
		return
	}

	pluginPrint(T("配置为回档后自动重启服务器"), "INFO")
	waitTime := restartConfig.WaitTimeS
	if waitTime == 0 {
		waitTime = 10
	}

	pluginPrint(T("等待 %d 秒后启动服务器...", waitTime), "INFO")
	time.Sleep(time.Duration(waitTime) * time.Second)

	startScriptPath := restartConfig.StartScriptPath
	if startScriptPath == "" {
		startScriptPath = "./start.bat"
	}

	pluginPrint(T("启动脚本路径: %s", startScriptPath), "INFO")

	// 解析启动脚本的绝对路径
	var startScriptFullPath string
	if filepath.IsAbs(startScriptPath) {
		startScriptFullPath = startScriptPath
	} else {
		startScriptFullPath = filepath.Join(restoreInfo.ServerDir, startScriptPath)
	}

	pluginPrint(T("服务器目录: %s", restoreInfo.ServerDir), "INFO")
	pluginPrint(T("启动脚本完整路径: %s", startScriptFullPath), "INFO")

	// 执行启动脚本
	pluginPrint(T("正在启动服务器..."), "INFO")

	// 检查脚本文件是否存在
	if _, err := os.Stat(startScriptFullPath); os.IsNotExist(err) {
		pluginPrint(T("启动脚本不存在: %s", startScriptFullPath), "ERROR")
		return
	}

	var cmd *exec.Cmd
	if runtime.GOOS == "windows" {
		// Windows 上使用 start 命令打开新窗口执行批处理文件
		cmd_path := os.Getenv("PATH")
		pluginPrint(cmd_path, "INFO")
		cmd = exec.Command("C:\\Windows\\System32\\cmd.exe", "/c", "start", "/I", startScriptFullPath)
	} else {
		// Linux/Mac 上直接执行脚本文件
		// cmd = exec.Command(startScriptFullPath)
		// 暂不支持Linux/Mac
		pluginPrint(T("暂不支持Linux/Mac"), "ERROR")
		pluginPrint(T("请手动启动服务器"), "INFO")
		return
	}

	// 设置工作目录
	cmd.Dir = restoreInfo.ServerDir

	// 打印命令信息用于调试
	pluginPrint(T("执行命令: %s", cmd.String()), "INFO")
	pluginPrint(T("工作目录: %s", cmd.Dir), "INFO")

	// 执行命令并等待完成
	if err := cmd.Run(); err != nil {
		pluginPrint(T("启动服务器失败: %v", err), "ERROR")
	} else {
		pluginPrint(T("服务器启动命令已执行"), "SUCCESS")
	}
}

// main 主函数
func main() {
	// 解析命令行参数
	backupFile := flag.String("backup", "", "备份文件路径")
	serverDir := flag.String("server", "", "服务器目录")
	worldName := flag.String("world", "", "世界名称")
	flag.Parse()

	// 检查必要参数
	if *backupFile == "" || *serverDir == "" || *worldName == "" {
		fmt.Println("使用方法: easybackuper -backup <备份文件> -server <服务器目录> -world <世界名称>")
		fmt.Println("缺少必要的参数")
		if runtime.GOOS == "windows" {
			fmt.Println("按任意键继续...")
			var input string
			fmt.Scanln(&input)
		}
		os.Exit(1)
	}

	restoreInfo = RestoreInfo{
		BackupFile: *backupFile,
		ServerDir:  *serverDir,
		WorldName:  *worldName,
	}

	// 加载配置
	if err := loadConfig(restoreInfo.ServerDir); err != nil {
		fmt.Printf("加载配置失败: %v\n", err)
		os.Exit(1)
	}

	// 设置日志
	if err := setupLogging(restoreInfo.ServerDir); err != nil {
		fmt.Printf("设置日志失败: %v\n", err)
		os.Exit(1)
	}
	defer logFile.Close()

	pluginPrint(strings.Repeat("=", 60), "INFO")
	pluginPrint(T("EasyBackuper 回档处理程序启动"), "SUCCESS")
	pluginPrint(T("Go版本: %s", runtime.Version()), "INFO")
	pluginPrint(T("操作系统: %s/%s", runtime.GOOS, runtime.GOARCH), "INFO")
	pluginPrint(T("工作目录: %s", restoreInfo.ServerDir), "INFO")
	pluginPrint(strings.Repeat("=", 60), "INFO")

	// 切换工作目录
	if err := os.Chdir(restoreInfo.ServerDir); err != nil {
		pluginPrint(T("切换工作目录失败: %v", err), "ERROR")
		os.Exit(1)
	}
	pluginPrint(T("切换工作目录到: %s", restoreInfo.ServerDir), "INFO")

	// 检测bedrock_server进程是否在运行
	var processName string
	if runtime.GOOS == "windows" {
		processName = "bedrock_server.exe"
	} else {
		processName = "bedrock_server"
	}

	if isProcessRunning(processName) {
		waitForProcessExit(processName)
	} else {
		pluginPrint(T("未检测到%s进程，继续回档操作", processName), "INFO")
	}

	pluginPrint(strings.Repeat("=", 60), "INFO")

	// 检查是否需要在回档前备份当前世界
	if pluginConfig.Restore.Config.BackupOldWorldBeforeRestore {
		if err := backupCurrentWorld(); err != nil {
			pluginPrint(T("回档前备份失败: %v", err), "ERROR")
			// 继续执行，不终止
		}
	} else {
		pluginPrint(T("配置为不备份当前世界"), "INFO")
	}

	pluginPrint(strings.Repeat("=", 60), "INFO")

	// 恢复备份
	pluginPrint(T("开始恢复备份"), "INFO")
	worldsDir := filepath.Join(restoreInfo.ServerDir, "worlds")

	// 创建临时目录用于解压
	tempDir := filepath.Join(restoreInfo.ServerDir, "temp_easybackuper")
	if _, err := os.Stat(tempDir); err == nil {
		os.RemoveAll(tempDir)
	}

	if err := os.MkdirAll(tempDir, 0755); err != nil {
		pluginPrint(T("创建临时目录失败: %v", err), "ERROR")
		os.Exit(1)
	}
	defer os.RemoveAll(tempDir)

	pluginPrint(T("创建临时目录: %s", tempDir), "INFO")

	// 根据配置选择解压方式
	tempWorldDir := filepath.Join(tempDir, restoreInfo.WorldName)
	backupFilePath := restoreInfo.BackupFile

	var err error
	// 根据文件扩展名选择解压方式
	if strings.HasSuffix(strings.ToLower(backupFilePath), ".7z") {
		pluginPrint(T("检测到.7z格式备份文件，使用7z解压"), "INFO")
		err = extractWith7z(backupFilePath, tempWorldDir)
	} else if strings.HasSuffix(strings.ToLower(backupFilePath), ".zip") {
		pluginPrint(T("检测到.zip格式备份文件，使用7z解压"), "INFO")
		err = extractWith7z(backupFilePath, tempWorldDir)
	} else if strings.HasSuffix(strings.ToLower(backupFilePath), ".tar.gz") || strings.HasSuffix(strings.ToLower(backupFilePath), ".tgz") {
		pluginPrint(T("检测到.tar.gz格式备份文件，使用tar解压"), "INFO")
		err = extractWithTarGz(backupFilePath, tempWorldDir)
		// 如果tar解压失败，尝试使用7z解压
		if err != nil {
			pluginPrint(T("tar解压失败，尝试使用7z解压"), "WARNING")
			err = extractWith7z(backupFilePath, tempWorldDir)
		}
	} else {
		// 默认使用配置中的设置
		compressionMethod := pluginConfig.Compression.Method
		if compressionMethod == "" {
			compressionMethod = "zip" // 默认使用zip
		}

		switch compressionMethod {
		case "7z", "zip":
			pluginPrint(T("使用配置中的7z解压"), "INFO")
			err = extractWith7z(backupFilePath, tempWorldDir)
		case "tar":
			pluginPrint(T("使用配置中的tar解压"), "INFO")
			err = extractWithTarGz(backupFilePath, tempWorldDir)
		default:
			// 默认使用7z解压
			pluginPrint(T("使用默认的7z解压"), "INFO")
			err = extractWith7z(backupFilePath, tempWorldDir)
		}
	}

	if err != nil {
		pluginPrint(T("解压失败: %v", err), "ERROR")
		os.Exit(1)
	}

	pluginPrint(strings.Repeat("=", 60), "INFO")

	// 删除现有的世界目录
	currentWorldDir := filepath.Join(worldsDir, restoreInfo.WorldName)
	if _, err := os.Stat(currentWorldDir); err == nil {
		if err := removeDir(currentWorldDir); err != nil {
			pluginPrint(T("删除旧世界目录失败: %v", err), "ERROR")
			// 继续执行
		}
	}

	pluginPrint(strings.Repeat("=", 60), "INFO")

	// 复制文件从临时目录到目标目录
	pluginPrint(T("开始复制文件..."), "INFO")
	pluginPrint(T("复制目标: %s ==> %s", tempWorldDir, worldsDir), "INFO")
	pluginPrint(T("使用 %d 个goroutine进行文件复制", globalConfig.MaxWorkers), "INFO")

	if err := copyDirWithProgress(tempWorldDir, worldsDir, globalConfig.MaxWorkers); err != nil {
		pluginPrint(T("文件复制失败: %v", err), "ERROR")
		os.Exit(1)
	}

	pluginPrint(T("文件复制完成"), "SUCCESS")
	pluginPrint(strings.Repeat("=", 60), "INFO")

	pluginPrint(T("备份恢复完成"), "SUCCESS")
	pluginPrint(strings.Repeat("=", 60), "INFO")

	// 重启服务器
	restartServer()
	os.Exit(0)
}
