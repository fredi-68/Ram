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

class And(Filter):

    def __init__(self, filter1, filter2):

        self._f1 = filter1
        self._f2 = filter2

    def construct(self, model):
        
        return "%s AND %s" % (self._f1.construct(model), self._f2.construct(model))

class Exists(Filter):

    def __init__(self, filter, model_override=None):

        self._next = filter
        self._table = model_override._table_name if model_override else None

    def construct(self, model):

        return ("EXISTS (SELECT * FROM %s WHERE %s)" % (self._table or model._table_name, self._next.construct(model)))

class Not(Filter):

    def __init__(self, filter):

        self._next = filter

    def construct(self, model):
        
        return "NOT " + self._next.construct(model)