"""Dataset loaders for public EEG datasets."""

from open_normative.datasets.lemon import LEMONLoader
from open_normative.datasets.hbn import HBNLoader
from open_normative.datasets.mipdb import MIPDBLoader

DATASETS = {
    "lemon": LEMONLoader,
    "hbn": HBNLoader,
    "mipdb": MIPDBLoader,
}
