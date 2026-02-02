
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

// Config struct definition
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

// RestoreInfo struct
type RestoreInfo struct {
	BackupFile string
	ServerDir  string
	WorldName  string
}

// Global variables
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
)

// pluginPrint custom log output
func pluginPrint(text string, level string) {
	// If it's DEBUG level and DEBUG mode is not enabled, don't output
	if level == "DEBUG" && !globalConfig.Debug {
		return
	}

	// Get current time
	currentTime := time.Now().Format("2006-01-02 15:04:05")

	// Log level color mapping
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

	// Output to console
	fmt.Println(levelText + text)

	// Output to log file
	if logger != nil {
		logPrefix := fmt.Sprintf("[%s] [%s] ", currentTime, level)
		logger.Println(logPrefix + text)
	}
}

// setupLogging configure logging
func setupLogging(serverDir string) error {
	logDir := filepath.Join(serverDir, "logs", pluginName)
	err := os.MkdirAll(logDir, 0755)
	if err != nil {
		return fmt.Errorf("Failed to create log directory: %v", err)
	}

	logFileName := fmt.Sprintf("%s_restore_%s.log", pluginNameSmall,
		time.Now().Format("20060102"))
	logFilePath := filepath.Join(logDir, logFileName)

	logFile, err = os.OpenFile(logFilePath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err != nil {
		return fmt.Errorf("Failed to open log file: %v", err)
	}

	// Set log level
	logLevel := log.LstdFlags
	if globalConfig.Debug {
		// In debug mode, add more detailed log information
		logger = log.New(logFile, "", logLevel|log.Lshortfile)
	} else {
		logger = log.New(logFile, "", logLevel)
	}

	return nil
}

// loadConfig load configuration file
func loadConfig(serverDir string) error {
	// Try multiple possible configuration file paths
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
		pluginPrint("All possible configuration file paths do not exist, using default configuration", "WARNING")
		pluginConfig = PluginConfig{
			Compression: CompressionConfig{
				Method:    "zip",
				Exe7zPath: "./plugins/EasyBackuper/7za.exe",
				Formats:   make(map[string]CompressionFormat),
			},
			MaxWorkers: defaultMaxWorkers,
		}
		// Initialize default formats
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

	pluginPrint(fmt.Sprintf("Using configuration file path: %s", configPath), "INFO")

	// Read configuration file
	data, err := os.ReadFile(configPath)
	if err != nil {
		return fmt.Errorf("Failed to read configuration file: %v", err)
	}

	// Parse JSON
	var config map[string]interface{}
	if err := json.Unmarshal(data, &config); err != nil {
		return fmt.Errorf("Failed to parse configuration file: %v", err)
	}

	// Initialize default configuration
	pluginConfig = PluginConfig{
		Compression: CompressionConfig{
			Method:    "zip",
			Exe7zPath: "./plugins/EasyBackuper/7za.exe",
			Formats:   make(map[string]CompressionFormat),
		},
		MaxWorkers: defaultMaxWorkers,
	}
	// Initialize default formats
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

	// Set plugin configuration
	if compressionData, ok := config["Compression"].(map[string]interface{}); ok {
		if method, ok := compressionData["method"].(string); ok {
			pluginConfig.Compression.Method = method
		}
		if exe7zPath, ok := compressionData["exe_7z_path"].(string); ok {
			pluginConfig.Compression.Exe7zPath = exe7zPath
		}
		// Ensure Formats map is initialized
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

	// Parse Restore configuration
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

	pluginPrint(fmt.Sprintf("Successfully loaded configuration file: %s", configPath), "SUCCESS")
	pluginPrint(fmt.Sprintf("DEBUG mode: %v", globalConfig.Debug), "INFO")
	pluginPrint(fmt.Sprintf("MaxWorkers: %d", globalConfig.MaxWorkers), "INFO")

	return nil
}

// copyFileWithProgress copy file
func copyFileWithProgress(src, dst string) error {
	pluginPrint(fmt.Sprintf("Copying file:%s --> %s", fmt.Sprint(src), fmt.Sprint(dst)), "DEBUG")

	sourceFile, err := os.Open(src)
	if err != nil {
		return fmt.Errorf("Failed to open source file: %v", err)
	}
	defer sourceFile.Close()

	// Create destination directory
	dstDir := filepath.Dir(dst)
	if err := os.MkdirAll(dstDir, 0755); err != nil {
		return fmt.Errorf("Failed to create destination directory: %v", err)
	}

	destinationFile, err := os.Create(dst)
	if err != nil {
		return fmt.Errorf("Failed to create destination file: %v", err)
	}
	defer destinationFile.Close()

	_, err = io.Copy(destinationFile, sourceFile)
	if err != nil {
		return fmt.Errorf("Failed to copy file content: %v", err)
	}

	// Copy file permissions
	sourceInfo, err := sourceFile.Stat()
	if err == nil {
		os.Chmod(dst, sourceInfo.Mode())
	}

	return nil
}

// copyDirWithProgress multi-goroutine directory copy
func copyDirWithProgress(src, dst string, maxThreads int) error {
	if _, err := os.Stat(dst); os.IsNotExist(err) {
		if err := os.MkdirAll(dst, 0755); err != nil {
			return fmt.Errorf("Failed to create destination directory: %v", err)
		}
		pluginPrint(fmt.Sprintf("Created directory: %s", dst), "DEBUG")
	}

	// Collect all files
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
		return fmt.Errorf("Failed to traverse source directory: %v", err)
	}

	// First create all directories
	for _, dir := range dirs {
		relPath, err := filepath.Rel(src, dir)
		if err != nil {
			return fmt.Errorf("Failed to calculate relative path: %v", err)
		}
		dstDir := filepath.Join(dst, relPath)
		if _, err := os.Stat(dstDir); os.IsNotExist(err) {
			if err := os.MkdirAll(dstDir, 0755); err != nil {
				return fmt.Errorf("Failed to create directory: %v", err)
			}
			pluginPrint(fmt.Sprintf("Created directory: %s ==> %s", dir, dstDir), "DEBUG")
		}
	}

	// Use worker pool to copy files
	type copyTask struct {
		src string
		dst string
	}

	tasks := make(chan copyTask, len(files))
	errors := make(chan error, len(files))
	var wg sync.WaitGroup

	// Start workers
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

	// Send tasks
	for _, file := range files {
		relPath, err := filepath.Rel(src, file)
		if err != nil {
			errors <- fmt.Errorf("Failed to calculate relative path: %v", err)
			continue
		}
		dstPath := filepath.Join(dst, relPath)
		tasks <- copyTask{src: file, dst: dstPath}
	}
	close(tasks)

	wg.Wait()

	// Check for errors
	select {
	case err := <-errors:
		return err
	default:
		return nil
	}
}

// extractWith7z extract using 7z
func extractWith7z(archivePath, destDir string) error {
	pluginPrint(fmt.Sprintf("Extracting with 7z: %s", archivePath), "INFO")
	pluginPrint(fmt.Sprintf("Extracting to: %s --> %s", archivePath, destDir), "INFO")

	var cmd *exec.Cmd
	if runtime.GOOS == "windows" {
		cmd = exec.Command(pluginConfig.Compression.Exe7zPath, "x", archivePath, "-o"+destDir, "-y")
	} else {
		cmd = exec.Command("7z", "x", archivePath, "-o"+destDir, "-y")
	}

	output, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("7z extraction failed: %v\nOutput: %s", err, string(output))
	}

	pluginPrint("7z extraction completed", "SUCCESS")
	return nil
}

// extractWithTarGz extract using tar
func extractWithTarGz(archivePath, destDir string) error {
	pluginPrint(fmt.Sprintf("Extracting with tar: %s", archivePath), "INFO")
	pluginPrint(fmt.Sprintf("Extracting to: %s --> %s", archivePath, destDir), "INFO")

	file, err := os.Open(archivePath)
	if err != nil {
		return fmt.Errorf("Failed to open archive file: %v", err)
	}
	defer file.Close()

	gzReader, err := gzip.NewReader(file)
	if err != nil {
		return fmt.Errorf("Failed to create gzip reader: %v", err)
	}
	defer gzReader.Close()

	tarReader := tar.NewReader(gzReader)

	for {
		header, err := tarReader.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			return fmt.Errorf("Failed to read tar header: %v", err)
		}

		targetPath := filepath.Join(destDir, header.Name)

		switch header.Typeflag {
		case tar.TypeDir:
			if err := os.MkdirAll(targetPath, 0755); err != nil {
				return fmt.Errorf("Failed to create directory: %v", err)
			}
		case tar.TypeReg:
			// Create directory
			if err := os.MkdirAll(filepath.Dir(targetPath), 0755); err != nil {
				return fmt.Errorf("Failed to create file directory: %v", err)
			}

			// Create file
			outFile, err := os.Create(targetPath)
			if err != nil {
				return fmt.Errorf("Failed to create file: %v", err)
			}

			if _, err := io.Copy(outFile, tarReader); err != nil {
				outFile.Close()
				return fmt.Errorf("Failed to write file: %v", err)
			}
			outFile.Close()

			// Set file permissions
			if err := os.Chmod(targetPath, os.FileMode(header.Mode)); err != nil {
				return fmt.Errorf("Failed to set file permissions: %v", err)
			}
		}
	}

	pluginPrint("tar extraction completed", "SUCCESS")
	return nil
}

// compressWith7z compress using 7z
func compressWith7z(srcDir, destFile string) error {
	pluginPrint(fmt.Sprintf("Compressing with 7z: %s", srcDir), "INFO")
	pluginPrint(fmt.Sprintf("Compressing to: %s --> %s", srcDir, destFile), "INFO")

	var cmd *exec.Cmd
	if runtime.GOOS == "windows" {
		cmd = exec.Command(pluginConfig.Compression.Exe7zPath, "a", destFile, srcDir+string(filepath.Separator)+"*", "-y")
	} else {
		cmd = exec.Command("7z", "a", destFile, srcDir+string(filepath.Separator)+"*", "-y")
	}

	output, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("7z compression failed: %v\nOutput: %s", err, string(output))
	}

	pluginPrint("7z compression completed", "SUCCESS")
	pluginPrint(fmt.Sprintf("Backup file saved: %s", destFile), "SUCCESS")
	return nil
}

// compressWithTarGz compress using tar
func compressWithTarGz(srcDir, destFile string) error {
	pluginPrint(fmt.Sprintf("Compressing with tar: %s", srcDir), "INFO")
	pluginPrint(fmt.Sprintf("Compressing to: %s --> %s", srcDir, destFile), "INFO")

	file, err := os.Create(destFile)
	if err != nil {
		return fmt.Errorf("Failed to create archive file: %v", err)
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

		// Create tar header
		header, err := tar.FileInfoHeader(info, "")
		if err != nil {
			return err
		}

		// Adjust path
		relPath, err := filepath.Rel(baseDir, path)
		if err != nil {
			return err
		}
		header.Name = filepath.Join(dirName, relPath)

		// Write header
		if err := tarWriter.WriteHeader(header); err != nil {
			return err
		}

		// If it's a file, write content
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
		return fmt.Errorf("Error occurred during compression: %v", err)
	}

	pluginPrint("tar compression completed", "SUCCESS")
	pluginPrint(fmt.Sprintf("Backup file saved: %s", destFile), "SUCCESS")
	return nil
}

// isProcessRunning check if process is running
func isProcessRunning(processName string) bool {
	processes, err := ps.Processes()
	if err != nil {
		pluginPrint(fmt.Sprintf("Failed to get process list: %v", err), "ERROR")
		return false
	}

	for _, process := range processes {
		if strings.Contains(strings.ToLower(process.Executable()), strings.ToLower(processName)) {
			return true
		}
	}
	return false
}

// waitForProcessExit wait for process to exit
func waitForProcessExit(processName string) {
	pluginPrint(fmt.Sprintf("Detected %s process is running, waiting for server to shutdown", processName), "WARNING")

	for isProcessRunning(processName) {
		time.Sleep(1 * time.Second)
	}

	pluginPrint("Server has been shut down", "SUCCESS")
}

// removeDir remove directory
func removeDir(dir string) error {
	pluginPrint(fmt.Sprintf("Removing directory: %s", dir), "INFO")

	err := filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}

		// Set write permission
		os.Chmod(path, 0666)

		if !info.IsDir() {
			pluginPrint(fmt.Sprintf("Deleting file: %s --> [Deleted]", path), "DEBUG")
		}
		return nil
	})

	if err != nil {
		return fmt.Errorf("Failed to traverse directory: %v", err)
	}

	// Remove entire directory
	err = os.RemoveAll(dir)
	if err != nil {
		return fmt.Errorf("Failed to remove directory: %v", err)
	}

	pluginPrint("Directory removal completed", "SUCCESS")
	return nil
}

// backupCurrentWorld backup current world
func backupCurrentWorld() error {
	pluginPrint("Configured to automatically backup current world before restore", "INFO")

	// Get current time as part of backup name
	currentTime := time.Now().Format("20060102_150405")
	backupName := fmt.Sprintf("before_restore_%s", currentTime)

	// Get backup directory
	backupDir := "./backup"
	if err := os.MkdirAll(backupDir, 0755); err != nil {
		return fmt.Errorf("Failed to create backup directory: %v", err)
	}

	// Create temporary directory
	tempBackupDir := filepath.Join(restoreInfo.ServerDir, "temp_easybackuper_backup")
	if _, err := os.Stat(tempBackupDir); err == nil {
		os.RemoveAll(tempBackupDir)
	}

	if err := os.MkdirAll(tempBackupDir, 0755); err != nil {
		return fmt.Errorf("Failed to create temporary backup directory: %v", err)
	}
	defer os.RemoveAll(tempBackupDir)

	// Copy world directory to temporary directory
	worldsDir := filepath.Join(restoreInfo.ServerDir, "worlds")
	tempWorldBackupDir := filepath.Join(tempBackupDir, restoreInfo.WorldName)

	pluginPrint(fmt.Sprintf("Backing up current world: %s", worldsDir), "INFO")

	if err := copyDirWithProgress(worldsDir, tempWorldBackupDir, globalConfig.MaxWorkers); err != nil {
		return fmt.Errorf("Failed to backup world directory: %v", err)
	}

	// Choose compression method based on configuration
	var oldBackupFilePath string
	compressionMethod := pluginConfig.Compression.Method
	if compressionMethod == "" {
		compressionMethod = "zip" // Default to zip
	}

	// Get file extension
	var fileExtension string
	if format, ok := pluginConfig.Compression.Formats[compressionMethod]; ok {
		fileExtension = format.Extension
	} else {
		fileExtension = ".zip" // Default extension
	}

	oldBackupFilePath = filepath.Join(backupDir, backupName+fileExtension)

	// Choose compression function based on compression method
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
		// Default to 7z compression
		if err := compressWith7z(tempWorldBackupDir, oldBackupFilePath); err != nil {
			return err
		}
	}

	pluginPrint("Pre-restore backup completed", "SUCCESS")
	return nil
}

// restartServer restart server
func restartServer() {
	restartConfig := pluginConfig.Restore.Config.RestartServer
	if !restartConfig.Status {
		pluginPrint("Configured not to automatically restart server", "INFO")
		return
	}

	pluginPrint("Configured to automatically restart server after restore", "INFO")
	waitTime := restartConfig.WaitTimeS
	if waitTime == 0 {
		waitTime = 10
	}

	pluginPrint(fmt.Sprintf("Waiting %d seconds before starting server...", waitTime), "INFO")
	time.Sleep(time.Duration(waitTime) * time.Second)

	startScriptPath := restartConfig.StartScriptPath
	if startScriptPath == "" {
		startScriptPath = "./start.bat"
	}

	pluginPrint(fmt.Sprintf("Start script path: %s", startScriptPath), "INFO")

	// Parse absolute path of start script
	var startScriptFullPath string
	if filepath.IsAbs(startScriptPath) {
		startScriptFullPath = startScriptPath
	} else {
		startScriptFullPath = filepath.Join(restoreInfo.ServerDir, startScriptPath)
	}

	pluginPrint(fmt.Sprintf("Server directory: %s", restoreInfo.ServerDir), "INFO")
	pluginPrint(fmt.Sprintf("Full path of start script: %s", startScriptFullPath), "INFO")

	// Execute start script
	pluginPrint("Starting server...", "INFO")

	// Check if script file exists
	if _, err := os.Stat(startScriptFullPath); os.IsNotExist(err) {
		pluginPrint(fmt.Sprintf("Start script does not exist: %s", startScriptFullPath), "ERROR")
		return
	}

	var cmd *exec.Cmd
	if runtime.GOOS == "windows" {
		// On Windows, use start command to open a new window to execute batch file
		cmd_path := os.Getenv("PATH")
		pluginPrint(cmd_path, "INFO")
		cmd = exec.Command("C:\\Windows\\System32\\cmd.exe", "/c", "start", "/I", startScriptFullPath)
	} else {
		// On Linux/Mac, execute script file directly
		// cmd = exec.Command(startScriptFullPath)
		// Not yet supported on Linux/Mac
		pluginPrint("Linux/Mac not yet supported", "ERROR")
		pluginPrint("Please start server manually", "INFO")
		return
	}

	// Set working directory
	cmd.Dir = restoreInfo.ServerDir

	// Print command info for debugging
	pluginPrint(fmt.Sprintf("Executing command: %s", cmd.String()), "INFO")
	pluginPrint(fmt.Sprintf("Working directory: %s", cmd.Dir), "INFO")

	// Execute command and wait for completion
	if err := cmd.Run(); err != nil {
		pluginPrint(fmt.Sprintf("Failed to start server: %v", err), "ERROR")
	} else {
		pluginPrint("Server start command has been executed", "SUCCESS")
	}
}

// main main function
func main() {
	// Parse command line arguments
	backupFile := flag.String("backup", "", "Backup file path")
	serverDir := flag.String("server", "", "Server directory")
	worldName := flag.String("world", "", "World name")
	flag.Parse()

	// Check required parameters
	if *backupFile == "" || *serverDir == "" || *worldName == "" {
		fmt.Println("Usage: easybackuper -backup <backup_file> -server <server_directory> -world <world_name>")
		fmt.Println("Missing required parameters")
		if runtime.GOOS == "windows" {
			fmt.Println("Press any key to continue...")
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

	// Load configuration
	if err := loadConfig(restoreInfo.ServerDir); err != nil {
		fmt.Printf("Failed to load configuration: %v\n", err)
		os.Exit(1)
	}

	// Setup logging
	if err := setupLogging(restoreInfo.ServerDir); err != nil {
		fmt.Printf("Failed to setup logging: %v\n", err)
		os.Exit(1)
	}
	defer logFile.Close()

	pluginPrint(strings.Repeat("=", 60), "INFO")
	pluginPrint("EasyBackuper Restore Handler Started", "SUCCESS")
	pluginPrint(fmt.Sprintf("Go version: %s", runtime.Version()), "INFO")
	pluginPrint(fmt.Sprintf("Operating system: %s/%s", runtime.GOOS, runtime.GOARCH), "INFO")
	pluginPrint(fmt.Sprintf("Working directory: %s", restoreInfo.ServerDir), "INFO")
	pluginPrint(strings.Repeat("=", 60), "INFO")

	// Change working directory
	if err := os.Chdir(restoreInfo.ServerDir); err != nil {
		pluginPrint(fmt.Sprintf("Failed to change working directory: %v", err), "ERROR")
		os.Exit(1)
	}
	pluginPrint(fmt.Sprintf("Changed working directory to: %s", restoreInfo.ServerDir), "INFO")

	// Check if bedrock_server process is running
	var processName string
	if runtime.GOOS == "windows" {
		processName = "bedrock_server.exe"
	} else {
		processName = "bedrock_server"
	}

	if isProcessRunning(processName) {
		waitForProcessExit(processName)
	} else {
		pluginPrint(fmt.Sprintf("No %s process detected, continuing with restore operation", processName), "INFO")
	}

	pluginPrint(strings.Repeat("=", 60), "INFO")

	// Check if we need to backup current world before restore
	if pluginConfig.Restore.Config.BackupOldWorldBeforeRestore {
		if err := backupCurrentWorld(); err != nil {
			pluginPrint(fmt.Sprintf("Pre-restore backup failed: %v", err), "ERROR")
			// Continue execution, do not terminate
		}
	} else {
		pluginPrint("Configured not to backup current world", "INFO")
	}

	pluginPrint(strings.Repeat("=", 60), "INFO")

	// Restore backup
	pluginPrint("Starting backup restore", "INFO")
	worldsDir := filepath.Join(restoreInfo.ServerDir, "worlds")

	// Create temporary directory for extraction
	tempDir := filepath.Join(restoreInfo.ServerDir, "temp_easybackuper")
	if _, err := os.Stat(tempDir); err == nil {
		os.RemoveAll(tempDir)
	}

	if err := os.MkdirAll(tempDir, 0755); err != nil {
		pluginPrint(fmt.Sprintf("Failed to create temporary directory: %v", err), "ERROR")
		os.Exit(1)
	}
	defer os.RemoveAll(tempDir)

	pluginPrint(fmt.Sprintf("Created temporary directory: %s", tempDir), "INFO")

	tempWorldDir := filepath.Join(tempDir, restoreInfo.WorldName)
	backupFilePath := restoreInfo.BackupFile

	var err error
	// Choose extraction method based on file extension
	if strings.HasSuffix(strings.ToLower(backupFilePath), ".7z") {
		pluginPrint("Detected .7z format backup file, using 7z to extract", "INFO")
		err = extractWith7z(backupFilePath, tempWorldDir)
	} else if strings.HasSuffix(strings.ToLower(backupFilePath), ".zip") {
		pluginPrint("Detected .zip format backup file, using 7z to extract", "INFO")
		err = extractWith7z(backupFilePath, tempWorldDir)
	} else if strings.HasSuffix(strings.ToLower(backupFilePath), ".tar.gz") || strings.HasSuffix(strings.ToLower(backupFilePath), ".tgz") {
		pluginPrint("Detected .tar.gz format backup file, using tar to extract", "INFO")
		err = extractWithTarGz(backupFilePath, tempWorldDir)
		// If tar extraction fails, try using 7z
		if err != nil {
			pluginPrint("tar extraction failed, trying to use 7z to extract", "WARNING")
			err = extractWith7z(backupFilePath, tempWorldDir)
		}
	} else {
		// Default to settings in configuration
		compressionMethod := pluginConfig.Compression.Method
		if compressionMethod == "" {
			compressionMethod = "zip" // Default to zip
		}

		switch compressionMethod {
		case "7z", "zip":
			pluginPrint("Using 7z from configuration to extract", "INFO")
			err = extractWith7z(backupFilePath, tempWorldDir)
		case "tar":
			pluginPrint("Using tar from configuration to extract", "INFO")
			err = extractWithTarGz(backupFilePath, tempWorldDir)
		default:
			// Default to 7z extraction
			pluginPrint("Using default 7z to extract", "INFO")
			err = extractWith7z(backupFilePath, tempWorldDir)
		}
	}

	if err != nil {
		pluginPrint(fmt.Sprintf("Extraction failed: %v", err), "ERROR")
		os.Exit(1)
	}

	pluginPrint(strings.Repeat("=", 60), "INFO")

	// Remove existing world directory
	currentWorldDir := filepath.Join(worldsDir, restoreInfo.WorldName)
	if _, err := os.Stat(currentWorldDir); err == nil {
		if err := removeDir(currentWorldDir); err != nil {
			pluginPrint(fmt.Sprintf("Failed to remove old world directory: %v", err), "ERROR")
			// Continue execution
		}
	}

	pluginPrint(strings.Repeat("=", 60), "INFO")

	// Copy files from temporary directory to target directory
	pluginPrint("Starting file copy...", "INFO")
	pluginPrint(fmt.Sprintf("Copy target: %s ==> %s", tempWorldDir, worldsDir), "INFO")
	pluginPrint(fmt.Sprintf("Using %d goroutines for file copying", globalConfig.MaxWorkers), "INFO")

	if err := copyDirWithProgress(tempWorldDir, worldsDir, globalConfig.MaxWorkers); err != nil {
		pluginPrint(fmt.Sprintf("File copy failed: %v", err), "ERROR")
		os.Exit(1)
	}

	pluginPrint("File copy completed", "SUCCESS")
	pluginPrint(strings.Repeat("=", 60), "INFO")

	pluginPrint("Backup restore completed", "SUCCESS")
	pluginPrint(strings.Repeat("=", 60), "INFO")

	// Restart server
	restartServer()
	os.Exit(0)
}
