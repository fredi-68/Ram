class Filter():

    def __init__(self, *args, **kwargs):

        pass

    def construct(self, model: "Model") -> str:

        pass

class Equals(Filter):

    def __init__(self, name, value):

        self.name = name
        self.value = value

    def construct(self, model):
        
        field = model._fields[self.name]
        return '%s=%s' % (self.name, field._serialize(self.value))