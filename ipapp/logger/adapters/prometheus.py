import re
from typing import Dict

from prometheus_client import Histogram, start_http_server

import ipapp.logger  # noqa
from ._abc import AbcConfig, AbcAdapter
from ..span import Span
from ...misc import dict_merge

LabelsCfg = Dict[str, Dict[str, str]]

RE_P8S_METRIC_NAME = re.compile(r'[^a-zA-Z0-9_]')

DEFAULT_HISTOGRAM_LABELS: LabelsCfg = {  # {name: {label: tag}, }
    'http_in': {
        'le': '0.01,0.1,1,10,Inf',  # le mapping to quantiles
        'route': 'http.route',
        'host': 'http.host',
        'method': 'http.method',
        'status_code': 'http.status_code',
        'error': 'error.class'
    },
    'http_out': {
        'le': '0.01,0.1,1,10,Inf',  # le mapping to quantiles
        'host': 'http.host',
        'method': 'http.method',
        'status_code': 'http.status_code',
        'error': 'error.class'
    }
}
DEFAULT_HISTOGRAM_DOCS = {
    'http_in': 'Incoming HTTP request',
    'http_out': 'Outgoing HTTP request',
}


class PrometheusConfig(AbcConfig):
    addr: str = '127.0.0.1'
    port: int = 9213
    hist_labels: LabelsCfg = {}
    hist_docs: Dict[str, str] = {}


class PrometheusAdapter(AbcAdapter):
    name = 'prometheus'
    cfg: PrometheusConfig

    def __init__(self):
        self.p8s_hists: Dict[str, Histogram] = {}
        self.p8s_hist_labels: LabelsCfg = {}
        self.p8s_hist_docs: Dict[str, str] = {}

    async def start(self, logger: 'ipapp.logger.Logger',
                    cfg: PrometheusConfig):
        self.cfg = cfg

        self.p8s_hists = {}  # Histograms

        self.p8s_hist_labels = dict_merge(DEFAULT_HISTOGRAM_LABELS,
                                          cfg.hist_labels)
        self.p8s_hist_docs = dict_merge(DEFAULT_HISTOGRAM_DOCS,
                                        cfg.hist_docs)

        for hist_name, labels_cfg in self.p8s_hist_labels.items():
            buckets = Histogram.DEFAULT_BUCKETS
            labelnames = []
            if labels_cfg:
                for label in labels_cfg.keys():
                    if label == 'le':
                        buckets = labels_cfg['le'].split(',')
                    else:
                        labelnames.append(label)

            doc = self.p8s_hist_docs.get(hist_name) or hist_name
            self.p8s_hists[hist_name] = Histogram(hist_name, doc,
                                                  labelnames=labelnames,
                                                  buckets=buckets)
        start_http_server(cfg.port, cfg.addr)

    def handle(self, span: Span):
        name = span.get_name4adapter(self.name)
        tags = span.get_tags4adapter(self.name)

        if name in self.p8s_hists:
            hist: Histogram = self.p8s_hists[name]
            labels_cfg = self.p8s_hist_labels.get(name)
            labels = {}
            if labels_cfg:
                for label, tag in labels_cfg.items():
                    if label != 'le':
                        tag_val = tags.get(tag)
                        labels[label] = tag_val or ''
            if labels:
                hist = hist.labels(**labels)
            hist.observe(span.duration)

    async def stop(self):
        pass
