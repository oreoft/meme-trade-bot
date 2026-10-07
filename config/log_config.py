import logging
import sys


def setup_logging():
    """配置日志系统：只输出到 stdout，由 docker 负责收集和轮转"""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # 清除现有的处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    root_logger.addHandler(console_handler)

    logging.info("📝 日志系统配置完成（输出到 stdout）")


def test_logging():
    """测试日志功能"""
    logging.debug("这是一条调试信息")
    logging.info("这是一条信息")
    logging.warning("这是一条警告信息")
    logging.error("这是一条错误信息")
    logging.critical("这是一条严重错误信息")


if __name__ == "__main__":
    setup_logging()
    test_logging()
