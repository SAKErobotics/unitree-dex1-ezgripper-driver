#!/usr/bin/env python3
"""
Setup script for Unitree Dex1 EZGripper Driver
"""

from setuptools import setup, find_packages
import os

# Read README
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements
with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="unitree-dex1-ezgripper-driver",
    version="1.0.0",
    author="SAKE Robotics",
    author_email="info@sakerobotics.com",
    description="Drop-in replacement for Unitree Dex1 gripper using SAKE Robotics EZGripper",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/SAKErobotics/unitree-dex1-ezgripper-driver",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Robotics",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "unitree-dex1-ezgripper-driver=unitree_dex1_ezgripper_driver:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.md", "*.txt"],
    },
)
