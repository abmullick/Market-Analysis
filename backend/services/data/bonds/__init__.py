"""Bond data provider package.

Source-specific retrieval/parsing lives here. Each provider normalizes its
raw response into internal CcilRawRecord / NseRawRecord / RbiRawRecord
models. The Bond domain layer then converts those into the normalized
Bond model.

Frontend never sees source-specific field names or URLs.
"""
