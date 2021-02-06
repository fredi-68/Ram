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
        self.logger.debug("Environment updated: %s" % str(self._env))

    def __getattribute__(self, name):
        
        return self._env[name]

environment = Environment()