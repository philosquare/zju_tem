import json
import datetime
import logging

from urllib.error import HTTPError
from flask import request, render_template

from . import api as app
from config import config
from scheduler import SchedulerHandler
from reserve import ReserveTem, ReserveTime
from instrument import Instrument
from errors import InstrumentException, ReserveException


def auth(username, password):
    """验证用户名密码

    debug时，可以是测试用户，无需密码
    其他情况，可以是管理员用户，或正确的易约帐号
    """
    if config.debug and username in config.TEST_USERS:
        return True
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
    """预约实验

    debug时任意用户名密码都可以设置预约定时，否则必须传入正确的易约网的用户名密码

    方法：POST
    请求body格式：x-www-form-urlencoded

    必要请求参数：
        username: 登录易约的用户名
        password: 登录易约的密码
        instrument: 预约的仪器，必须是resources.instruments中某一仪器的name
        reserve_date: 预约的实验日期，格式：2017-01-01
        start_time: 预约的实验开始时间，格式：9:00
        end_time: 预约的实验结束时间，格式：13:00

    可选请求参数：
        report: 预约实验时要求填写的实验内容
        reserve_time: 开始预约时间，只有debug时才有效，否则预约时间是根据实验时间自动生成

    """
    username = request.form.get('username', '')
    password = request.form.get('password', '')
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
    # 判断start_time，end_time，reserve_date是否符合要求
    try:
        datetime.datetime.strptime(start_time, '%H:%M')
        datetime.datetime.strptime(end_time, '%H:%M')
        reserve_date = datetime.datetime.strptime(raw_reserve_date, '%Y-%m-%d').date()
    except ValueError as e:
        logging.warning('预约参数不正确：%s' % e)
        return json.dumps(dict(code=-5, msg='预约参数不正确'))

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
    try:
        reserve.set_account(username, password)
    except ReserveException as e:
        logging.warning('用户名或密码不符合要求：%s' % e)
        return json.dumps(dict(code=-5, msg='用户名或密码不符合要求'))
    reserve.set_info(reserve_info)
    # 设定预约时间
    if config.debug:
        if reserve_time == '':
            run_time = datetime.datetime.now()
        else:
            run_time = datetime.datetime.strptime(reserve_time, '%Y-%m-%d %H:%M:%S')
    else:
        # 根据实验时间和仪器自动判断预约时间
        run_time = ReserveTime.get_time(instrument, reserve_date)

    # 设定定时任务
    try:
        job = reserve.set_job(run_time)
    except Exception as e:
        logging.exception(e)
        return json.dumps(dict(code=-4, msg='服务器出现错误'), ensure_ascii=False)

    if job:
        return json.dumps(dict(code=0, msg='预约设定成功', job_id=job.id,
                               trigger_time=job.trigger.run_date.strftime('%Y-%m-%d %H:%M:%S')))
    else:
        return json.dumps(dict(code=-1, msg='帐号或密码错误'), ensure_ascii=False)


@app.route('/api/scheduled_jobs')
def scheduled_jobs():
    username = request.args.get('username')
    password = request.args.get('password')
    if username is None or password is None:
        if config.debug:
            username = config.ADMIN_USERNAME
            password = config.ADMIN_PASSWORD
        else:
            return json.dumps(dict(code=-2, msg='请输入帐号密码'))

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
    """检查用户名密码是否正确，用于登录界面

    注意：登录成功不一定能预约：管理员帐号可以登录成功，但是不能预约
    """
    username = request.args.get('username')
    password = request.args.get('password')
    try:
        authed = auth(username, password)
    except HTTPError as e:
        logging.warning('login failed in `login_test`')
        return json.dumps(dict(code=-4, msg='服务器出现问题'), ensure_ascii=False)

    if authed:
        if username == config.ADMIN_USERNAME:
            msg = '管理员登录成功！'
        else:
            msg = '登录成功！'
        return json.dumps(dict(code=0, msg=msg), ensure_ascii=False)
    else:
        return json.dumps(dict(code=-1, msg='登录失败'), ensure_ascii=False)
