from datetime import datetime
import logging
import os

class Logger:
    def __init__(self, filename: str = ''):
        self.__logger = self.__get_logger(filename=filename)

    def log_debug_msg(self, msg: str):
        self.__logger.debug(msg)
            
    def log_error_msg(self, msg: str):
        self.__logger.exception(msg)

    def __get_logger(self, name: str = 'root',
                   log_parent_directory: str = 'C:/Users/John/Downloads/Trade History/Scanner',
                   filename = '',
                   level: int = logging.DEBUG,
                   display_format: str = '\r%(asctime)s - %(message)s (%(levelname)s)',
                   date_format: str = '%m/%d/%Y %I:%M:%S %p'):
        log_date = datetime.now().strftime('%Y%m%d')
        log_filename = filename + 'scanner_log_' + log_date + '.txt' if filename else 'scanner_log_' + log_date + '.txt'
        log_dir = log_parent_directory + "/" + log_filename
        if not os.path.exists(os.path.dirname(log_dir)) and os.path.dirname(log_dir):
            os.makedirs(os.path.dirname(log_dir))

        logger = logging.getLogger(name)
        handler = logging.FileHandler(log_dir)
        logger.setLevel(level)

        if not len(logger.handlers):
            formatter = logging.Formatter(display_format, datefmt=date_format)
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger