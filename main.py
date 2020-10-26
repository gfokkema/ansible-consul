import json

from consul_api.consul_io import ConsulInventory
from consul_api.inventory import NewInventory
from consul_api.wrapper import ConsulBulk

inventory = ConsulInventory().build_inventory()
print('--- Original ---')
print(json.dumps(inventory, sort_keys=True, indent=2))

print('--- Rewrite ---')
i = NewInventory(loader=ConsulBulk)
print(i.inventory('dc1'))
