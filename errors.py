class InstrumentException(Exception):
    """仪器相关异常，如仪器不存在
    """
    pass


class ReserveException(Exception):
    """ReserveTem中的异常，如调用顺序不符合要求
    """
    pass
