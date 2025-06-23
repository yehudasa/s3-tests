import pytest
import random
import string
import re
import json
from botocore.exceptions import ClientError
from botocore.exceptions import EventStreamError

from random import choices, randrange, sample


import uuid
import warnings
import traceback

from . import (
    configfile,
    setup_teardown,
    get_client,
    get_new_bucket
    )

import logging
logging.basicConfig(level=logging.INFO)

import collections
collections.Callable = collections.abc.Callable

def random_text(length):
    return ''.join(choices(string.ascii_letters + string.digits + " ", k=length))

def get_object(client, bucket_name, key, snap_id = None): 
    if snap_id is None:
        return client.get_object(Bucket=bucket_name, Key=key)
    
    return client.get_object(Bucket=bucket_name, Key=key, SnapId=int(snap_id))

def _get_body(response):
    body = response['Body']
    return body.read()

def get_bucket_snaps_status(client, bucket_name):
    return client.list_bucket_snapshots(Bucket = bucket_name)

def get_bucket_snaps_enabled(client, bucket_name):
    status = get_bucket_snaps_status(client, bucket_name)
    return status['Enabled']

def list_bucket_snaps(client, bucket_name):
    status = get_bucket_snaps_status(client, bucket_name)
    return status.get('Snapshots')

def enable_bucket_snaps(client, bucket_name):
    try:
        response = client.put_bucket_snapshots_configuration(Bucket = bucket_name, BucketSnapsConf = { 'Enabled': True } )
    except:
        return False

    return response['ResponseMetadata']['HTTPStatusCode'] == 200

def create_bucket_snap(client, bucket_name, snap_name, desc = None):
    
    conf = { 'Name': snap_name }
    if desc:
        conf['Description'] = desc

    try:
        response = client.create_bucket_snapshot(Bucket = bucket_name, SnapConf = conf)
    except:
        return False

    return response['ResponseMetadata']['HTTPStatusCode'] == 200

@pytest.mark.snap
def test_enable_snap():

    client = get_client()
    bucket_name = get_new_bucket()

    enabled = get_bucket_snaps_enabled(client, bucket_name)
    assert not enabled
    
    success = enable_bucket_snaps(client, bucket_name)
    assert success

    enabled = get_bucket_snaps_enabled(client, bucket_name)
    assert enabled

@pytest.mark.snap
def test_create_snap():

    client = get_client()
    bucket_name = get_new_bucket()

    snap_name = 'mysnap'
    snap_desc = 'bla'

    # should fail before we enable snapshots
    success = create_bucket_snap(client, bucket_name, snap_name, desc = snap_desc)
    assert not success

    success = enable_bucket_snaps(client, bucket_name)
    assert success

    success = create_bucket_snap(client, bucket_name, snap_name, desc = snap_desc)
    assert success

    snaps = list_bucket_snaps(client, bucket_name)
    assert len(snaps) == 1

    snap_info = snaps[0]['Info']
    assert snap_info['Name'] == snap_name
    assert snap_info['Description'] == snap_desc

    # should fail a second time
    success = create_bucket_snap(client, bucket_name, snap_name, desc = snap_desc)
    assert not success

class DataObject:
    def __init__(self, key = None, data = None, snap_id = None):
        self.key = key
        self.data = data
        self.snap_id = snap_id

        if not key:
            if not self.snap_id:
                self.key = 'obj-' + random_text(7)
            else:
                self.key = f'obj-{self.snap_id}-' + random_text(7)


        if not data:
            object_size = randrange(50)
            self.data = bytes(random_text(object_size), 'utf-8')

class SnapManager:
    def __init__(self, client, bucket_name):
        self.client = client
        self.bucket_name = bucket_name
        self.snap_id = 1
        self.snaps = { 1: {}}

    def enable_snaps(self):
        return enable_bucket_snaps(self.client, self.bucket_name)

    def create_snap(self, name, desc = None):
        success = create_bucket_snap(self.client, self.bucket_name, name, desc=desc)
        if not success:
            return False
        
        self.snap_id += 1

        self.snaps[self.snap_id] = {}

        return True

    def put(self, obj):
        self.client.put_object(Bucket=self.bucket_name, Key=obj.key, Body=obj.data)
        self.snaps[self.snap_id][obj.key] = obj

    def get_obj(self, obj, snap_id = None):
        return get_object(self.client, self.bucket_name, obj.key, snap_id)

    def get_obj_data(self, key, snap_id = None):
        response = self.get_obj(key, snap_id)
        return _get_body(response)

    def check_data(self, obj, snap_id = None):
        data = self.get_obj_data(obj, snap_id)

        store_snap_id = snap_id
        if store_snap_id == None:
            store_snap_id = self.snap_id

        print(f'snap_id={store_snap_id}')
        print(f'bucket={self.bucket_name}')
        print(f'key={obj.key}')
        print(f'expected data={obj.data}')
        print(f'actual data={data}')
        return data == obj.data


def test_snap_object_write_file_before_snapshots_enabled():
    bucket_name = get_new_bucket()
    client = get_client()

    sm = SnapManager(client, bucket_name)

    obj = DataObject()

    sm.put(obj)
    snap_id = sm.snap_id

    success = sm.check_data(obj)
    assert success

    success = sm.enable_snaps()
    assert success
    success = sm.create_snap('mysnap')
    assert success

    new_obj = DataObject(key=obj.key)
    sm.put(new_obj)

    success = sm.check_data(new_obj)
    assert success

    success = sm.check_data(obj)
    assert not success

    success = sm.check_data(obj, snap_id = snap_id)
    assert success
