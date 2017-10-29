#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import json
import datetime
import urllib
# import urllib2
from urllib.parse import urlparse, urlencode, parse_qs, unquote
from http.cookiejar import CookieJar
import logging
from time import sleep
from flask import Flask, request, render_template
from apscheduler.schedulers.background import BackgroundScheduler


logging.basicConfig(filename='log_tem.log', level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
app = Flask(__name__)

class Config:
    INTERVAL = 2
    TRY_TIME = 5
    debug = False
    ADMIN_USERNAME = 'root'
    ADMIN_PASSWORD = '00432791'


class SchedulerHandler(object):
    _instance = None
    scheduler = BackgroundScheduler()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = object.__new__(cls)
            cls.scheduler.add_jobstore('sqlalchemy', url='sqlite:///jobs.sqlite')
        return cls._instance

    def start(self):
        return self.scheduler.start()
    
    def add_job(self, *args, **kwargs):
        return self.scheduler.add_job(*args, **kwargs)

    def get_jobs(self, username):
        all_jobs = self.scheduler.get_jobs()
        if username == Config.ADMIN_USERNAME:
            jobs = all_jobs
        else:
            jobs = []
            for job in all_jobs:
                if job.kwargs['username'] == username:
                    jobs.append(job)
        return jobs
    
    def get_job(self, job_id, username):
        job = self.scheduler.get_job(job_id)
        if username == Config.ADMIN_USERNAME or job.kwargs['username'] == username:
            return job
        else:
            return None
    
    def remove_job(self, job_id, username):
        if self.get_job(job_id, username):
            self.scheduler.remove_job(job_id)
            return True
        else:
            return False

    def remove_all_jobs(self, username):
        if username == Config.ADMIN_USERNAME:
            self.scheduler.remove_all_jobs()
        else:
            jobs = self.get_jobs(username)
            for job in jobs:
                self.scheduler.remove_job(job.id)


class Instrument:
    OLD_F20 = '28ad18ae3ebb4f91b1d52553019ca381'
    NEW_F20 = '563e690aae7b41dfb6da1880f291e65b'
    FIB = '23ba4d2d9470434a905b4049ef457648'

    @staticmethod
    def get_id(instrument_name):
        return dict(OLD_F20=Instrument.OLD_F20,
                    NEW_F20=Instrument.NEW_F20,
                    FIB=Instrument.FIB
                    ).get(instrument_name)

    @staticmethod
    def get_name_by_id(instrument_id):
        return {Instrument.OLD_F20: 'OLD_F20',
                Instrument.NEW_F20: 'NEW_F20',
                Instrument.FIB: 'FIB'}.get(instrument_id)


class ReserveTime:
    # TODO: 根据预约的日期和仪器确定时间
    @staticmethod
    def get_reserve_time(instrument_name):
        """get reserve start time according to instrument name automatically

        :param instrument_name: OLD_F20, NEW_F20 or FIB

        :return: datetime.datetime: correct datetime to reserve the specific instrument
        """
        today = datetime.date.today()
        if instrument_name in ['OLD_F20', 'NEW_F20']:
            # 00:00 SAT
            reserve_weekday = 5
            reserve_hour = 0
        elif instrument_name == 'FIB':
            # 8:00 MON
            reserve_weekday = 0
            reserve_hour = 8
        else:
            # TODO: 创建自己的exception类型 记得catch
            raise Exception('wrong instrument name')
        # 根据今天周几算出预约日期
        delta_day = (reserve_weekday - today.weekday()) % 7
        reserve_date = today + datetime.timedelta(days=delta_day)
        # 日期加上时间
        reserve_datetime = datetime.datetime.combine(reserve_date, datetime.time(hour=reserve_hour))
        return reserve_datetime


class ReserveTem(object):
    def __init__(self):
        self.login_url = 'http://cem.ylab.cn/doLogin.action'  # GET or POST
        self.reserve_url = 'http://cem.ylab.cn/user/doReserve.action'  # POST

        self.cookie = CookieJar()
        self.handler = urllib.request.HTTPCookieProcessor(self.cookie)
        self.opener = urllib.request.build_opener(self.handler)

        self.username = ''
        self.password = ''
        self.account_checked = None  # True: correct, False: wrong, None: haven't try
        self.reserve_data = {}

        self.scheduler = SchedulerHandler()

    def set_account(self, username, password):
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
        login_result = self.opener.open(self.login_url, login_data)
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
        post_data = urlencode(self.reserve_data).encode()
        location = self.opener.open(self.reserve_url, post_data).geturl()
        result = parse_qs(urlparse(location).query)
        if 'success' in result.get('errorType', [''])[0]:
            # 预约成功
            return dict(status=True, msg='预约成功')
        else:
            msg = unquote(unquote(result.get('errorCode')[0]))
            logging.info(msg)
            return dict(status=False, msg=msg)

    # def reserve(self):
    #     """reserve once
    #
    #     :return: return True if reserve successfully else False
    #     """
    #     self.login()
    #     return self._reserve()

    def keep_reserve(self):
        """reserve many times until success or exceed max try time

        :return: return True if reserve successfully else False
        """
        log_str = 'reserve date: %s time: %s - %s' % (
                  self.reserve_data['reserveDate'],
                  self.reserve_data['reserveStartTime'],
                  self.reserve_data['reserveEndTime'])

        self.login()
        for i in range(Config.TRY_TIME):
            try:
                reserve_result = self._reserve()
                if reserve_result.get('status'):
                    logging.info('reserve success! %s' % log_str)
                    return True
                else:
                    logging.info('reserve failed no.%d, error message:%s %s' % (
                        i + 1, reserve_result.get('msg'), log_str))
            # except urllib.URLError as e:
            #     logging.exception(e)
            except Exception as e:
                logging.exception(e)
            sleep(Config.INTERVAL)
        return False

    def set_job(self, reserve_time):
        """start reserve at `reserve_time`

        must set reserve_info by calling `set_info()` before

        :param datetime.datetime reserve_time: format: '%Y-%m-%d %H:%M:%S'
        :return: apscheduler.job.Job instance
        """
        if self.login():
            job = self.scheduler.add_job(keep_reserve_job, 'date', run_date=reserve_time, kwargs=dict(
                username=self.username, password=self.password, reserve_data=self.reserve_data))
            return job
        return None


def keep_reserve_job(username, password, reserve_data):
    reserve = ReserveTem()
    reserve.set_account(username, password)
    reserve.set_info(reserve_data)
    reserve.keep_reserve()


def auth(username, password):
    if username == Config.ADMIN_USERNAME:
        if password == Config.ADMIN_PASSWORD:
            return True
        else:
            return False
    else:
        r = ReserveTem()
        r.set_account(username, password)
        return r.login()


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        return render_template("index.html")


@app.route('/api/reserve', methods=['GET', 'POST'])
def api_reserve():
    username = request.args.get('username')
    password = request.args.get('password')
    instrument_name = request.args.get('instrument')  # OLD_F20
    raw_reserve_date = request.args.get('reserve_date')  # '2017-01-01'
    start_time = request.args.get('start_time')  # '12:00'
    end_time = request.args.get('end_time')  # '13:00'
    report = request.args.get('report', 'tem')
    reserve_time = request.args.get('reserve_time', '')  # 开抢时间 2017-01-01 00:00:00

    reserve_date = datetime.datetime.strptime(raw_reserve_date, '%Y-%m-%d').strftime('%Y年%m月%d日')
    reserve = ReserveTem()
    reserve.set_account(username, password)
    reserve_info = dict(
        reserveDate=reserve_date,
        reserveStartTime=start_time,
        reserveEndTime=end_time,
        instrumentId=Instrument.get_id(instrument_name),
        ReserveReport=report
    )
    reserve.set_info(reserve_info)
    if Config.debug:
        run_time = datetime.datetime.now()
    else:
        if reserve_time == '':
            run_time = ReserveTime.get_reserve_time(instrument_name)
        else:
            run_time = datetime.datetime.strptime(reserve_time, '%Y-%m-%d %H:%M:%S')

    job = reserve.set_job(run_time)
    if job is not None:
        return json.dumps(dict(status=1, msg='预约设定成功', job_id=job.id,
                               trigger_time=job.trigger.run_date.strftime('%Y-%m-%d %H:%M:%S')),
                          ensure_ascii=False)
    else:
        return json.dumps(dict(status=-1, msg='帐号或密码错误'), ensure_ascii=False)


@app.route('/api/scheduled_jobs')
def scheduled_jobs():
    username = request.args.get('username', Config.ADMIN_USERNAME)
    password = request.args.get('password', Config.ADMIN_PASSWORD)

    if auth(username, password):
        jobs = SchedulerHandler().get_jobs(username)
    else:
        return json.dumps(dict(status=-1, msg='帐号或密码错误'))

    result_jobs = []
    for job in jobs:
        result_jobs.append(dict(
            id=job.id,
            username=job.kwargs['username'],
            trigger_time=job.trigger.run_date.strftime('%Y-%m-%d %H:%M:%S'),
            reserve_date=datetime.datetime.strptime(
                job.kwargs['reserve_data']['reserveDate'], '%Y年%m月%d日').strftime('%Y-%m-%d'),
            reserveStartTime=job.kwargs['reserve_data']['reserveStartTime'],
            reserveEndTime=job.kwargs['reserve_data']['reserveEndTime'],
            instrument=Instrument.get_name_by_id(job.kwargs['reserve_data']['instrumentId']),
            ReserveReport=job.kwargs['reserve_data']['ReserveReport']
        ))
    return json.dumps(dict(status=1, msg='ok', jobs=result_jobs))


@app.route('/api/remove_job', methods=['GET', 'POST'])
def remove_one_job():
    if request.method == 'GET':
        username = request.args.get('username', Config.ADMIN_USERNAME)
        password = request.args.get('password', Config.ADMIN_PASSWORD)
        job_id = request.args.get('job_id')
    else:
        username = request.form.get('username', Config.ADMIN_USERNAME)
        password = request.form.get('password', Config.ADMIN_PASSWORD)
        job_id = request.form.get('job_id')

    if auth(username, password):
        if SchedulerHandler().remove_job(job_id, username):
            return json.dumps(dict(status=1, msg='删除成功！'), ensure_ascii=False)
        else:
            return json.dumps(dict(status=-1, msg='任务不存在'), ensure_ascii=False)
    else:
        return json.dumps(dict(status=-1, msg='用户名或密码错误'), ensure_ascii=False)


@app.route('/api/remove_all_jobs')
def remove_all_jobs():
    username = request.args.get('username', Config.ADMIN_USERNAME)
    password = request.args.get('password', Config.ADMIN_PASSWORD)

    if auth(username, password):
        SchedulerHandler().remove_all_jobs(username)
        return json.dumps(dict(status=1, msg='删除成功！'), ensure_ascii=False)
    else:
        return json.dumps(dict(status=-1, msg='用户名或密码错误'), ensure_ascii=False)


@app.route('/api/login_test')
def login_test():
    username = request.args.get('username')
    password = request.args.get('password')
    reserve = ReserveTem()
    reserve.set_account(username, password)
    if reserve.login():
        return json.dumps(dict(status=1, msg='登录成功！'), ensure_ascii=False)
    else:
        return json.dumps(dict(status=-1, msg='登录失败'), ensure_ascii=False)


if __name__ == '__main__':
    scheduler = SchedulerHandler()
    scheduler.start()

    if len(sys.argv) > 1 and sys.argv[1] == 'debug':
        Config.debug = True
        Config.TRY_TIME = 1

    app.run(host='0.0.0.0', port=17910, debug=Config.debug, threaded=True)
