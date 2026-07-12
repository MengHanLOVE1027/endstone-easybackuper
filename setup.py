import re
import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("src/endstone_easybackuper/easybackuper_plugin.py", "r") as f:
    m = re.search(r'plugin_version\s*=\s*"(.+?)"', f.read())
    version = m.group(1) if m else "0.0.0"

setuptools.setup(
    name="endstone-easybackuper",
    version=version,
    author="MengHanLOVE",
    url='https://github.com/MengHanLOVE1027',
    author_email="2193438288@qq.com",
    description="一个基于 EndStone 的轻量级、高性能、功能全面的Minecraft服务器热备份插件 / A lightweight, high-performance, and feature-rich hot backup plugin for Minecraft servers based on EndStone.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
)
