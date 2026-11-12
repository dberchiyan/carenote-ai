"""Shared contracts: the extraction schema and the provider interfaces.

Both the pipeline and the providers depend on this package, and on nothing in each other,
so a vendor SDK can never leak into pipeline code and the pipeline stays pure.
"""
