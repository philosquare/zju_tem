from errors import InstrumentException
from resources import instruments


class Instrument(object):
    class OneInstrument(object):
        """一个OneInstrument实例表示一个仪器

        不可变类，只有在初始化时可以设置四个属性，分别是：

            str name: 仪器的名称

            str cn_name: 仪器的中文名称

            str instrument_id: 实验仪器的ID，预约的POST数据中用到

            int reserve_weekday: 仪器的预约日期，每周的周几开始预约该仪器
                周一为0，周二为1，周日为6（与datetime.weekday相同）

            datetime.time reserve_time: 仪器预约时间，开始预约该仪器的时间
        """
        # just for IDE can find attributes
        name = cn_name = instrument_id = reserve_weekday = reserve_time = None

        def __init__(self, name, cn_name, instrument_id, reserve_weekday, reserve_time):
            super().__setattr__('name', name)
            super().__setattr__('cn_name', cn_name)
            super().__setattr__('instrument_id', instrument_id)
            super().__setattr__('reserve_weekday', reserve_weekday)
            super().__setattr__('reserve_time', reserve_time)

        def __setattr__(self, key, value):
            raise AttributeError("can't set attribute to a OneInstrument instance after initial")

    name_to_instrument = {}
    id_to_instrument = {}
    instrument_list = []
    for ins_dict in instruments:
        instrument = OneInstrument(**ins_dict)
        name_to_instrument[ins_dict['name']] = instrument
        id_to_instrument[ins_dict['instrument_id']] = instrument
        instrument_list.append(instrument)

    # def __init__(self):
    #     self.name_to_instrument = {}
    #     self.id_to_instrument = {}
    #     self.instrument_list = []
    #     for ins_dict in instruments:
    #         instrument = self.OneInstrument(**ins_dict)
    #         # 真的有用吗
    #         # self.__setattr__(ins_dict['name'], instrument)
    #         self.name_to_instrument[ins_dict['name']] = instrument
    #         self.id_to_instrument[ins_dict['instrument_id']] = instrument
    #         self.instrument_list.append(instrument)

    @staticmethod
    def get(name=None, instrument_id=None):
        if instrument_id:
            instrument = Instrument.id_to_instrument.get(instrument_id)
            if instrument is None:
                raise InstrumentException("instrument not found by id: '%s'" % id)
        elif name:
            instrument = Instrument.name_to_instrument.get(name)
            if instrument is None:
                raise InstrumentException("instrument not found by name: '%s'" % name)
        else:
            raise InstrumentException('must give id or name to get an instrument')

        return instrument
