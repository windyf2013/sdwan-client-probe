import logging
import sys

from sdwan_analyzer.config import LOG_LEVEL, TEST_MODE


def get_logger(name: str) -> logging.Logger:
    """获取日志记录器

    Args:
        name: 日志记录器名称

    Returns:
        logging.Logger: 配置好的日志记录器
    """
    logger = logging.getLogger(name)
    
    # 只有在测试模式下才输出日志
    if TEST_MODE:
        # 配置日志级别
        logger.setLevel(getattr(logging, LOG_LEVEL))
        
        # 检查是否已经有处理器
        if not logger.handlers:
            # 创建控制台处理器
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(getattr(logging, LOG_LEVEL))
            
            # 创建日志格式
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            
            # 添加处理器到日志记录器
            logger.addHandler(handler)
    else:
        # 非测试模式下禁用日志
        logger.setLevel(logging.CRITICAL)
    
    return logger