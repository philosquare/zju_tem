import json
import datetime
import logging
import time

import requests

import config as Config

Config.config = Config.get_config('debug')
from config import config

logging.basicConfig(filename='log_tem_test.log', level=logging.INFO)


class TemTest(object):
    def __init__(self):
        with open('/etc/temdata.json') as f:
            data = f.readline()
        self.data = json.loads(data)
        self.admin = dict(
            username=config.ADMIN_USERNAME,
            password=config.ADMIN_PASSWORD
        )

    def reserve(self, data=None, delay=0):
        if data is None:
            data = self.data.copy()
            data['username'] = config.TEST_USERS[0]
        else:
            data = data.copy()
        data['reserve_time'] = (datetime.datetime.now() + datetime.timedelta(
            seconds=delay)).strftime('%Y-%m-%d %H:%M:%S')
        return requests.post('http://localhost/tem/api/reserve', data=data)

    def scheduled_jobs(self, username='', password=''):
        username = username or config.TEST_USERS[0]
        params = dict(username=username, password=password)
        return requests.get('http://localhost/tem/api/scheduled_jobs', params=params)

    def remove_job(self, jobid, username='', password=''):
        username = username or config.TEST_USERS[0]
        data = dict(username=username, password=password, job_id=jobid)
        return requests.post('http://localhost/tem/api/remove_job', data=data)

    def remove_all(self, username='', password=''):
        username = username or config.TEST_USERS[0]
        data = dict(username=username, password=password)
        return requests.post('http://localhost/tem/api/remove_all_jobs', data=data)

    def test_reserve(self):
        logging.info('预约测试：\n-------------------------------')
        r1 = self.reserve(self.data)
        r2 = self.reserve(self.data)
        logging.info('第一次预约：\n' + r1.text)
        logging.info('第二次预约：\n' + r2.text)
        if r1.status_code != requests.codes.ok or json.loads(r1.text).get('code') != 0 or json.loads(r2.text).get('code') != 0:
            print('预约测试失败……')
            return
        else:
            print('预约测试通过，请查看实际预约结果')
        # 乱填数据测试
        data = self.data.copy()
        data['username'] = 'vxz'
        data['reserve_date'] = 'asdefdsa ff'
        data['start_time'] = '三改'
        r3 = self.reserve(data)
        logging.info('第三次预约：\n' + r3.text)
        if r3.status_code != 200:
            print('预约测试-乱填数据测试失败……')
        print('预约测试-乱填数据测试通过')

    def test_scheduled_jobs(self):
        logging.info('获取定时任务测试：\n-------------------------------')
        rj1 = self.scheduled_jobs()
        job_num1 = len(json.loads(rj1.text).get('jobs'))
        self.reserve(delay=10)
        rj2 = self.scheduled_jobs()
        job_num2 = len(json.loads(rj2.text).get('jobs'))
        logging.info('获取列表：\n' + rj2.text)
        if rj1.status_code == requests.codes.ok and json.loads(rj1.text).get('code') == 0 and \
                job_num2 - job_num1 == 1:
            print('获取定时任务测试通过')
        else:
            print('获取定时任务测试失败……')
            return
        # 管理员获取任务测试
        rj3 = self.scheduled_jobs(config.ADMIN_USERNAME, config.ADMIN_PASSWORD)
        job_num3 = len(json.loads(rj3.text).get('jobs'))
        if job_num3 >= job_num2:
            print('管理员获取定时任务测试通过')
        else:
            print('管理员获取定时任务测试失败……')

    def test_remove_one(self):
        logging.info('删除任务测试：\n-------------------------------')
        rj = self.reserve(delay=10)
        if rj.status_code != requests.codes.ok:
            print('删除任务测试失败……')
            return
        jid = json.loads(rj.text).get('job_id')
        rj1 = self.scheduled_jobs()
        job_num1 = len(json.loads(rj1.text).get('jobs'))
        rm = self.remove_job(jid)
        code = json.loads(rm.text).get('code')
        rj2 = self.scheduled_jobs()
        job_num2 = len(json.loads(rj2.text).get('jobs'))
        logging.info('预约任务: \n%s\n任务ID：%s\n任务列表1：\n%s\n删除任务：\n%s\n任务列表2：\n%s' % (
            rj.text, jid, rj1.text, rm.text, rj2.text))
        if code == 0 and job_num1 - job_num2 == 1:
            print('删除任务测试通过')
        else:
            print('删除任务测试失败……')
            return
        # 删除其他用户任务测试
        rj = self.reserve(delay=10)
        jid = json.loads(rj.text).get('job_id')
        rm = self.remove_job(jid, config.TEST_USERS[1])
        logging.info('删除其他用户任务：\n%s' % rm.text)
        code = json.loads(rm.text).get('code')
        if code == -1:
            print('删除任务-删除其他用户任务测试通过')
        else:
            print('删除任务-删除其他用户任务测试失败……')

    def test_remove_all(self):
        logging.info('删除所有任务测试：\n-------------------------------')
        r1 = self.reserve(delay=10)
        r2 = self.reserve(delay=10)
        logging.info('预约请求返回：\n%s\n%s' % (r1.text, r2.text))
        jobs1 = self.scheduled_jobs()
        if jobs1.status_code != requests.codes.ok:
            print('删除所有任务测试失败……')
            return
        job_num1 = len(json.loads(jobs1.text).get('jobs'))
        # 删除其他用户任务测试
        rma1 = self.remove_all(config.TEST_USERS[1])
        job_num2 = len(json.loads(self.scheduled_jobs().text).get('jobs'))
        logging.info('删除所有任务-删除其他用户任务返回：\n%s删除前数量：%s\n删除后数量：%s' % (
            rma1.text, job_num1, job_num2))
        if rma1.status_code == requests.codes.ok and job_num1 == job_num2:
            print('删除所有任务-删除其他用户任务测试通过')
        else:
            print('删除所有任务-删除其他用户任务测试失败……')
        rma2 = self.remove_all()
        job_num3 = len(json.loads(self.scheduled_jobs().text).get('jobs'))
        logging.info('删除所有任务返回：\n%s删除前数量：%s\n删除后数量：%s' % (
            rma2.text, job_num2, job_num3))
        if job_num2 > 0 and job_num3 == 0:
            print('删除所有任务测试通过')
        else:
            print('删除所有任务测试失败……')

        r3 = self.reserve(delay=10)
        job_num4 = len(json.loads(self.scheduled_jobs().text).get('jobs'))
        rma3 = self.remove_all(config.ADMIN_USERNAME, config.ADMIN_PASSWORD)
        job_num5 = len(json.loads(self.scheduled_jobs().text).get('jobs'))
        if rma3.status_code == requests.codes.ok and job_num5 == 0 and job_num4 > 0:
            print('管理员删除所有任务测试通过')
        else:
            print('管理员删除所有任务测试失败……')


if __name__ == '__main__':
    tem_test = TemTest()
    tem_test.test_reserve()
    tem_test.test_scheduled_jobs()
    tem_test.test_remove_one()
    tem_test.test_remove_all()
