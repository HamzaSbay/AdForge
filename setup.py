from setuptools import setup, find_packages

setup(
    name="adforge",
    version="0.1.0",
    author="AdForge Contributors",
    description="Custom local AI-powered video ad production tool",
    long_description=open("README.md", "r", encoding="utf-8").read() if open("README.md", "r").readable() else "",
    long_description_content_type="text/markdown",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "fastapi>=0.100.0",
        "uvicorn>=0.20.0",
        "python-dotenv>=1.0.0",
        "google-generativeai>=0.3.0",
        "requests>=2.31.0",
        "pydantic>=2.0.0",
        "python-multipart>=0.0.6",
        "aiofiles>=23.0.0",
        "Pillow>=10.0.0",
        "pyttsx3>=2.90",
        "PyYAML>=6.0"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
)
