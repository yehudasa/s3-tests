import pytest
import random
import string
import re
import json
from botocore.exceptions import ClientError
from botocore.exceptions import EventStreamError

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
