import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="endstone-easybackuper",
    version="0.4.3.2",
    author="MengHanLOVE",
    url='https://github.com/MengHanLOVE1027',
    author_email="2193438288@qq.com",
    description="一个基于 EndStone 的轻量级、高性能、功能全面的Minecraft服务器热备份插件 / A lightweight, high-performance, and feature-rich hot backup plugin for Minecraft servers based on EndStone.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
)
