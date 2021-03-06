from nose.tools import assert_true
from tests.fixtures import DatabaseTest, QueueDatabaseTest

from wikimetrics import app
from wikimetrics.metrics import NamespaceEdits
from wikimetrics.models import Cohort, MetricJob


class NamespaceEditsDatabaseTest(DatabaseTest):
    
    def test_finds_edits(self):
        cohort = self.session.query(Cohort).filter_by(name='test').one()
        
        metric = NamespaceEdits()
        results = metric(list(cohort), self.mwSession)
        
        assert_true(results is not None)
        assert_true(results[1] == 2, 'Dan had not 2 edits')
        assert_true(results[2] == 3, 'Evan had not 3 edits')
    
    def test_reports_zero_edits(self):
        cohort = self.session.query(Cohort).filter_by(name='test').one()
        
        metric = NamespaceEdits()
        results = metric(list(cohort), self.mwSession)
        
        assert_true(results is not None)
        assert_true(results[3] == 0, 'Andrew had not 0 edits')


class NamespaceEditsFullTest(QueueDatabaseTest):
    
    def test_namespace_edits(self):
        cohort = self.session.query(Cohort).filter_by(name='test').one()
        
        metric = NamespaceEdits()
        job = MetricJob(metric, list(cohort), 'enwiki')
        results = job.task.delay().get()
        print 'results: %s' % results
        
        assert_true(results is not None)
        assert_true(results[2] == 3, 'Evan had not 3 edits, when run on queue')
    
    def test_namespace_edits_namespace_filter(self):
        cohort = self.session.query(Cohort).filter_by(name='test').one()
        
        namespaces = [3]
        metric = NamespaceEdits(namespaces=namespaces)
        job = MetricJob(metric, list(cohort), 'enwiki')
        results = job.task.delay().get()
        
        assert_true(results is not None)
        assert_true(results[2] == 0, 'Evan had not 0 edits in namespaces %d, when run on queue')
    
    def test_namespace_edits_namespace_filter_no_namespace(self):
        cohort = self.session.query(Cohort).filter_by(name='test').one()
        
        namespaces = []
        metric = NamespaceEdits(namespaces=namespaces)
        job = MetricJob(metric, list(cohort), 'enwiki')
        results = job.task.delay().get()
        
        assert_true(results is not None)
        assert_true(results[2] == 0, 'Evan had not 0 edits in namespaces %s, when run on queue')
