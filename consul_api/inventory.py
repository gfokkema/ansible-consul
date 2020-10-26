import json

from collections import defaultdict

from .config import ConsulConfig
from .node import ConsulKV, ConsulNode
from .wrapper import ConsulDirect

class NewInventory(object):
    def __init__(self, loader=ConsulDirect):
        self.config = ConsulConfig()
        self.consul = loader(self.config)

    def groups(self, dc):
        groups = defaultdict(list)
        for (dc, node), v in self.consul.get_nodes(dc).items():
            ng = self.consul.get_groups(dc, node)
            for e in ['all', *ng]:
                groups[e].append(v.name())
        return groups

    def metadata(self, dc):
        metadata = defaultdict(dict)
        for (dc, node), v in self.consul.get_nodes(dc).items():
            nm = {
                **v.metadata(),
            }
            metadata[v.fullname()] = nm
        return metadata

    def inventory(self, dc):
        return json.dumps({
            '_meta': {
                'hostvars': self.metadata(dc),
            },
            **self.groups(dc),
        }, indent=2)
