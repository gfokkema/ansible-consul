import json

from collections import defaultdict

from .config import ConsulConfig
from .node import ConsulKV, ConsulNode
from .wrapper import ConsulDirect

class NewInventory(object):
    def __init__(self, loader=ConsulDirect):
        self.config = ConsulConfig()
        self.consul = loader(self.config)

    def groups_for_node(self, dc, node):
        return ['all', *self.consul.get_groups(dc, node)]

    def groups(self, dc):
        groups = defaultdict(list)
        for (dc, node), v in self.consul.get_nodes(dc).items():
            for e in self.groups_for_node(dc, node):
                groups[e].append(v.name())
        return groups

    def metadata(self, dc):
        metadata = defaultdict(dict)
        for (dc, node), v in self.consul.get_nodes(dc).items():
            nm = dict()
            nm.update(v.metadata())
            for e in self.groups_for_node(dc, node):
                nm.update(self.consul.get_metadata('groups', e))
            nm.update(self.consul.get_metadata(dc, node))
            metadata[v.fullname()] = nm
        return metadata

    def inventory(self, dc):
        return json.dumps({
            '_meta': {
                'hostvars': self.metadata(dc),
            },
            **self.groups(dc),
        }, indent=2)
