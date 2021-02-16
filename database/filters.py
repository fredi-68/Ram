class Filter():

    def __init__(self, *args, **kwargs):

        pass

    def construct(self, model: "Model") -> str:

        pass

class Equals(Filter):

    def __init__(self, field, name, value):

        self.field = field
        self.name = name
        self.value = value

    def construct(self):
        
        return '%s=%s' % (self.name, self.field._serialize(self.value))