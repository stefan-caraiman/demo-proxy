#! /usr/bin/env python
"""DemoProxy install script."""

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


setup(
    name="demo-proxy",
    version="0.1.1",
    description="A demo proxy",
    long_description=open("README.md").read(),
    author="Stefan Caraiman",
    url="https://github.com/stefan-caraiman/demo-proxy",
    packages=["demo_proxy", "demo_proxy.client", "demo_proxy.common"],
    scripts=["scripts/demo_proxy"],
    requires=open("requirements.txt").readlines(),
)
