"""
测试火山引擎 Ark API 连通性
使用当前 settings.json 中的配置进行测试
"""
import json
import sys
from pathlib import Path

# 加载配置
settings_path = Path(__file__).parent / "GlimpseData" / "config" / "settings.json"
if not settings_path.exists():
    print(f"ERROR: 配置文件不存在: {settings_path}")
    sys.exit(1)

with open(settings_path, 'r', encoding='utf-8') as f:
    settings = json.load(f)

ai_config = settings.get("ai", {})
base_url = ai_config.get("base_url", "")
api_key = ai_config.get("api_key", "")
model = ai_config.get("model", "")
timeout = ai_config.get("timeout", 30)

print("=== 当前 AI 配置 ===")
print(f"base_url: {base_url}")
print(f"api_key:  {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else ''} (长度: {len(api_key)})")
print(f"model:    {model}")
print(f"timeout:  {timeout}")
print()

# 测试 1: 验证 openai 库可用
try:
    import openai
    print(f"✓ openai 库版本: {openai.__version__}")
except ImportError:
    print("✗ openai 库未安装")
    sys.exit(1)

# 测试 2: 尝试获取模型列表（验证 API Key 和 base_url）
print("\n=== 测试 1: 获取模型列表 ===")
print("这可以验证 API Key 是否正确、base_url 是否可访问...")
try:
    client = openai.OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
    )
    models = client.models.list()
    print(f"✓ 连接成功！可用模型数: {len(models.data)}")
    for m in models.data[:5]:
        print(f"  - {m.id}")
    if len(models.data) > 5:
        print(f"  ... 还有 {len(models.data) - 5} 个")
except Exception as e:
    print(f"✗ 连接失败: {type(e).__name__}")
    print(f"  错误信息: {e}")
    print()
    print("可能的原因:")
    print("  1. API Key 错误（当前看起来是端点 ID，不是 API Key）")
    print("  2. base_url 不可访问（网络问题）")
    print("  3. 模型端点未创建或已删除")

# 测试 3: 尝试简单的 Chat Completion
print("\n=== 测试 2: 简单 Chat Completion ===")
try:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "你好，这是一个测试"}],
        max_tokens=50,
    )
    content = response.choices[0].message.content
    print(f"✓ 请求成功！")
    print(f"  回复: {content[:100]}...")
except Exception as e:
    print(f"✗ 请求失败: {type(e).__name__}")
    print(f"  错误信息: {e}")
    print()
    print("可能的原因:")
    print("  1. 端点 ID（model）不存在或已删除")
    print("  2. 端点未启用")
    print("  3. API Key 没有调用该端点的权限")

print("\n=== 测试完成 ===")
