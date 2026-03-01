
"""
Easy系列插件的 BStats 遥测模块
"""
import json
import platform
import uuid
import threading
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Callable
import psutil
import requests

# 创建bStats专用的logger
bstats_logger = logging.getLogger(f"EasyBackuperBStats")
bstats_logger.setLevel(logging.INFO)

# 添加控制台处理器
if not bstats_logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('[%(name)s] [%(levelname)s] %(message)s')
    console_handler.setFormatter(formatter)
    bstats_logger.addHandler(console_handler)


class BStatsConfig:
    """bStats 配置管理"""

    def __init__(self, config_file: Path):
        self.config_file = config_file
        self.enabled = True
        self.server_uuid = str(uuid.uuid4())
        self.log_errors_enabled = False
        self.log_sent_data_enabled = False
        self.log_response_status_text_enabled = False
        self._load_config()

    def _load_config(self):
        """加载配置文件"""
        try:
            # bstats_logger.info(f"正在加载配置文件: {self.config_file}")
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.enabled = config.get('enabled', True)
                    self.server_uuid = config.get('serverUUID', self.server_uuid)
                    self.log_errors_enabled = config.get('log-errors-enabled', False)
                    self.log_sent_data_enabled = config.get('log-sent-data-enabled', False)
                    self.log_response_status_text_enabled = config.get('log-response-status-text-enabled', False)
                # bstats_logger.info(f"配置文件加载成功")
                bstats_logger.info(f"遥测状态: {'已启用' if self.enabled else '已禁用'}")
            else:
                # bstats_logger.info(f"配置文件不存在,将创建新文件")
                self._save_config()
        except Exception as e:
            bstats_logger.error(f"加载配置失败: {e}")
            import traceback
            bstats_logger.error(f"异常堆栈: {traceback.format_exc()}")

    def _save_config(self):
        """保存配置文件"""
        try:
            # bstats_logger.info(f"正在保存配置文件: {self.config_file}")
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'enabled': self.enabled,
                    'serverUUID': self.server_uuid,
                    'log-errors-enabled': self.log_errors_enabled,
                    'log-sent-data-enabled': self.log_sent_data_enabled,
                    'log-response-status-text-enabled': self.log_response_status_text_enabled
                }, f, indent=4)
            # bstats_logger.info(f"配置文件保存成功")
        except Exception as e:
            bstats_logger.error(f"保存配置失败: {e}")
            import traceback
            bstats_logger.error(f"异常堆栈: {traceback.format_exc()}")


class SimplePie:
    """简单饼图数据收集器"""

    def __init__(self, chart_id: str, value_provider: Callable[[], str]):
        self.chart_id = chart_id
        self.value_provider = value_provider

    def get_data(self) -> Dict[str, Any]:
        """获取图表数据"""
        return {
            'chartId': self.chart_id,
            'data': {
                'value': self.value_provider()
            }
        }


class DrilldownPie:
    """下钻饼图数据收集器"""

    def __init__(self, chart_id: str, data_provider: Callable[[], Dict[str, Dict[str, int]]]):
        self.chart_id = chart_id
        self.data_provider = data_provider

    def get_data(self) -> Dict[str, Any]:
        """获取图表数据"""
        return {
            'chartId': self.chart_id,
            'data': self.data_provider()
        }


class BStats:
    """bStats 遥测主类"""

    def __init__(self, plugin, service_id: int):
        """
        初始化 bStats

        Args:
            plugin: 插件实例
            service_id: bStats 服务ID
        """
        self.plugin = plugin
        self.service_id = service_id
        self.plugin_name = getattr(plugin, 'name', 'Unknown')
        self.plugin_version = getattr(plugin, 'version', 'Unknown')

        # 初始化配置
        try:
            data_folder = getattr(plugin, 'data_folder', None)
            if data_folder is None:
                # 如果没有data_folder属性,使用默认路径
                data_folder = Path("./plugins") / self.plugin_name

            bstats_folder = Path(data_folder) / "bstats"
            # bstats_logger.info(f"配置文件路径: {bstats_folder / 'config.json'}")
            self.config = BStatsConfig(bstats_folder / "config.json")
        except Exception as e:
            bstats_logger.error(f"初始化配置失败: {e}")
            import traceback
            bstats_logger.error(f"异常堆栈: {traceback.format_exc()}")
            raise

        # 自定义图表
        self.custom_charts = []

        # 系统信息缓存
        self.cached_os_name = "Unknown"
        self.cached_os_arch = "Unknown"
        self.cached_os_version = "Unknown"
        self.cached_core_count = 0

        # 探测系统信息
        self._probe_system_info()

        # 提交线程
        self._submit_thread = None
        self._running = False

        # bStats API
        self.platform = "bukkit"
        self.base_url = f"https://bstats.org/api/v2/data/{self.platform}"

        # bstats_logger.info(f"bStats 初始化完成")

    def _probe_system_info(self):
        """探测系统信息"""
        try:
            # 操作系统名称
            os_name = platform.system()
            if os_name == "Windows":
                self.cached_os_name = f"Windows {platform.release()}"
                self.cached_os_version = platform.version()
            elif os_name == "Linux":
                self.cached_os_name = "Linux"
                self.cached_os_version = platform.release()

            # 系统架构
            self.cached_os_arch = platform.machine().lower()

            # CPU 核心数
            self.cached_core_count = psutil.cpu_count(logical=False) or 0

        except Exception as e:
            bstats_logger.warning(f"探测系统信息失败: {e}")

    def add_custom_chart(self, chart):
        """
        添加自定义图表

        Args:
            chart: 图表实例 (SimplePie 或 DrilldownPie)
        """
        self.custom_charts.append(chart)

    def _collect_data(self) -> Dict[str, Any]:
        """
        收集遥测数据

        Returns:
            包含所有遥测数据的字典
        """
        # 获取在线玩家数
        player_amount = 0
        try:
            player_amount = len(self.plugin.server.online_players)
        except:
            pass

        # 获取 Minecraft 版本
        minecraft_version = "Unknown"
        try:
            minecraft_version = self.plugin.server.minecraft_version
        except:
            pass

        # 收集自定义图表数据
        custom_charts_data = []
        for chart in self.custom_charts:
            try:
                custom_charts_data.append(chart.get_data())
            except Exception as e:
                bstats_logger.warning(f"收集图表数据失败: {e}")

        return {
            'serverUUID': self.config.server_uuid,
            'metricsVersion': '2',
            'playerAmount': player_amount,
            'onlineMode': 1,  # EndStone 暂不支持离线模式检测
            'bukkitVersion': minecraft_version,
            'javaVersion': f"Python {platform.python_version()}",
            'osName': self.cached_os_name,
            'osArch': self.cached_os_arch,
            'osVersion': self.cached_os_version,
            'coreCount': self.cached_core_count,
            'service': {
                'id': self.service_id,
                'pluginVersion': self.plugin_version,
                'customCharts': custom_charts_data
            }
        }

    def _submit_data(self):
        """提交数据到 bStats 服务器"""
        if not self.config.enabled:
            bstats_logger.info("遥测模块已禁用，跳过上报。")
            return

        try:
            payload = self._collect_data()

            if self.config.log_sent_data_enabled:
                bstats_logger.info(f"准备上报数据包内容:")
                bstats_logger.info(json.dumps(payload, indent=2))

            bstats_logger.info(f"正在提交遥测数据到 bStats 服务器...")
            response = requests.post(
                self.base_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )

            if response.status_code == 200:
                bstats_logger.info("遥测数据上报成功！")
                if self.config.log_sent_data_enabled:
                    bstats_logger.info(f"响应内容: {response.text if response.text else '(空)'}")
            else:
                bstats_logger.warning(f"上报失败，状态码: {response.status_code}")
                if self.config.log_sent_data_enabled:
                    bstats_logger.warning(f"返回结果: {response.text if response.text else '(空)'}")

        except Exception as e:
            bstats_logger.error(f"网络请求异常: {e}")
            if self.config.log_errors_enabled:
                import traceback
                bstats_logger.error(f"异常堆栈: {traceback.format_exc()}")

    def _submit_loop(self):
        """数据提交循环"""
        # 首次等待 30 秒
        for _ in range(30):
            if not self._running:
                return
            time.sleep(1)

        while self._running:
            try:
                self._submit_data()
            except Exception as e:
                bstats_logger.error(f"提交数据时发生错误: {e}")
                if self.config.log_errors_enabled:
                    import traceback
                    bstats_logger.error(f"异常堆栈: {traceback.format_exc()}")

            # 等待 30 分钟
            for _ in range(30 * 60):
                if not self._running:
                    break
                time.sleep(1)

    def start(self):
        """启动 bStats 遥测"""
        if self._running:
            return

        self._running = True
        self._submit_thread = threading.Thread(target=self._submit_loop, daemon=True)
        self._submit_thread.start()

        # 输出启动日志
        bstats_logger.info(f"{self.plugin_name} 遥测模块已启动。")
        bstats_logger.info(f"首次数据将在 30 秒后发送,之后每 30 分钟发送一次。")
        if self.config.log_sent_data_enabled:
            bstats_logger.info(f"插件ID: {self.service_id}, 插件版本: {self.plugin_version}")
            bstats_logger.info(f"遥测状态: {'已启用' if self.config.enabled else '已禁用'}")
            bstats_logger.info(f"调试模式: {'已启用' if self.config.log_sent_data_enabled else '已禁用'}")

    def shutdown(self):
        """关闭 bStats 遥测"""
        self._running = False
        if self._submit_thread and self._submit_thread.is_alive():
            self._submit_thread.join(timeout=5)

        if self.config.log_sent_data_enabled:
            bstats_logger.info(f"{self.plugin_name} 遥测模块已关闭。")
