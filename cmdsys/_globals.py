import logging

CLEANUP_FUNCTIONS = []
SUPERUSERS = set()

class Environment():

    logger = logging.getLogger("cmdsys.Environment")

    def __init__(self):

        self._env = {}

    def update_environment(self, env):

        """
        Initialize the command system environment.
        """

        self._env.update(env)
        self.logger.info("Environment updated: %s" % str(self._env))

    def __getattr__(self, name):
        
        self.logger.debug("Requested environment variable %s" % name)
        return self._env[name]

environment = Environment()