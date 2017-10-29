#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import json
import datetime
import logging
from flask import Flask, request, render_template

import config
from scheduler import SchedulerHandler
from reserve import ReserveTem, ReserveTime
from instrument import Instrument, InstrumentException

# TODO: 预约信息的log和程序log分开

logging.basicConfig(filename='log_tem.log', level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
app = Flask(__name__)


def auth(username, password):
    if username == config.ADMIN_USERNAME:
        if password == config.ADMIN_PASSWORD:
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


@app.route('/api/reserve', methods=['POST'])
def api_reserve():
    username = request.form.get('username')
    password = request.form.get('password')
    instrument_name = request.form.get('instrument', '')  # OLD_F20
    raw_reserve_date = request.form.get('reserve_date')  # '2017-01-01'
    start_time = request.form.get('start_time')  # '12:00'
    end_time = request.form.get('end_time')  # '13:00'
    report = request.form.get('report', 'tem')
    reserve_time = request.form.get('reserve_time', '')  # 开抢时间 2017-01-01 00:00:00

    # 根据名称找到仪器对象
    try:
        instrument = Instrument.get(name=instrument_name)
    except InstrumentException as e:
        logging.info(e)
        return json.dumps(dict(code=-2, msg="不存在该仪器: '%s'" % instrument_name), ensure_ascii=False)

    reserve_date = datetime.datetime.strptime(raw_reserve_date, '%Y-%m-%d').date()
    reserve_date_str = reserve_date.strftime('%Y年%m月%d日')
    reserve_info = dict(
        reserveDate=reserve_date_str,
        reserveStartTime=start_time,
        reserveEndTime=end_time,
        instrumentId=instrument.instrument_id,
        ReserveReport=report
    )

    # 创建对象，传入预约数据
    reserve = ReserveTem()
    reserve.set_account(username, password)
    reserve.set_info(reserve_info)

    if config.debug:
        if reserve_time == '':
            run_time = datetime.datetime.now()
        else:
            run_time = datetime.datetime.strptime(reserve_time, '%Y-%m-%d %H:%M:%S')
    else:
        run_time = ReserveTime.get_time(instrument, reserve_date)

    job = reserve.set_job(run_time)
    if job:
        return json.dumps(dict(code=0, msg='预约设定成功', job_id=job.id,
                               trigger_time=job.trigger.run_date.strftime('%Y-%m-%d %H:%M:%S')),
                          ensure_ascii=False)
    else:
        return json.dumps(dict(code=-1, msg='帐号或密码错误'), ensure_ascii=False)


@app.route('/api/scheduled_jobs')
def scheduled_jobs():
    username = request.args.get('username', config.ADMIN_USERNAME)
    password = request.args.get('password', config.ADMIN_PASSWORD)

    if auth(username, password):
        jobs = SchedulerHandler().get_jobs(username)
    else:
        return json.dumps(dict(code=-1, msg='帐号或密码错误'))

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
            instrument=Instrument.get(instrument_id=job.kwargs['reserve_data']['instrumentId']).cn_name,
            ReserveReport=job.kwargs['reserve_data']['ReserveReport']
        ))
    return json.dumps(dict(code=0, msg='ok', jobs=result_jobs))


@app.route('/api/remove_job', methods=['GET', 'POST'] if config.debug else ['POST'])
def remove_one_job():
    if config.debug:
        # debug时，帐号密码默认管理员，GET POST都可以
        if request.method == 'GET':
            username = request.args.get('username', config.ADMIN_USERNAME)
            password = request.args.get('password', config.ADMIN_PASSWORD)
            job_id = request.args.get('job_id')
        else:
            username = request.form.get('username', config.ADMIN_USERNAME)
            password = request.form.get('password', config.ADMIN_PASSWORD)
            job_id = request.form.get('job_id')
    else:
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        job_id = request.form.get('job_id')

    if auth(username, password):
        if SchedulerHandler().remove_job(job_id, username):
            return json.dumps(dict(code=0, msg='删除成功！'), ensure_ascii=False)
        else:
            return json.dumps(dict(code=-1, msg='任务不存在'), ensure_ascii=False)
    else:
        return json.dumps(dict(code=-1, msg='用户名或密码错误'), ensure_ascii=False)


@app.route('/api/remove_all_jobs', methods=['GET', 'POST'] if config.debug else ['POST'])
def remove_all_jobs():
    if config.debug:
        if request.method == 'GET':
            username = request.args.get('username', config.ADMIN_USERNAME)
            password = request.args.get('password', config.ADMIN_PASSWORD)
        else:
            username = request.form.get('username', config.ADMIN_USERNAME)
            password = request.form.get('password', config.ADMIN_PASSWORD)
    else:
        username = request.form.get('username', '')
        password = request.form.get('password', '')

    if auth(username, password):
        SchedulerHandler().remove_all_jobs(username)
        return json.dumps(dict(code=0, msg='删除成功！'), ensure_ascii=False)
    else:
        return json.dumps(dict(code=-1, msg='用户名或密码错误'), ensure_ascii=False)


@app.route('/api/login_test')
def login_test():
    username = request.args.get('username')
    password = request.args.get('password')
    if auth(username, password):
        if username == config.ADMIN_USERNAME:
            msg = '管理员登录成功！'
        else:
            msg = '登录成功！'
        return json.dumps(dict(code=0, msg=msg), ensure_ascii=False)
    else:
        return json.dumps(dict(code=-1, msg='登录失败'), ensure_ascii=False)


if __name__ == '__main__':
    scheduler = SchedulerHandler()
    scheduler.start()

    if len(sys.argv) > 1 and sys.argv[1] == 'debug':
        config.debug = True
        config.TRY_TIME = 1

    app.run(host='0.0.0.0', port=17910, debug=config.debug, threaded=True)
