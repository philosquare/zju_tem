#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import logging

from flask import Flask

import config

if len(sys.argv) > 1 and sys.argv[1] == 'debug':
    config.config = config.get_config('debug')
else:
    config.config = config.get_config('production')


from scheduler import SchedulerHandler
from api import api

# TODO: 预约信息的log和程序log分开
logging.basicConfig(filename='log_tem.log', level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
app = Flask(__name__)
app.register_blueprint(api)


if __name__ == '__main__':
    scheduler = SchedulerHandler()
    scheduler.start()
    app.run(host='0.0.0.0', port=17910, debug=config.config.debug, threaded=True)
