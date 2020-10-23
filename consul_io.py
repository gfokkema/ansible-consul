#!/usr/bin/env python

import json
import re
import yaml

from ansible.module_utils.six import iteritems
from consul_config import ConsulConfig


class ConsulInventory(object):
    def __init__(self):
        ''' Create an inventory based on the catalog of nodes and services
        registered in a consul cluster'''
        self.node_metadata = {}
        self.nodes = {}
        self.nodes_by_service = {}
        self.nodes_by_tag = {}
        self.nodes_by_datacenter = {}
        self.nodes_by_kv = {}
        self.nodes_by_availability = {}
        self.current_dc = None

        self.inmemory_kv = []
        self.inmemory_nodes = []

        self.config = ConsulConfig()
        self.consul_api = self.config.get_consul_api()

        if self.config.has_config('datacenter'):
            if self.config.has_config('host'):
                self.load_data_for_node(self.config.host, self.config.datacenter)
            else:
                self.load_data_for_datacenter(self.config.datacenter)
        else:
            self.load_all_data_consul()

    def build_inventory(self):
        inventory = {"_meta": {"hostvars": self.node_metadata}}
        groupings = [self.nodes, self.nodes_by_datacenter, self.nodes_by_service,
                     self.nodes_by_tag, self.nodes_by_kv, self.nodes_by_availability]
        for grouping in groupings:
            for name, addresses in grouping.items():
                inventory[name] = sorted(list(set(addresses)))
        return inventory

    def bulk_load(self, datacenter):
        index, groups_list = self.consul_api.kv.get(self.config.kv_groups, recurse=True, dc=datacenter)
        index, metadata_list = self.consul_api.kv.get(self.config.kv_metadata, recurse=True, dc=datacenter)
        index, nodes = self.consul_api.catalog.nodes(dc=datacenter)
        self.inmemory_kv += groups_list
        self.inmemory_kv += metadata_list
        self.inmemory_nodes += nodes

    def load_all_data_consul(self):
        ''' cycle through each of the datacenters in the consul catalog and process
            the nodes in each '''
        self.datacenters = self.consul_api.catalog.datacenters()
        for datacenter in self.datacenters:
            self.current_dc = datacenter
            self.bulk_load(datacenter)
            self.load_data_for_datacenter(datacenter)

    def load_metadata(self, key):
        if self.config.bulk_load == 'true':
            metadata = self.consul_get_kv_inmemory(key)
        else:
            index, metadata = self.consul_api.kv.get(key)
        return metadata

    def load_nodes(self, datacenter):
        if self.config.bulk_load == 'true':
            nodes = self.inmemory_nodes
        else:
            index, nodes = self.consul_api.catalog.nodes(dc=datacenter)
        return nodes

    def load_availability_groups(self, node, datacenter):
        '''check the health of each service on a node and add the node to either
        an 'available' or 'unavailable' grouping. The suffix for each group can be
        controlled from the config'''
        if self.config.has_config('availability'):
            for service_name, service in iteritems(node['Services']):
                for node in self.consul_api.health.service(service_name)[1]:
                    if self.is_service_available(node, service_name):
                        suffix = self.config.get_availability_suffix(
                            'available_suffix', '_available')
                    else:
                        suffix = self.config.get_availability_suffix(
                            'unavailable_suffix', '_unavailable')
                    self.add_node_to_map(self.nodes_by_availability,
                                         service_name + suffix, node['Node'])

    def is_service_available(self, node, service_name):
        '''check the availability of the service on the node beside ensuring the
        availability of the node itself'''
        consul_ok = service_ok = False
        for check in node['Checks']:
            if check['CheckID'] == 'serfHealth':
                consul_ok = check['Status'] == 'passing'
            elif check['ServiceName'] == service_name:
                service_ok = check['Status'] == 'passing'
        return consul_ok and service_ok

    def consul_get_kv_inmemory(self, key):
        result = filter(lambda x: x['Key'] == key, self.inmemory_kv)
        return result.pop() if result else None

    def consul_get_node_inmemory(self, node):
        result = filter(lambda x: x['Node'] == node, self.inmemory_nodes)
        return {"Node": result.pop(), "Services": {}} if result else None

    def load_data_for_datacenter(self, datacenter):
        '''processes all the nodes in a particular datacenter'''
        nodes = self.load_nodes(datacenter)
        for node in nodes:
            self.add_node_to_map(self.nodes_by_datacenter, datacenter, node)
            self.load_data_for_node(node['Node'], datacenter)

    def load_data_for_node(self, node, datacenter):
        '''loads the data for a single node adding it to various groups based on
        metadata retrieved from the kv store and service availability'''

        if self.config.suffixes == 'true':
            index, node_data = self.consul_api.catalog.node(node, dc=datacenter)
        else:
            node_data = self.consul_get_node_inmemory(node)
        node = node_data['Node']

        self.add_node_to_map(self.nodes, 'all', node)
        self.add_metadata(node_data, "consul_datacenter", datacenter)
        self.add_metadata(node_data, "consul_nodename", node['Node'])

        self.load_groups_from_kv(node_data)
        self.load_node_metadata_from_kv(node_data)
        if self.config.suffixes == 'true':
            self.load_availability_groups(node_data, datacenter)
            for name, service in node_data['Services'].items():
                self.load_data_from_service(name, service, node_data)

    def load_node_metadata_from_kv(self, node_data):
        ''' load the json dict at the metadata path defined by the kv_metadata value
            and the node name add each entry in the dictionary to the node's
            metadata '''
        node = node_data['Node']
        if self.config.has_config('kv_metadata'):
            key = "%s/%s/%s" % (self.config.kv_metadata, self.current_dc, node['Node'])
            metadata = self.load_metadata(key)
            if metadata and metadata['Value']:
                try:
                    metadata = yaml.safe_load(metadata['Value'])
                    for k, v in metadata.items():
                        self.add_metadata(node_data, k, v)
                except Exception as e:
                    print(e)
                    pass

    def load_groups_from_kv(self, node_data):
        ''' load the comma separated list of groups at the path defined by the
            kv_groups config value and the node name add the node address to each
            group found '''
        node = node_data['Node']
        if self.config.has_config('kv_groups'):
            key = "%s/%s/%s" % (self.config.kv_groups, self.current_dc, node['Node'])
            if self.config.bulk_load == 'true':
                groups = self.consul_get_kv_inmemory(key)
            else:
                index, groups = self.consul_api.kv.get(key)
            if groups and groups['Value']:
                for group in groups['Value'].split(','):
                    self.add_node_to_map(self.nodes_by_kv, group.strip(), node)

    def load_data_from_service(self, service_name, service, node_data):
        '''process a service registered on a node, adding the node to a group with
        the service name. Each service tag is extracted and the node is added to a
        tag grouping also'''
        self.add_metadata(node_data, "consul_services", service_name, True)

        if self.is_service("ssh", service_name):
            self.add_metadata(node_data, "ansible_ssh_port", service['Port'])

        if self.config.has_config('servers_suffix'):
            service_name = service_name + self.config.servers_suffix

        self.add_node_to_map(self.nodes_by_service, service_name, node_data['Node'])
        self.extract_groups_from_tags(service_name, service, node_data)

    def is_service(self, target, name):
        return name and (name.lower() == target.lower())

    def extract_groups_from_tags(self, service_name, service, node_data):
        '''iterates each service tag and adds the node to groups derived from the
        service and tag names e.g. nginx_master'''
        if self.config.has_config('tags') and service['Tags']:
            tags = service['Tags']
            self.add_metadata(node_data, "consul_%s_tags" % service_name, tags)
            for tag in service['Tags']:
                tagname = service_name + '_' + tag
                self.add_node_to_map(self.nodes_by_tag, tagname, node_data['Node'])

    def add_metadata(self, node_data, key, value, is_list=False):
        ''' Pushed an element onto a metadata dict for the node, creating
            the dict if it doesn't exist '''
        key = self.to_safe(key)
        node = self.get_inventory_name(node_data['Node'])

        if node in self.node_metadata:
            metadata = self.node_metadata[node]
        else:
            metadata = {}
            self.node_metadata[node] = metadata
        if is_list:
            self.push(metadata, key, value)
        else:
            metadata[key] = value

    def get_inventory_name(self, node_data):
        '''return the ip or a node name that can be looked up in consul's dns'''
        domain = self.config.domain
        if domain:
            node_name = node_data['Node']
            if self.current_dc:
                return '%s.node.%s.%s' % (node_name, self.current_dc, domain)
            else:
                return '%s.node.%s' % (node_name, domain)
        else:
            return node_data['Address']

    def add_node_to_map(self, map, name, node):
        self.push(map, name, self.get_inventory_name(node))

    def push(self, my_dict, key, element):
        ''' Pushed an element onto an array that may not have been defined in the
            dict '''
        key = self.to_safe(key)
        if key in my_dict:
            my_dict[key].append(element)
        else:
            my_dict[key] = [element]

    def to_safe(self, word):
        ''' Converts 'bad' characters in a string to underscores so they can be used
         as Ansible groups '''
        return re.sub(r'[^A-Za-z0-9\-\.]', '_', word)

    def sanitize_dict(self, d):

        new_dict = {}
        for k, v in d.items():
            if v is not None:
                new_dict[self.to_safe(str(k))] = self.to_safe(str(v))
        return new_dict

    def sanitize_list(self, seq):
        new_seq = []
        for d in seq:
            new_seq.append(self.sanitize_dict(d))
        return new_seq


print(json.dumps(ConsulInventory().build_inventory(), sort_keys=True, indent=2))
