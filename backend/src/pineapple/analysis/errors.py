"""The one exception type the analysis package raises for expected failures."""


class AnalysisError(Exception):
    """A problem the user can act on: a malformed archive, a wrong password, a
    missing manifest. Raised instead of leaking library-specific exceptions."""


class ArtifactUnreadable(AnalysisError):
    """One source database could not be parsed (damaged or an unexpected schema).

    The run records it as skipped and carries on with the other artifacts.
    """
