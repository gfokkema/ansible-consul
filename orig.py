import json

from consul_api.consul_io import ConsulInventory

print('--- Original ---')
inventory = ConsulInventory().build_inventory()
print(json.dumps(inventory, sort_keys=True, indent=2))
