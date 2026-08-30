"""Every typed exception in PayLoop. Nothing outside api/app.py catches bare Exception."""


class PayLoopError(Exception):
    pass


class SchemaViolation(PayLoopError):
    pass


class FeatureLeakage(PayLoopError):
    """A label or raw identifier reached the feature set. Never caught."""


class BlindHoldoutLeak(PayLoopError):
    """The blind cohort intersects a training pool. Never caught: it voids the headline claim."""


class RegistryInvalid(PayLoopError):
    pass


class FidelityGateFailure(PayLoopError):
    pass


class RedAgentUnavailable(PayLoopError):
    pass


class ProposalInvalid(PayLoopError):
    pass


class InjectorProducedNothing(PayLoopError):
    pass


class PrevalenceExceeded(PayLoopError):
    pass


class WarehouseUnavailable(PayLoopError):
    pass


class ModelArtifactMissing(PayLoopError):
    pass


class LatencyBudgetExceeded(PayLoopError):
    pass
