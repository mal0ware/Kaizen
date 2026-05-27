"""Model providers behind one interface (ADR 0001/0006).

Importing this package is light — heavy SDKs (anthropic, etc.) are only pulled
in by the concrete adapters when actually used.
"""
