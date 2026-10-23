"""Agent failure loop: benchmark, trace, judge, analyse, fix, measure.

Everything in this package is additive. It reads AgentIQ through its public
graph API and reuses EvalForge's judge and statistics rather than restating
them. Nothing here imports from, or writes to, either project's own modules.
"""
