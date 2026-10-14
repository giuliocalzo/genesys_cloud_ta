import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "package", "bin"))

from genesyscloud_models import EdgeModel


def test_sum_disks_adds_every_disk():
    disks = [
        {"partition_name": "/dev/a", "total_bytes": 100.0, "available_bytes": 40.0},
        {"partition_name": "/dev/b", "total_bytes": 50.0, "available_bytes": 10.0},
    ]
    assert EdgeModel.sum_disks(disks) == (150.0, 50.0)


def test_sum_disks_treats_null_values_as_zero():
    disks = [{"partition_name": "/dev/a", "total_bytes": None, "available_bytes": 5.0}]
    assert EdgeModel.sum_disks(disks) == (0, 5.0)


def test_sum_disks_empty_list():
    assert EdgeModel.sum_disks([]) == (0, 0)


def test_sum_disks_missing():
    assert EdgeModel.sum_disks(None) == (0, 0)
