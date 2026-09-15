"""Bond domain service package.

This layer converts normalized provider raw records (CcilRawRecord,
NseRawRecord, RbiRawRecord) into the internal normalized Bond model.

Source-specific retrieval / parsing lives in backend.services.data.bonds.*.
Analytics lives in bond_analytics.py.
Cash-flow generation lives in bond_cashflows.py.
Normalization logic lives in bond_normalizer.py.
"""
