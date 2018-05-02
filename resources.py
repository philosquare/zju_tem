import datetime

instruments = [
    dict(
        name='OLD_F20',
        cn_name='场发射透射电镜F20-118（老F20）',
        instrument_id='28ad18ae3ebb4f91b1d52553019ca381',
        reserve_weekday=5,
        reserve_time=datetime.time(hour=12)
    ), dict(
        name='NEW_F20',
        cn_name='场发射透射电镜F20-112（新F20）',
        instrument_id='563e690aae7b41dfb6da1880f291e65b',
        reserve_weekday=5,
        reserve_time=datetime.time(hour=12)
    ), dict(
        name='FIB',
        cn_name='双束聚焦微纳加工仪FIB',
        instrument_id='23ba4d2d9470434a905b4049ef457648',
        reserve_weekday=0,
        reserve_time=datetime.time(hour=8)
    )]
