import json
import yaml

class ComplexEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, RecursiveNamespace):
            return obj.__dict__
        elif isinstance(obj, bytes):
            return str(obj)
        return json.JSONEncoder.default(self, obj)


class RecursiveNamespace:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, self.map_entry(v))

    def __str__(self):
        return json.dumps(self, cls=ComplexEncoder, indent=2)

    @classmethod
    def from_dict(cls, data):
        return cls(**data)

    def items(self):
        return self.__dict__.items()

    def keys(self):
        return self.__dict__.keys()

    def map_entry(self, entry):
        if type(entry) == list:
            return list(map(self.map_entry, entry))
        elif type(entry) == dict:
            return RecursiveNamespace(**entry)
        return entry


class ConsulKV(RecursiveNamespace):
    @staticmethod
    def is_entry(obj):
        return not obj.Key.endswith('/') and obj.Value

    def key(self):
        return self.Key

    def value(self):
        return yaml.safe_load(self.Value)


class ConsulNode(RecursiveNamespace):
    def datacenter(self):
        return self.Datacenter

    def fullname(self):
        return '{}.node.{}.consul'.format(self.name(), self.datacenter())

    def name(self):
        return self.Node

    def metadata(self):
        return {
            'consul_datacenter': self.datacenter(),
            'consul_nodename': self.name(),
        }
