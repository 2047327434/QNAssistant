"""默认话术文件初始化（txt格式）"""
import os

DEFAULT_PHRASES_TXT = """[问候语]
欢迎光临 = 亲，欢迎光临！有什么可以帮您的吗？
感谢咨询 = 感谢咨询，祝您生活愉快！有问题随时联系我们~

[物流相关]
发货时间 = 亲，我们会尽快为您安排发货哦~
物流查询 = 亲，您可以在订单详情页查看物流信息，也可以告诉我订单号帮您查询~

[售后处理]
质量问题 = 亲，非常抱歉给您带来不便！请提供照片和订单号，我们马上为您处理~
退换货 = 亲，如需退换货请在订单页面申请，我们会尽快为您处理~
"""


def get_app_root():
    """返回工具根目录：开发模式为 main.py 所在目录，打包后为 exe 所在目录。"""
    import sys

    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ensure_phrases_file(app_root=None):
    """确保工具根目录下存在 phrases.txt。

    关键场景：用户只把 QianniuAssistant.exe 复制到任意电脑目录下运行时，
    该目录可能没有 phrases.txt。此函数会在 exe 同目录自动创建预置话术文件。
    """
    root = os.path.abspath(app_root or get_app_root())
    os.makedirs(root, exist_ok=True)
    phrases_path = os.path.join(root, "phrases.txt")

    if not os.path.isfile(phrases_path):
        with open(phrases_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(DEFAULT_PHRASES_TXT.strip() + "\n")

    return phrases_path


def phrases_file_exists(app_root=None):
    """检查工具根目录下是否已经存在 phrases.txt。"""
    root = os.path.abspath(app_root or get_app_root())
    return os.path.isfile(os.path.join(root, "phrases.txt"))
