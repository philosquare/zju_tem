import config
from apscheduler.schedulers.background import BackgroundScheduler


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
        if username == config.ADMIN_USERNAME:
            jobs = all_jobs
        else:
            jobs = []
            for job in all_jobs:
                if job.kwargs['username'] == username:
                    jobs.append(job)
        return jobs

    def get_job(self, job_id, username):
        job = self.scheduler.get_job(job_id)
        if username == config.ADMIN_USERNAME or job.kwargs['username'] == username:
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
        if username == config.ADMIN_USERNAME:
            self.scheduler.remove_all_jobs()
        else:
            jobs = self.get_jobs(username)
            for job in jobs:
                self.scheduler.remove_job(job.id)
