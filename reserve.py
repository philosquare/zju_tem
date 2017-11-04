import datetime
from urllib.request import HTTPCookieProcessor, build_opener
from urllib.parse import urlparse, urlencode, parse_qs, unquote
from urllib.error import HTTPError
from http.cookiejar import CookieJar
from time import sleep

from config import config
import logging
from scheduler import SchedulerHandler
from errors import ReserveException


class ReserveTime:
    @staticmethod
    def get_time(instrument, experiment_date):
        """根据仪器类型和实验日期，返回开始预约的时间。如果当前已经过了预约时间，则返回当前时间

        :param Instrument.OneInstrument instrument: 实验仪器，它的两个attribute表示开始预约时间：
                reserve_weekday 表示实验日期的前一周的周几开始预约，周一是0，周日是6
                reserve_date 表示开始预约的时间

        :param datetime.date experiment_date: 实验日期

        :return: datetime.datetime: 开始预约的时间
        """
        reserve_weekday = instrument.reserve_weekday

        # 计算日期 实验日期的前一周
        delta_day = experiment_date.weekday() + 7 - reserve_weekday
        trigger_date = experiment_date - datetime.timedelta(days=delta_day)
        # 时期加上时间
        trigger_datetime = datetime.datetime.combine(trigger_date, instrument.reserve_time)
        # 和当前时间对比
        now = datetime.datetime.now()

        return trigger_datetime if trigger_datetime > now else now


def keep_reserve_job(username, password, reserve_data):
    """scheduler的定时任务，到预约时间触发，实现预约功能

    :param str username: 登录“易约”的用户名
    :param str password: 登录“易约”的密码
    :param dict reserve_data: POST请求提交的数据
    """
    reserve = ReserveTem()
    reserve.set_account(username, password)
    reserve.set_info(reserve_data)
    reserve.keep_reserve()


class ReserveTem(object):
    def __init__(self):
        self.login_url = 'http://cem.ylab.cn/doLogin.action'  # GET or POST
        self.reserve_url = 'http://cem.ylab.cn/user/doReserve.action'  # POST

        self.cookie = CookieJar()
        self.handler = HTTPCookieProcessor(self.cookie)
        self.opener = build_opener(self.handler)

        self.username = ''
        self.password = ''
        self.account_checked = None  # True: correct, False: wrong, None: haven't try
        self.reserve_data = {}

        self.scheduler = SchedulerHandler()

    def set_account(self, username, password):
        if not username or not password:
            raise ReserveException('username and password can not be empty')
        self.username = username
        self.password = password
        self.account_checked = None

    def set_info(self, reserve_data):
        self.reserve_data = reserve_data

    def login(self):
        login_data = urlencode(dict(
            origUrl='',
            origType='',
            rememberMe='false',
            username=self.username,
            password=self.password
        )).encode()
        # 尝试登录 有可能出现服务器500错误，所以尝试多次
        for i in range(config.LOGIN_TRY_TIME):
            try:
                login_result = self.opener.open(self.login_url, login_data)
                break
            except HTTPError as e:
                logging.warning('HTTPError: login try no.%s failed: %s' % (i + 1, str(e)))
                if i < config.LOGIN_TRY_TIME - 1:
                    sleep((i + 1) / 2)
        else:
            logging.warning('login failed: exceed max try times')
            raise e

        if login_result.geturl() != self.login_url:
            # 重定向则登录成功
            self.account_checked = True
            return True
        else:
            self.account_checked = False
            return False

    def _reserve(self):
        """must call set_account, set_info and login before this method

        :return: 返回一个dict
                status=True/False 是否预约成功，
                msg 服务器返回的errorCode 即错误信息
        """
        if self.username == '':
            raise ReserveException('must set account before reserve')
        if self.reserve_data == {}:
            raise ReserveException('must set reserve data before reserve')
        post_data = urlencode(self.reserve_data).encode()
        location = self.opener.open(self.reserve_url, post_data).geturl()
        result = parse_qs(urlparse(location).query)
        if 'success' in result.get('errorType', [''])[0]:
            # 预约成功
            return dict(status=True, msg='预约成功')
        else:
            msg = ''
            try:
                msg = unquote(unquote(result.get('errorCode')[0]))
            except TypeError as e:
                logging.exception(e)
            logging.info(msg)
            return dict(status=False, msg=msg)

    def keep_reserve(self):
        """reserve many times until success or exceed max try time

        :return: return True if reserve successfully else False
        """

        try:
            self.login()
        except HTTPError as e:
            return False
        except Exception as e:
            logging.exception(e)
            return False

        log_str = 'reserve date: %s time: %s-%s' % (
                  self.reserve_data['reserveDate'],
                  self.reserve_data['reserveStartTime'],
                  self.reserve_data['reserveEndTime'])

        for i in range(config.TRY_TIME):
            try:
                reserve_result = self._reserve()
                if reserve_result.get('status'):
                    logging.info('reserve success! %s' % log_str)
                    return True
                else:
                    logging.info('reserve failed no.%d, error message:%s %s' % (
                        i + 1, reserve_result.get('msg'), log_str))
            except Exception as e:
                logging.exception(e)
            if i < config.TRY_TIME - 1:
                sleep(config.INTERVAL)
        else:
            logging.warning('超过最大尝试次数，预约失败！%s' % log_str)
        return False

    def set_job(self, reserve_time):
        """设置预约定时任务

        必须先调用`set_account()`以及`set_info()`，设置好账户和预约信息

        :param datetime.datetime reserve_time: 预约触发时间
        :return: apscheduler.job.Job job: apscheduler的job对象
        """
        if not self.username:
            raise ReserveException('must set account before set job')
        if self.reserve_data == {}:
            raise ReserveException('must set reserve data before set job')
        if config.debug:
            checked = True
        else:
            if self.account_checked is None:
                self.login()
            checked = self.account_checked
        if checked:
            job = self.scheduler.add_job(keep_reserve_job, 'date', run_date=reserve_time, kwargs=dict(
                username=self.username, password=self.password, reserve_data=self.reserve_data))
            return job
        return None
