"""
Regression tests for cache-mutation-via-shared-reference (Lens A findings).

Confirmed scope
---------------
- MemoryStorage and any storage wrapped in CachingMiddleware are affected;
  plain JSONStorage re-parses from disk on every read and is unaffected.
- Nested / mutable field values (e.g. appending to a list field) leak through
  the shared cache reference.
- Top-level field *reassignment* (doc['key'] = value) does NOT leak, because
  the Document dict object is a separate copy from what is stored; only
  mutations to nested mutable objects (list.append, dict update) propagate.

Each test below uses TinyDB(storage=CachingMiddleware(JSONStorage)) which is
TinyDB's own documented caching pattern, as required by the regression spec.
"""

import pytest

from tinydb import TinyDB, where
from tinydb.middlewares import CachingMiddleware
from tinydb.storages import JSONStorage, MemoryStorage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def caching_json_db(tmp_path):
    """TinyDB backed by CachingMiddleware(JSONStorage) — the canonical setup."""
    db = TinyDB(tmp_path / 'test_cache_mutation.json',
                storage=CachingMiddleware(JSONStorage))
    yield db
    db.close()


@pytest.fixture
def memory_db():
    """TinyDB backed by plain MemoryStorage."""
    db = TinyDB(storage=MemoryStorage)
    yield db
    db.close()



# ---------------------------------------------------------------------------
# 2. Table._read_table — raw storage reference must not be exposed
# ---------------------------------------------------------------------------

class TestReadTableMutation:
    """
    Covers: tinydb/table.py  Table._read_table  (lines 774-797)

    Before the fix: _read_table() returned tables[self.name] — a direct
    reference into the live storage dict.  Mutating a nested value on a
    document returned by get() or __iter__ would silently update the storage.

    After the fix: copy.deepcopy is applied before returning.
    """

    def test_get_result_mutation_does_not_corrupt_storage(
            self, caching_json_db):
        """
        Mutate a nested list on a get() result; a subsequent get() must
        return the original, unmodified data.
        """
        db = caching_json_db
        db.insert({'key': 'sentinel', 'data': [1, 2, 3]})

        doc = db.get(where('key') == 'sentinel')
        assert doc['data'] == [1, 2, 3]

        # Append to the nested list — this must NOT leak into storage.
        doc['data'].append(999)

        doc2 = db.get(where('key') == 'sentinel')
        assert doc2['data'] == [1, 2, 3], (
            "Storage mutation leak: appending to a nested list on a get() "
            "result corrupted the underlying storage state."
        )

    def test_iter_result_mutation_does_not_corrupt_storage(
            self, caching_json_db):
        """
        Mutate a nested list on a document yielded by iterating the table;
        a subsequent get() must return the original, unmodified data.
        """
        db = caching_json_db
        db.insert({'key': 'iter_sentinel', 'items': ['a', 'b']})

        for doc in db:
            if doc.get('key') == 'iter_sentinel':
                doc['items'].append('INJECTED')
                break

        doc2 = db.get(where('key') == 'iter_sentinel')
        assert doc2['items'] == ['a', 'b'], (
            "Storage mutation leak: appending to a nested list on an "
            "__iter__ result corrupted the underlying storage state."
        )

    def test_get_result_mutation_does_not_corrupt_storage_memory(
            self, memory_db):
        """Same check against MemoryStorage."""
        db = memory_db
        db.insert({'key': 'mem_sentinel', 'vals': [10, 20]})

        doc = db.get(where('key') == 'mem_sentinel')
        doc['vals'].append(999)

        doc2 = db.get(where('key') == 'mem_sentinel')
        assert doc2['vals'] == [10, 20], (
            "MemoryStorage mutation leak: nested list mutation via get() "
            "corrupted the in-memory storage state."
        )


# ---------------------------------------------------------------------------
# 3. CachingMiddleware.read — returned dict must be a copy
# ---------------------------------------------------------------------------

class TestCachingMiddlewareReadMutation:
    """
    Covers: tinydb/middlewares.py  CachingMiddleware.read  (lines 97-106)

    Before the fix: read() returned self.cache directly.  The caller (Table)
    received a live reference to the cache dict.  Any mutation of a nested
    document field propagated back into self.cache without a write() call,
    producing stale / corrupt data on the next flush to disk.

    After the fix: copy.deepcopy(self.cache) is returned.
    """

    def test_caching_middleware_read_returns_independent_copy(
            self, caching_json_db):
        """
        Confirm that the dict returned by storage.read() is not the same
        object as the internal cache after a CachingMiddleware read.
        """
        db = caching_json_db
        db.insert({'probe': True, 'nested': {'count': 0}})

        # Access internal storage through TinyDB's public _storage property.
        raw = db._storage.read()
        assert raw is not None

        # Mutate a nested value in the raw read result.
        for table_data in raw.values():
            for doc in table_data.values():
                if isinstance(doc, dict) and 'nested' in doc:
                    doc['nested']['count'] = 9999

        # A second read must return the original, un-mutated data.
        raw2 = db._storage.read()
        for table_data in raw2.values():
            for doc in table_data.values():
                if isinstance(doc, dict) and 'nested' in doc:
                    assert doc['nested']['count'] == 0, (
                        "CachingMiddleware.read() returned the live cache "
                        "reference; mutation via the first read corrupted "
                        "the second read."
                    )


# ---------------------------------------------------------------------------
# 4. MemoryStorage.read — returned dict must be a copy
# ---------------------------------------------------------------------------

class TestMemoryStorageReadMutation:
    """
    Covers: tinydb/storages.py  MemoryStorage.read  (lines 177-178)

    Before the fix: read() returned self.memory directly.

    After the fix: copy.deepcopy(self.memory) is returned.
    """

    def test_memory_storage_read_returns_independent_copy(self, memory_db):
        """
        Confirm that mutating the dict returned by MemoryStorage.read() does
        not affect what is returned by a subsequent read().
        """
        db = memory_db
        db.insert({'sensor': 'A', 'readings': [1, 2, 3]})

        raw = db._storage.read()
        assert raw is not None

        # Mutate a nested list in the raw result.
        for table_data in raw.values():
            for doc in table_data.values():
                if isinstance(doc, dict) and 'readings' in doc:
                    doc['readings'].append(999)

        raw2 = db._storage.read()
        for table_data in raw2.values():
            for doc in table_data.values():
                if isinstance(doc, dict) and 'readings' in doc:
                    assert doc['readings'] == [1, 2, 3], (
                        "MemoryStorage.read() returned the live self.memory "
                        "reference; mutation via the first read corrupted "
                        "the second read."
                    )
