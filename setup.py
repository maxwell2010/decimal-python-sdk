from setuptools import setup, find_packages

setup(
    name="decimal-python-sdk",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "aiohttp",
        "python-dotenv",
    ],
)
