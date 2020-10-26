import abc

from .config import ConsulConfig
from .node import ConsulKV, ConsulNode
from types import SimpleNamespace


class ConsulWrapper(abc.ABC):
    def __init__(self, config):
        self.api = config.get_consul_api()
        self.kv_groups = config.kv_groups
        self.kv_metadata = config.kv_metadata

    @abc.abstractmethod
    def get_groups(self, *args):
        pass

    @abc.abstractmethod
    def get_metadata(self, *args):
        pass

    @abc.abstractmethod
    def get_node(self, name):
        pass


class ConsulBulk(ConsulWrapper):
    def __init__(self, config):
        super().__init__(config)
        self.cache = SimpleNamespace(groups=dict(), metadata=dict(), nodes=dict())
        self.cache.groups.update({e.key(): e for e in self.load_path(self.kv_groups)})
        self.cache.metadata.update({e.key(): e for e in self.load_path(self.kv_metadata)})
        self.cache.nodes.update({(e.datacenter(), e.name()): e for e in self.load_nodes()})

    def load_path(self, *args):
        index, data = self.api.kv.get('/'.join(args), recurse=True)
        return filter(ConsulKV.is_entry, map(ConsulKV.from_dict, data))

    def load_nodes(self, datacenter='dc1'):
        index, nodes = self.api.catalog.nodes(dc=datacenter)
        return map(ConsulNode.from_dict, nodes)

    def get_value(self, cache, default, *args):
        res = cache.get('/'.join(args))
        return res.value() if res else default

    def get_groups(self, *args):
        return self.get_value(self.cache.groups, list(), self.kv_groups, *args)

    def get_metadata(self, *args):
        return self.get_value(self.cache.metadata, dict(), self.kv_metadata, *args)

    def get_node(self, dc, node):
        return self.cache.nodes.get((dc, node))

    def get_nodes(self, dc):
        return self.cache.nodes


class ConsulDirect(ConsulWrapper):
    def __init__(self, config):
        super().__init__(config)

    def get_value(self, *args):
        index, data = self.api.kv.get('/'.join(args))
        return ConsulKV.from_dict(data).value() if data else None

    def get_groups(self, *args):
        return self.get_value(self.kv_groups, *args)

    def get_metadata(self, *args):
        return self.get_value(self.kv_metadata, *args)

    def get_node(self, dc, node):
        index, data = self.api.catalog.node(node, dc=dc)
        return ConsulNode.from_dict(data.get('Node'))
