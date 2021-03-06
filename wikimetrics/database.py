"""
This module deals with database connections, engine creation, and session creation.
It exposes methods and variables according to SQLAlchemy best practices (hopefully).
It has the ability to connect to multiple mediawiki databases.
It uses Flask's handy config module to configure itself.
"""
import json
from os.path import exists
from urllib2 import urlopen
#from multiprocessing import Pool
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import exc
from sqlalchemy import event
from sqlalchemy.pool import Pool

__all__ = [
    'Database',
]


class SerializableBase(object):
    """
    This is used as a base class for our declarative Bases.  It allows us to jsonify
    instances of SQLAlchemy models more easily.
    """
    
    def _asdict(self):
        """ simplejson (used by flask.jsonify) looks for a method with this name """
        #return {c.name : getattr(self, c.name) for c in self.__table__.columns if c.name != 'id'}
        return {c.name : getattr(self, c.name) for c in self.__table__.columns}


def get_host_projects(host_id):
    cluster_url_fmt = 'https://noc.wikimedia.org/conf/s{0}.dblist'
    url = cluster_url_fmt.format(host_id)
    projects = urlopen(url).read().splitlines()
    return (host_id, projects)


class Database(object):
    """
    Basically a collection of all database related objects and methods.
    Instantiated after configuration is done, in the wikimetrics.configurables module.
    You should not instantiate this yourself, just do `from .configurables import db`
    """
    
    def __init__(self):
        """
        Initializes the config object (using Flask's Config class).
        Sets the root_path of the Config object to '' which means you must provide
        absolute paths to any `config.from_pyfile` calls.
        
        Initializes the declarative bases that are used throughout the project.
        Initializes the empty engines and sessionmakers that support
        `get_session` and `get_mw_session`.
        """
        self.WikimetricsBase = declarative_base(cls=SerializableBase)
        self.MediawikiBase = declarative_base(cls=SerializableBase)

        self.wikimetrics_engine = None
        self.wikimetrics_sessionmaker = None
        
        self.mediawiki_engines = {}
        self.mediawiki_sessionmakers = {}
        self.project_host_map = self.get_project_host_map(usecache=False)
    
    def get_session(self):
        """
        On the first run, instantiates the Wikimetrics session maker
        and create wikimetrics tables if they don't exist.
        On subsequent runs, it does not re-define the session maker or engine.
        
        Returns:
            new sqlalchemy session open to the wikimetrics database
        """
        if not self.wikimetrics_engine:
            self.wikimetrics_engine = create_engine(
                self.config['WIKIMETRICS_ENGINE_URL'],
                echo=self.config['SQL_ECHO'],
            )
            # This import is necessary here so WikimetricsBase knows about all its children.
            import wikimetrics.models
            self.WikimetricsBase.metadata.create_all(self.wikimetrics_engine, checkfirst=True)
            self.wikimetrics_sessionmaker = sessionmaker(self.wikimetrics_engine)
        
        return self.wikimetrics_sessionmaker()
    
    def get_mw_session(self, project):
        """
        Based on the mediawiki project passed in, create a sqlalchemy session.
        
        Parameters:
            project : string name of the mediawiki project (for example: enwiki, arwiki)
        
        Returns:
            new sqlalchemy session connected to the appropriate database.  As an optimization,
            this method caches sqlalchemy session makers and creates sessions from those.
        """
        if project in self.mediawiki_sessionmakers:
            return self.mediawiki_sessionmakers[project]()
        else:
            import wikimetrics.models.mediawiki
            engine = self.get_mw_engine(project)
            
            project_sessionmaker = sessionmaker(engine)
            self.mediawiki_sessionmakers[project] = project_sessionmaker
            return project_sessionmaker()
    
    def get_mw_engine(self, project):
        """
        Based on the mediawiki project passed in, create a sqlalchemy engine.
        
        Parameters:
            project : string name of the mediawiki project (for example: enwiki, arwiki)
        
        Returns:
            new or cached sqlalchemy engine connected to the appropriate database.
        """
        if project in self.mediawiki_engines:
            return self.mediawiki_engines[project]
        else:
            engine = create_engine(
                self.config['MEDIAWIKI_ENGINE_URL_TEMPLATE'].format(project),
                echo=self.config['SQL_ECHO'],
            )
            self.mediawiki_engines[project] = engine
            return engine
    
    def get_project_host_map(self, usecache=True):
        """
        Retrieves the list of mediawiki projects from noc.wikimedia.org.
        
        Parameters:
            usecache    : defaults to True and uses a local cache if available
        """
        cache_name = 'project_host_map.json'
        if not exists(cache_name) or not usecache:
            # TODO: these numbers are hardcoded, is that ok?
            num_hosts = 7
            host_projects = map(get_host_projects, range(1, num_hosts + 1))
            #pool = Pool(num_hosts)
            #host_projects = pool.map(get_host_projects, range(1, num_hosts + 1))
            project_host_map = {}
            host_fmt = 's{0}'
            for host_id, projects in host_projects:
                host = host_fmt.format(host_id)
                for project in projects:
                    project_host_map[project] = host
            if usecache:
                json.dump(project_host_map, open(cache_name, 'w'))
        else:
            project_host_map = json.load(open(cache_name))
        
        return project_host_map


@event.listens_for(Pool, "checkout")
def ping_connection(dbapi_connection, connection_record, connection_proxy):
    """
    Pings the connection on checkout, making sure that it hasn't gone stale.
    This prevents error (OperationalError) (2006, 'MySQL server has gone away').
    This fix can be tested with tests/manual/connection_survives_server_restart.py
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("SELECT 1")
    except:
        # optional - dispose the whole pool
        # instead of invalidating one at a time
        # connection_proxy._pool.dispose()

        # raise DisconnectionError - pool will try
        # connecting again up to three times before raising.
        raise exc.DisconnectionError()
    cursor.close()
