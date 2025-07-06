import logging
import logging.handlers
import os


def setup_logging():
    """配置日志系统"""
    # 创建logs目录
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
        print(f"📁 创建日志目录: {logs_dir}")

    # 创建根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # 清除现有的处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 1. 所有级别日志文件 (DEBUG及以上)
    all_handler = logging.handlers.RotatingFileHandler(
        os.path.join(logs_dir, 'all.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    all_handler.setLevel(logging.DEBUG)
    all_handler.setFormatter(formatter)
    root_logger.addHandler(all_handler)

    # 2. 警告级别日志文件 (WARNING及以上)
    warning_handler = logging.handlers.RotatingFileHandler(
        os.path.join(logs_dir, 'warning.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    warning_handler.setLevel(logging.WARNING)
    warning_handler.setFormatter(formatter)
    root_logger.addHandler(warning_handler)

    # 3. 错误级别日志文件 (ERROR及以上)
    error_handler = logging.handlers.RotatingFileHandler(
        os.path.join(logs_dir, 'error.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)

    # 4. 控制台输出 (INFO及以上)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # 记录日志配置完成
    logging.info("📝 日志系统配置完成")
    logging.info(f"📂 日志文件位置: {os.path.abspath(logs_dir)}")
    logging.info("📋 日志级别配置:")
    logging.info("  - all.log: 所有级别日志 (DEBUG+)")
    logging.info("  - warning.log: 警告级别日志 (WARNING+)")
    logging.info("  - error.log: 错误级别日志 (ERROR+)")
    logging.info("  - 控制台: 信息级别日志 (INFO+)")


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
