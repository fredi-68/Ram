CLEANUP_FUNCTIONS = []
SUPERUSERS = set()

class Environment():

    def __init__(self):

        self._env = {}

    def initialize_environment(self, env):

        """
        Initialize the command system environment.
        """

        self._env.update(env)

    def __getattribute__(self, name):
        
        return self._env[name]

environment = Environment()