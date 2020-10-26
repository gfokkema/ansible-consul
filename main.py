import json

from consul_api.inventory import NewInventory
from consul_api.wrapper import ConsulBulk

print('--- Rewrite ---')
i = NewInventory(loader=ConsulBulk)
print(i.inventory('dc1'))
