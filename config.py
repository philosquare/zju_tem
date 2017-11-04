class Config:
    INTERVAL = 1
    ADMIN_USERNAME = 'root'
    ADMIN_PASSWORD = '00432791'


class ProductionConfig(Config):
    TRY_TIME = 10
    debug = False
    LOGIN_TRY_TIME = 3
    TEST_USERS = []
    SCHEDULER_STORE_URL = 'sqlite:///jobs.sqlite'


class DebugConfig(Config):
    debug = True
    SCHEDULER_STORE_URL = 'sqlite:///jobs_debug.sqlite'
    TEST_USERS = ['testuser1', 'testuser2']
    TRY_TIME = 1
    LOGIN_TRY_TIME = 1


def get_config(env):
    return dict(
        debug=DebugConfig,
        production=ProductionConfig
    ).get(env)

config = DebugConfig
