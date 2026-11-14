from experiments.bench_v3 import overlap


def test_containment_counts_shared_shingles() -> None:
    a = [overlap.shingles("the station is closed until noon")]
    b = [overlap.shingles("the station is closed from nine"), overlap.shingles("trip is late")]
    assert 0.2 < overlap.containment(a, b) < 0.8
    assert overlap.containment(a, a) == 1.0
    assert overlap.containment(a, [overlap.shingles("nothing alike here at all")]) == 0.0


def test_near_duplicates_keep_the_first_and_drop_the_copy() -> None:
    docs = [
        overlap.shingles("the station is closed to passengers until the evening today"),
        overlap.shingles("the station is closed to passengers until the evening today"),
        overlap.shingles("trip number seven is cancelled because of the strike"),
    ]
    assert overlap.near_duplicates(docs) == {1}


def test_short_text_has_one_shingle() -> None:
    assert overlap.shingles("closed now") == frozenset({"closed now"})
    assert overlap.shingles("") == frozenset()
