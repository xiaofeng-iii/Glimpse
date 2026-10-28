from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def read_declared_dependencies() -> list[str]:
    requirements = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    return [requirements, pyproject]


def test_torch_stack_is_not_declared():
    """嵌入推理已切 ONNX：torch 系依赖不得回流（安装体积 400MB 级回归守卫）。"""
    for content in read_declared_dependencies():
        for package in ("sentence-transformers", "transformers", "huggingface-hub", "torch", "nltk"):
            assert package not in content, f"{package} 不应再出现在依赖声明中"


def test_onnx_embedding_stack_is_pinned():
    """ONNX 嵌入推理依赖保持钉版。"""
    for content in read_declared_dependencies():
        assert "onnxruntime==1.23.2" in content
        assert "tokenizers==0.13.3" in content
