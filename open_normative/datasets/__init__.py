"""Dataset loaders for public EEG datasets."""

from open_normative.datasets.lemon import LEMONLoader
from open_normative.datasets.hbn import HBNLoader
from open_normative.datasets.mipdb import MIPDBLoader
from open_normative.datasets.dortmund import DortmundLoader
from open_normative.datasets.srm import SRMLoader
from open_normative.datasets.trt import TRTLoader
from open_normative.datasets.depress import DepressLoader

DATASETS = {
    "lemon": LEMONLoader,
    "hbn": HBNLoader,
    "mipdb": MIPDBLoader,
    "dortmund": DortmundLoader,
    "srm": SRMLoader,
    "trt": TRTLoader,
    "depress": DepressLoader,
}
