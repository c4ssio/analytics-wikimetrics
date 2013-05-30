import collections
from sqlalchemy import Column, Integer, String, ForeignKey
from wikimetrics.database import Base
from queue import celery
from celery import group, chord
from flask_utils import get_user_id

__all__ = [
    'Job',
    'JobNode',
    'JobLeaf',
    'JobStatus',
]

class JobStatus(object):
    CREATED = 'CREATED'
    STARTED = 'STARTED'
    FINISHED = 'FINISHED'

class Job(Base):
    __tablename__ = 'job'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'))
    classpath = Column(String(200))
    status = Column(String(100))
    result_id = Column(String(50))
    
    def __init__(self,
            user_id = None,
            status = JobStatus.CREATED,
            parent_job_id = None,
            result_id = None,
        ):
        self.user_id = user_id or get_user_id()
        self.status = status
        self.parent_job_id = parent_job_id
        self.result_id = result_id
    
    # FIXME: calling ConcatMetricsJob().run uses this run instead of the JobNode one
    #@celery.task
    #def run(self):
        #pass
    
    def __repr__(self):
        return '<Job("{0}")>'.format(self.id)
    
    def get_classpath(self):
        return str(type(self))

class JobNode(Job):
    def __init__(self):
        super(JobNode, self).__init__()
    
    def child_tasks(self):
        return group(child.run.s(child) for child in self.children)
    
    @celery.task
    def run(self):
        children_then_finish = chord(self.child_tasks())(self.finish.s())
        children_then_finish.get()
    
    @celery.task
    def finish(self):
        pass

class JobLeaf(Job):
    def __init__(self):
        super(JobLeaf, self).__init__()
