"""
环境验证脚本
验证 Glimpse 项目的 Python 版本和依赖安装
"""
import sys


def test_python_version():
    """测试 Python 版本"""
    print("=== 测试 Python 版本 ===")
    version = sys.version_info
    print(f"Python版本: {version.major}.{version.minor}.{version.micro}")

    if version.major == 3 and version.minor >= 10:
        print(f"OK: Python 版本满足要求 (3.{version.minor}.{version.micro})")
        return True
    else:
        print("FAIL: Python 版本需要 3.10+")
        return False


def test_dependencies():
    """测试依赖安装情况"""
    print("\n=== 测试依赖安装 ===")

    package_import_map = {
        'PySide6': 'PySide6',
        'chromadb': 'chromadb',
        'sentence-transformers': 'sentence_transformers',
        'transformers': 'transformers',
        'huggingface-hub': 'huggingface_hub',
        'tokenizers': 'tokenizers',
        'numpy': 'numpy',
        'mss': 'mss',
        'Pillow': 'PIL',
        'pynput': 'pynput',
        'rapidocr-onnxruntime': 'rapidocr_onnxruntime',
        'openai': 'openai',
        'requests': 'requests',
        'python-dotenv': 'dotenv',
        'psutil': 'psutil',
        'python-dateutil': 'dateutil',
        'pytest': 'pytest',
    }

    missing_packages = []

    for package, import_name in package_import_map.items():
        try:
            module = __import__(import_name)
            version = getattr(module, "__version__", "unknown")
            print(f"OK: {package} (版本: {version})")
        except ImportError:
            missing_packages.append(package)
            print(f"FAIL: {package} 未安装")

    if missing_packages:
        print(f"\nERROR: 缺少依赖: {', '.join(missing_packages)}")
        print("请运行: pip install -r requirements.txt")
        return False
    else:
        print("\nOK: 所有依赖已安装")
        return True


def test_environment_vars():
    """测试环境变量配置"""
    print("\n=== 测试环境变量 ===")

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("WARN: python-dotenv 未安装，跳过 .env 加载")
        return True

    api_key = os.environ.get('OPENAI_API_KEY', '')
    if api_key:
        print(f"OK: OPENAI_API_KEY 已配置")
        return True
    else:
        print("WARN: OPENAI_API_KEY 未配置（可运行后设置）")
        return True


def main():
    """主测试函数"""
    print("=== Glimpse 环境验证 ===\n")

    results = [
        test_python_version(),
        test_dependencies(),
        test_environment_vars(),
    ]

    print("\n" + "="*40)
    passed = sum(1 for r in results if r)
    print(f"结果: {passed}/{len(results)} 测试通过")

    if all(results):
        print("OK: 环境验证通过")
        return 0
    else:
        print("FAIL: 部分验证失败")
        return 1


if __name__ == "__main__":
    import os
    sys.exit(main())
