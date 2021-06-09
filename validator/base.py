import datetime
from typing import Dict, List
from validator.kube.resource import NamespaceKubernetesResource
import json

__all__ = ["ResultSummary", "ClusterResult", "ClusterResultJsonEncoder", "ContainerResult"]


class ResultMessage:
    def __init__(self, id, message, type, category):
        self.id = id
        self.message = message
        self.type = type
        self.category = category


def count_messages(messages: List[ResultMessage]):
    from validator.resource import RESOURCE_VALIDATION_ERROR, RESOURCE_VALIDATION_WARNING, \
        RESOURCE_VALIDATION_SUCCESS
    by_category = dict()
    for msg in messages:
        category_data = CountSummary()
        if msg.type == RESOURCE_VALIDATION_ERROR:
            category_data.errors += 1
        elif msg.type == RESOURCE_VALIDATION_WARNING:
            category_data.warnings += 1
        elif msg.type == RESOURCE_VALIDATION_SUCCESS:
            category_data.successes += 1
        if by_category.__contains__(msg.category):
            by_category[msg.category].add(category_data)
        else:
            by_category[msg.category] = category_data
    return ResultSummary(by_category)


class CountSummary:
    def __init__(self, successes=0, errors=0, warnings=0):
        self.successes = successes
        self.warnings = warnings
        self.errors = errors

    def add(self, item):
        self.successes += item.successes
        self.warnings += item.warnings
        self.errors += item.errors


class ResultSummary:

    def __init__(self, category_summary: Dict[str, CountSummary]):
        self.by_category = category_summary

    @property
    def totals(self):
        count = CountSummary()
        for k in self.by_category:
            count.add(self.by_category[k])
        return count

    def add(self, res):
        if res is None:
            return
        keys = set()
        list(self.by_category.keys()).extend(list())
        for k in self.by_category: keys.add(k)
        for k in res.by_category: keys.add(k)
        for key in keys:
            if res.by_category.__contains__(key) and self.by_category.__contains__(key):
                self.by_category[key].add(res.by_category[key])
            elif res.by_category.__contains__(key):
                self.by_category[key] = res.by_category[key]


class ContainerResult:
    def __init__(self, name, messages: List[ResultMessage]):
        self.name = name
        self.messages = messages

    @property
    def summary(self):
        return count_messages(self.messages)


class PodResult:
    def __init__(self, messages: List[ResultMessage], container_results: List[ContainerResult]):
        self.messages = messages
        self.container_results = container_results

    @property
    def summary(self):
        s = count_messages(self.messages)
        for cr in self.container_results:
            s.add(cr.summary)
        return s


class ControllerResult:
    def __init__(self, name, namespace, type, pod_result: PodResult):
        self.name = name
        self.namespace = namespace
        self.type = type
        self.pod_result = pod_result


class NamespaceInfo():
    def __init__(self, namespace_resource: NamespaceKubernetesResource):
        self.count = {
            "pods": len(namespace_resource.pods),
            "deployments": len(namespace_resource.deployments),
            "statefulSets": len(namespace_resource.stateful_sets),
            "daemonSets": len(namespace_resource.daemon_sets),
            "jobs": len(namespace_resource.jobs),
            "cronJobs": len(namespace_resource.cron_jobs),
        }


class NamespaceResult:
    def __init__(self, name, controller_results):
        self.controller_results = controller_results
        self.name = name

    @property
    def summary(self):
        s = None
        for cr in self.controller_results:
            if s is None:
                s = cr.pod_result.summary
            else:
                s.add(cr.pod_result.summary)
        return s

    def append_controller_result(self, controller_result: ControllerResult):
        self.controller_results.append(controller_result)


class ClusterResult:
    def __init__(self, namespace_results, created_time=datetime.datetime.now()):
        self.created_time = created_time
        self.namespace_results = namespace_results

    @property
    def summary(self):
        s = None
        for cr in self.namespace_results:
            if s is None:
                s = cr.summary
            else:
                s.add(cr.summary)
        return s

    @property
    def score(self):
        if self.summary:
            total = self.summary.totals.successes * 2 + self.summary.totals.warnings + self.summary.totals.errors * 2
            return (float(self.summary.totals.successes * 2) / total) * 100

    @property
    def grade(self):
        score = self.score
        if score >= 97:
            return "A+"
        elif score >= 93:
            return "A"
        elif score >= 90:
            return "A-"
        elif score >= 87:
            return "B+"
        elif score >= 83:
            return "B"
        elif score >= 80:
            return "B-"
        elif score >= 77:
            return "C+"
        elif score >= 73:
            return "C"
        elif score >= 70:
            return "C-"
        elif score >= 67:
            return "D+"
        elif score >= 63:
            return "D"
        elif score >= 60:
            return "D-"
        else:
            return "F"


class ClusterResultJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ClusterResult):
            return {
                "namespace_results": obj.namespace_results,
                "score": obj.score,
                "summary": obj.summary,
                "grade": obj.grade
            }
        if isinstance(obj, NamespaceResult):
            return {
                "controller_results": obj.controller_results,
                "summary": obj.summary,
                "name": obj.name
            }
        if isinstance(obj, ControllerResult):
            return {
                "name": obj.name,
                "type": obj.type,
                "namespace": obj.namespace,
                "pod_result": obj.pod_result
            }

        if isinstance(obj, PodResult):
            return {
                "container_results": obj.container_results,
                "summary": obj.summary,
                "messages": obj.messages,
            }
        if isinstance(obj, ContainerResult):
            return {
                "messages": obj.messages,
                "summary": obj.summary,
                "name": obj.name
            }
        if isinstance(obj, ResultSummary):
            return {
                "totals": obj.totals,
                "by_category": obj.by_category
            }
        if isinstance(obj, ResultMessage):
            return {
                "type": obj.type,
                "category": obj.category,
                "message": obj.message,
                "id": obj.id
            }
        if isinstance(obj, CountSummary):
            return {
                "successes": obj.successes,
                "errors": obj.errors,
                "warnings": obj.warnings
            }

        if isinstance(obj, datetime.datetime):
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        return json.JSONEncoder.default(self, obj)
